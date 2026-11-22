"""Resolve and record the declared scan scope of a required Semgrep run.

The policy and its matching live in :mod:`l9_ci.rulesets.semgrep.scope`; this
command-layer module supplies what that layer may not touch: the Git listing
of tracked files, the work-tree file checks and the atomic evidence write.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
import tempfile
from pathlib import Path
from typing import Any

from l9_ci.artifacts.serializer import canonical_json_bytes
from l9_ci.repository.git import inspect_git_repository, is_git_repository
from l9_ci.rulesets.semgrep.scope import (
    ScanScope,
    ScanScopeError,
    ScanScopePolicy,
    build_scan_scope,
)


def resolve_scan_scope(root: Path, policy: ScanScopePolicy) -> ScanScope:
    """Resolve the effective scope of a required run under ``root``.

    Raises :class:`ScanScopeError` when ``root`` is not a Git work tree, and
    whatever :func:`build_scan_scope` raises for an empty or oversized scope.
    """
    root = root.resolve()
    if not is_git_repository(root):
        raise ScanScopeError(
            f"declared scan scope needs a Git work tree; {root} is not one"
        )
    try:
        tracked = inspect_git_repository(root, include_untracked=False).tracked_files
    except ValueError as exc:
        raise ScanScopeError(f"cannot list tracked files: {exc}") from exc

    def is_regular_file(path: str) -> bool:
        on_disk = root / path
        return not on_disk.is_symlink() and on_disk.is_file()

    return build_scan_scope(tracked, is_regular_file=is_regular_file, policy=policy)


def scope_evidence_path(raw_report: Path) -> Path:
    """Return the evidence path beside ``raw_report``: ``<stem>.scope.json``."""
    return raw_report.with_name(f"{raw_report.stem}.scope.json")


def consumer_evidence_path(raw_report: Path) -> Path:
    """Return the consumer record path beside ``raw_report``."""
    return raw_report.with_name(f"{raw_report.stem}.consumer.json")


def write_scope_evidence(
    scope: ScanScope,
    destination: Path,
    *,
    rule_overlaps: Mapping[str, Any] | None = None,
) -> None:
    """Write ``scope`` as canonical JSON, atomically.

    ``rule_overlaps`` records the registry rules a packaged L9 rule supersedes
    in this run (``rule-overlaps.yaml``, ADR 0022).
    """
    payload = scope.to_dict()
    if rule_overlaps is not None:
        payload["rule_overlaps"] = dict(rule_overlaps)
    write_evidence_record(payload, destination)


def write_evidence_record(payload: Mapping[str, Any], destination: Path) -> None:
    """Write one evidence record as canonical JSON, atomically."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(dict(payload)))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


__all__ = [
    "consumer_evidence_path",
    "resolve_scan_scope",
    "scope_evidence_path",
    "write_evidence_record",
    "write_scope_evidence",
]
