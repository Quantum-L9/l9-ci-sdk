"""Declared scan scope for central required Semgrep runs.

A required central run (``l9-ci semgrep run --required``) no longer lets
Semgrep decide what it scans. Semgrep would otherwise take scope from a
consumer's root ``.semgrepignore`` or, when none exists, from its own built-in
default ignore list; neither is declared by Core or the SDK, and the first lets
a consumer drop any path from a required central rule.

This module owns the SDK-packaged policy ``scan-scope.yaml`` and applies it:
every Git-tracked file at the analyzed snapshot, minus the policy's declared
exclusions. Listing the tracked files and writing the evidence belong to the
command layer (``l9_ci.commands.semgrep_scope``); this layer stays free of Git
and serialization. The command passes each resolved file to Semgrep
as an explicit target, which Semgrep never filters through ``.semgrepignore``
(those patterns apply only while expanding a folder scan root). The resolved
scope is written as ``l9.semgrep-scan-scope/v1`` evidence beside the raw
report, so the effective scope of every required run is on record.

Every defect fails closed: an unreadable or malformed policy, an empty scope
or an argv overflow raise :class:`ScanScopeError` rather
than falling back to Semgrep's implicit scope.
"""

from __future__ import annotations

import fnmatch
import functools
import hashlib
import importlib.resources
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

SCAN_SCOPE_POLICY_SCHEMA = "l9.semgrep-scan-scope-policy/v1"
SCAN_SCOPE_EVIDENCE_SCHEMA = "l9.semgrep-scan-scope/v1"
SCAN_SCOPE_EVIDENCE_SCHEMA_VERSION = "1.2.0"

# Per-rule, per-file analysis budget of a required run (B5). Semgrep's defaults
# are a 5 s timeout and a threshold of 3 timeouts per file, after which the
# remaining rules on that file are skipped silently. A required run gives each
# rule/file pair 30 s and never skips rules on a file because others timed out
# (threshold 0 disables the cut-off). A pair that still times out under this
# budget is not analysed, and the provider records it as incomplete coverage
# (l9_ci/providers/semgrep/provider.py, ``_INCOMPLETE_ANALYSIS_ERROR_TYPES``).
REQUIRED_RULE_TIMEOUT_SECONDS = 30
REQUIRED_RULE_TIMEOUT_THRESHOLD = 0

# The only include source the policy may declare: files tracked at the
# analyzed snapshot. Untracked and ignored files are not product code.
_SOURCE_GIT_TRACKED = "git-tracked"

_EXCLUDE_KINDS = ("anchored_paths", "directory_names", "names", "file_globs")

# A path that is tracked but is not a regular file on disk (a submodule
# gitlink, a symlink, or a file deleted from the work tree) cannot be passed to
# Semgrep as a target. It is reported under this label rather than dropped.
NOT_A_REGULAR_FILE = "not-a-regular-file"

# Explicit targets travel on the Semgrep argv. Linux caps the whole argv plus
# environment at ARG_MAX (commonly 2 MiB); past this bound the run fails closed
# with a clear error instead of an opaque exec failure.
MAX_TARGET_ARGUMENT_BYTES = 1_000_000

# Excluded paths recorded per pattern in the evidence; the count is always
# exact, the list is a bounded sample.
EVIDENCE_SAMPLE_LIMIT = 50


class ScanScopeError(ValueError):
    """The declared scan scope could not be resolved; the run must not start."""


@dataclass(frozen=True, slots=True)
class ScanScopePolicy:
    """The parsed ``l9.semgrep-scan-scope-policy/v1`` document."""

    version: str
    source: str
    anchored_paths: tuple[str, ...]
    directory_names: tuple[str, ...]
    names: tuple[str, ...]
    file_globs: tuple[str, ...]
    sha256: str

    def exclusion_for(self, path: str) -> str | None:
        """Return the first declared pattern excluding ``path``, else ``None``.

        The label is ``<kind>:<pattern>`` so evidence names the exact policy
        entry. Kinds are checked in declaration order, so one path is always
        attributed to the same entry.
        """
        parts = PurePosixPath(path).parts
        for anchored in self.anchored_paths:
            if path == anchored or path.startswith(f"{anchored}/"):
                return f"anchored_paths:{anchored}"
        directories = parts[:-1]
        for name in self.directory_names:
            if name in directories:
                return f"directory_names:{name}"
        for name in self.names:
            if name in parts:
                return f"names:{name}"
        base_name = parts[-1] if parts else path
        for glob in self.file_globs:
            if fnmatch.fnmatchcase(base_name, glob):
                return f"file_globs:{glob}"
        return None


@dataclass(frozen=True, slots=True)
class ScanScope:
    """The effective scope of one required Semgrep run."""

    policy: ScanScopePolicy
    targets: tuple[str, ...]
    files_tracked: int
    excluded: tuple[tuple[str, tuple[str, ...]], ...]
    consumer_semgrepignore_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        digest = hashlib.sha256("\n".join(self.targets).encode("utf-8")).hexdigest()
        return {
            "schema": SCAN_SCOPE_EVIDENCE_SCHEMA,
            "schema_version": SCAN_SCOPE_EVIDENCE_SCHEMA_VERSION,
            "policy": {
                "schema": SCAN_SCOPE_POLICY_SCHEMA,
                "version": self.policy.version,
                "sha256": self.policy.sha256,
            },
            "source": self.policy.source,
            "nosem": "disabled",
            "analysis_budget": {
                "timeout_seconds": REQUIRED_RULE_TIMEOUT_SECONDS,
                "timeout_threshold": REQUIRED_RULE_TIMEOUT_THRESHOLD,
                "on_timeout": "incomplete",
            },
            "consumer_semgrepignore": {
                "files": list(self.consumer_semgrepignore_files),
                "honored": False,
            },
            "files_tracked": self.files_tracked,
            "files_in_scope": len(self.targets),
            "in_scope_sha256": digest,
            "excluded": [
                {
                    "pattern": pattern,
                    "count": len(paths),
                    "sample_paths": list(paths[:EVIDENCE_SAMPLE_LIMIT]),
                    "truncated": len(paths) > EVIDENCE_SAMPLE_LIMIT,
                }
                for pattern, paths in self.excluded
            ],
        }


def scan_scope_policy_path() -> Path:
    """Return the packaged scan-scope policy shipped with the SDK."""
    traversable = importlib.resources.files(__package__) / "scan-scope.yaml"
    resolved = Path(str(traversable))
    if not resolved.is_file():
        raise ScanScopeError(
            f"packaged Semgrep scan-scope policy not found: {resolved}"
        )
    return resolved


def _string_list(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ScanScopeError(f"scan-scope policy: {context} must be a list of strings")
    if len(set(value)) != len(value):
        raise ScanScopeError(f"scan-scope policy: {context} has duplicate entries")
    return tuple(value)


def load_scan_scope_policy(path: Path | None = None) -> ScanScopePolicy:
    """Parse and validate a scan-scope policy, failing closed on any defect."""
    policy_path = path if path is not None else scan_scope_policy_path()
    try:
        raw = policy_path.read_bytes()
    except OSError as exc:
        raise ScanScopeError(f"scan-scope policy unreadable: {exc}") from exc
    document = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ScanScopeError("scan-scope policy: document root must be a mapping")
    if document.get("schema") != SCAN_SCOPE_POLICY_SCHEMA:
        raise ScanScopeError(
            f"scan-scope policy: schema must be {SCAN_SCOPE_POLICY_SCHEMA!r}"
        )
    unknown = sorted(set(document) - {"schema", "version", "include", "exclude"})
    if unknown:
        raise ScanScopeError(f"scan-scope policy: unknown keys {unknown}")
    version = document.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ScanScopeError("scan-scope policy: version must be a non-empty string")
    include = document.get("include")
    if not isinstance(include, dict) or set(include) != {"source"}:
        raise ScanScopeError("scan-scope policy: include must be {source: ...}")
    if include["source"] != _SOURCE_GIT_TRACKED:
        raise ScanScopeError(
            f"scan-scope policy: include.source must be {_SOURCE_GIT_TRACKED!r}"
        )
    exclude = document.get("exclude")
    if not isinstance(exclude, dict) or set(exclude) != set(_EXCLUDE_KINDS):
        raise ScanScopeError(
            f"scan-scope policy: exclude must declare exactly {list(_EXCLUDE_KINDS)}"
        )
    lists = {
        kind: _string_list(exclude[kind], context=f"exclude.{kind}")
        for kind in _EXCLUDE_KINDS
    }
    for anchored in lists["anchored_paths"]:
        if anchored.startswith("/") or anchored.endswith("/") or ".." in anchored:
            raise ScanScopeError(
                f"scan-scope policy: anchored path {anchored!r} must be a "
                "normalized repository-relative path"
            )
    for kind in ("directory_names", "names"):
        for name in lists[kind]:
            if "/" in name:
                raise ScanScopeError(
                    f"scan-scope policy: exclude.{kind} entry {name!r} "
                    "must be a single path component"
                )
    return ScanScopePolicy(
        version=version,
        source=_SOURCE_GIT_TRACKED,
        anchored_paths=lists["anchored_paths"],
        directory_names=lists["directory_names"],
        names=lists["names"],
        file_globs=lists["file_globs"],
        sha256=hashlib.sha256(raw).hexdigest(),
    )


@functools.lru_cache(maxsize=1)
def packaged_scan_scope_policy() -> ScanScopePolicy:
    """Return the packaged policy (cached; the packaged file is immutable)."""
    return load_scan_scope_policy()


def build_scan_scope(
    tracked_files: Sequence[str],
    *,
    is_regular_file: Callable[[str], bool],
    policy: ScanScopePolicy,
) -> ScanScope:
    """Apply ``policy`` to the tracked files of one snapshot.

    ``is_regular_file`` reports whether a repository-relative path is a regular
    file in the work tree (not a symlink, a submodule or a deleted file); the
    caller supplies it so this layer stays free of filesystem and Git access.
    Raises :class:`ScanScopeError` when the scope is empty or when the targets
    would overflow the argv bound.
    """
    targets: list[str] = []
    excluded: dict[str, list[str]] = {}
    for path in tracked_files:
        label = policy.exclusion_for(path)
        if label is None and not is_regular_file(path):
            label = NOT_A_REGULAR_FILE
        if label is None:
            # A leading "-" would read as a Semgrep option, not a target.
            targets.append(f"./{path}" if path.startswith("-") else path)
        else:
            excluded.setdefault(label, []).append(path)

    if not targets:
        raise ScanScopeError(
            f"declared scan scope is empty: {len(tracked_files)} tracked file(s), "
            "all excluded by the scan-scope policy"
        )
    argv_bytes = sum(len(os.fsencode(target)) + 1 for target in targets)
    if argv_bytes > MAX_TARGET_ARGUMENT_BYTES:
        raise ScanScopeError(
            f"declared scan scope has {len(targets)} file(s) totalling "
            f"{argv_bytes} argv bytes, over the {MAX_TARGET_ARGUMENT_BYTES}-byte "
            "bound for explicit Semgrep targets"
        )
    return ScanScope(
        policy=policy,
        targets=tuple(targets),
        files_tracked=len(tracked_files),
        excluded=tuple(
            (label, tuple(paths)) for label, paths in sorted(excluded.items())
        ),
        consumer_semgrepignore_files=tuple(
            path
            for path in tracked_files
            if PurePosixPath(path).name == ".semgrepignore"
        ),
    )


__all__ = [
    "EVIDENCE_SAMPLE_LIMIT",
    "MAX_TARGET_ARGUMENT_BYTES",
    "NOT_A_REGULAR_FILE",
    "SCAN_SCOPE_EVIDENCE_SCHEMA",
    "SCAN_SCOPE_EVIDENCE_SCHEMA_VERSION",
    "REQUIRED_RULE_TIMEOUT_SECONDS",
    "REQUIRED_RULE_TIMEOUT_THRESHOLD",
    "SCAN_SCOPE_POLICY_SCHEMA",
    "ScanScope",
    "ScanScopeError",
    "ScanScopePolicy",
    "build_scan_scope",
    "load_scan_scope_policy",
    "packaged_scan_scope_policy",
    "scan_scope_policy_path",
]
