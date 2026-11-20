"""Complete, deterministic capability inventory for one repository snapshot.

``detect_repository_capabilities`` answers "which languages are here". This
module answers the question a caller needs before it schedules analysis: for
this exact snapshot, what is every supported language, framework and provider
prerequisite, and in which state is each one.

Nothing here collapses a mixed repository into one language, and nothing here
turns a problem into absence. The states are deliberately separate:

``applicable``
    Positive evidence that the capability applies and the SDK can serve it.
``not_applicable``
    Positive evidence that it does not apply: the files were examined and none
    match. An inventory never reports this without saying what was examined.
``unsupported``
    The capability is present in the repository but the SDK has no analysis
    target for it. It stays visible; it is not absence and it is not a pass.
``incomplete``
    The capability applies but a prerequisite the caller asked to be probed is
    missing, for example the provider executable.
``failed``
    Evidence exists and cannot be trusted: a manifest that does not parse, or
    a packaged rulepack that does not resolve.

The inventory is a factual record. It carries no requiredness, no enforcement
mode and no verdict: Core decides what is required, Assurance decides policy.
"""

from __future__ import annotations

import ast
import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from enum import StrEnum
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from jsonschema import Draft202012Validator

from l9_ci.repository import build_repository_snapshot

CAPABILITY_INVENTORY_PROTOCOL = "l9.capability-inventory/v1"
CAPABILITY_INVENTORY_SCHEMA_VERSION = "1.1.0"

_SAMPLE_LIMIT = 5

# Every language the inventory can name. A language outside the SDK's analysis
# targets is still recognized here so it is reported as ``unsupported`` rather
# than vanishing from the record.
_LANGUAGE_SUFFIXES: Mapping[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".rb": "ruby",
    ".rs": "rust",
    ".php": "php",
    ".swift": "swift",
    ".scala": "scala",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".sh": "shell",
    ".bash": "shell",
    ".xml": "xml",
}

_ODOO_LANGUAGES = ("python", "xml")


class CapabilityState(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LanguageCapability:
    """One language present in the snapshot.

    ``unanalyzed_file_count`` is how many of its files no declared target
    analyzes: a file with a suffix the target's tool does not scan, or a file
    outside the framework a framework target is scoped to. A language is
    ``applicable`` when at least one of its files is analyzed; the rest stay
    counted here and named in the inventory's ``reasons``.
    """

    language: str
    state: CapabilityState
    file_count: int
    sample_paths: tuple[str, ...]
    reason: str
    unanalyzed_file_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "state": self.state.value,
            "file_count": self.file_count,
            "unanalyzed_file_count": self.unanalyzed_file_count,
            "sample_paths": list(self.sample_paths),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class FrameworkCapability:
    """One framework the SDK can recognize, detected or not."""

    framework: str
    state: CapabilityState
    languages: tuple[str, ...]
    language_file_counts: Mapping[str, int]
    evidence_count: int
    evidence_paths: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework,
            "state": self.state.value,
            "languages": list(self.languages),
            "language_file_counts": dict(sorted(self.language_file_counts.items())),
            "evidence_count": self.evidence_count,
            "evidence_paths": list(self.evidence_paths),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ManifestEvidence:
    """One manifest that was read as evidence.

    ``state`` is ``applicable`` when the manifest parsed and ``failed`` when it
    did not. A manifest that does not parse is never treated as missing.

    ``sha256`` is the digest of the bytes that were read, or ``None`` when the
    file could not be read. The snapshot identity covers which paths exist, not
    what they contain, so this is what binds a manifest's state to its content.
    """

    path: str
    kind: str
    state: CapabilityState
    reason: str
    sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "state": self.state.value,
            "reason": self.reason,
            "sha256": self.sha256,
        }


_TARGET_SCOPES = frozenset({"language", "framework"})
_EXECUTABLE_STATES = frozenset({"available", "missing", "not_probed"})


@dataclass(frozen=True, slots=True)
class AnalysisTarget:
    """One thing a provider can analyze, declared by the caller.

    This package detects repository facts and must not import the provider or
    rulepack layers, so the composition layer declares each target and what it
    already knows about it: whether its packaged rulepack resolved and, when a
    probe was requested, whether its executable is available. The inventory
    then decides which of those targets this snapshot actually calls for.

    ``suffixes`` are the file suffixes the target's tool actually analyzes,
    lower case with the leading dot. Empty means every file of ``languages``.
    A file of a served language with any other suffix is counted as not
    analyzed, never as covered.

    ``scope_exclusion`` returns the declared scan-scope entry that keeps a
    repository-relative path out of the target's scan, or ``None`` when the
    path is in scope. A target is planned only on files its scan will
    actually reach: when every matching file is excluded, the target is
    ``not_applicable`` and the reason names the exclusions. The composition
    layer supplies the predicate, because this package must not import the
    scope policy (``l9_ci.rulesets``).
    """

    provider_id: str
    scope: str
    name: str
    languages: tuple[str, ...]
    rulepack: str | None
    rulepack_resolved: bool
    executable: str = "not_probed"
    executable_version: str | None = None
    suffixes: tuple[str, ...] = ()
    scope_exclusion: Callable[[str], str | None] | None = field(
        default=None, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.scope not in _TARGET_SCOPES:
            raise ValueError(f"unknown analysis target scope {self.scope!r}")
        if self.executable not in _EXECUTABLE_STATES:
            raise ValueError(f"unknown executable state {self.executable!r}")
        if not self.provider_id or not self.name or not self.languages:
            raise ValueError(
                "an analysis target needs a provider, a name and languages"
            )
        for suffix in self.suffixes:
            if (
                not suffix.startswith(".")
                or suffix != suffix.lower()
                or len(suffix) < 2
            ):
                raise ValueError(
                    f"analysis target suffix {suffix!r} must be lower case and "
                    "start with a dot"
                )

    @property
    def target(self) -> str:
        return f"{self.scope}:{self.name}"


@dataclass(frozen=True, slots=True)
class ProviderPrerequisite:
    """One analysis target of one provider, and whether it can run.

    ``executable`` is ``not_probed`` unless the caller probed it. The snapshot
    facts are deterministic; the executable is a fact about the machine, so it
    is reported separately and never guessed.
    """

    provider_id: str
    target: str
    state: CapabilityState
    file_count: int
    rulepack: str | None
    executable: str
    executable_version: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "target": self.target,
            "state": self.state.value,
            "file_count": self.file_count,
            "rulepack": self.rulepack,
            "executable": self.executable,
            "executable_version": self.executable_version,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class CapabilityInventory:
    """Every capability fact for one exact repository snapshot."""

    SDK_version: str
    snapshot_id: str
    revision: str | None
    dirty: bool
    source: str
    examined_file_count: int
    unclassified_file_count: int
    languages: tuple[LanguageCapability, ...]
    frameworks: tuple[FrameworkCapability, ...]
    manifests: tuple[ManifestEvidence, ...]
    package_managers: tuple[str, ...]
    provider_prerequisites: tuple[ProviderPrerequisite, ...]
    status: CapabilityState
    reasons: tuple[str, ...]
    schema: str = CAPABILITY_INVENTORY_PROTOCOL
    schema_version: str = CAPABILITY_INVENTORY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "SDK_version": self.SDK_version,
            "snapshot": {
                "snapshot_id": self.snapshot_id,
                "revision": self.revision,
                "dirty": self.dirty,
                "source": self.source,
            },
            "examined_file_count": self.examined_file_count,
            "unclassified_file_count": self.unclassified_file_count,
            "languages": [item.to_dict() for item in self.languages],
            "frameworks": [item.to_dict() for item in self.frameworks],
            "manifests": [item.to_dict() for item in self.manifests],
            "package_managers": list(self.package_managers),
            "provider_prerequisites": [
                item.to_dict() for item in self.provider_prerequisites
            ],
            "status": self.status.value,
            "reasons": list(self.reasons),
        }


def _parse_toml(text: str) -> None:
    tomllib.loads(text)


def _parse_json_object(text: str) -> None:
    if not isinstance(json.loads(text), dict):
        raise ValueError("top-level value is not an object")


def _parse_odoo_manifest(text: str) -> None:
    if not isinstance(ast.literal_eval(text), dict):
        raise ValueError("manifest is not a dictionary literal")


def _parse_nothing(text: str) -> None:
    del text


# name -> (kind, package manager or None, parser). A manifest with no structured
# grammar the SDK reads is still recorded as evidence; it just cannot fail.
_MANIFESTS: Mapping[str, tuple[str, str | None, Callable[[str], None]]] = {
    "pyproject.toml": ("python-project", "python", _parse_toml),
    "requirements.txt": ("python-requirements", "python", _parse_nothing),
    "package.json": ("node-package", "node", _parse_json_object),
    "Cargo.toml": ("cargo-package", "cargo", _parse_toml),
    "go.mod": ("go-module", "go", _parse_nothing),
    "pom.xml": ("maven-project", "maven", _parse_nothing),
    "build.gradle": ("gradle-build", "gradle", _parse_nothing),
    "__manifest__.py": ("odoo-addon", None, _parse_odoo_manifest),
    "__openerp__.py": ("odoo-addon", None, _parse_odoo_manifest),
}


def _read_manifest(root: Path, relative: str) -> ManifestEvidence:
    kind, _, parser = _MANIFESTS[PurePosixPath(relative).name]
    try:
        content = (root / relative).read_bytes()
    except OSError as exc:
        return ManifestEvidence(
            relative,
            kind,
            CapabilityState.FAILED,
            f"manifest could not be read: {type(exc).__name__}",
            None,
        )
    digest = hashlib.sha256(content).hexdigest()
    try:
        parser(content.decode("utf-8"))
    except UnicodeDecodeError:
        return ManifestEvidence(
            relative,
            kind,
            CapabilityState.FAILED,
            "manifest could not be read: UnicodeDecodeError",
            digest,
        )
    except (ValueError, SyntaxError) as exc:
        # tomllib.TOMLDecodeError and json.JSONDecodeError are ValueErrors.
        return ManifestEvidence(
            relative,
            kind,
            CapabilityState.FAILED,
            f"manifest is malformed: {type(exc).__name__}",
            digest,
        )
    return ManifestEvidence(
        relative, kind, CapabilityState.APPLICABLE, "parsed", digest
    )


def _languages(
    by_language: Mapping[str, tuple[str, ...]],
    analyzed: frozenset[str],
    out_of_scope: frozenset[str] = frozenset(),
) -> tuple[LanguageCapability, ...]:
    result = []
    for language in sorted(by_language):
        paths = by_language[language]
        missed = tuple(path for path in paths if path not in analyzed)
        excluded = sum(1 for path in missed if path in out_of_scope)
        if missed and excluded == len(paths):
            state = CapabilityState.UNSUPPORTED
            reason = (
                f"all {excluded} file(s) are outside the declared scan scope, "
                "so no analysis target scans them"
            )
        elif len(missed) == len(paths):
            state = CapabilityState.UNSUPPORTED
            reason = "no declared analysis target analyzes a file of this language"
        elif excluded:
            state = CapabilityState.APPLICABLE
            reason = (
                f"declared analysis targets analyze {len(paths) - len(missed)} of "
                f"{len(paths)} file(s); {excluded} are outside the declared scan "
                f"scope and {len(missed) - excluded} are analyzed by no target"
            )
        elif missed:
            state = CapabilityState.APPLICABLE
            reason = (
                f"declared analysis targets analyze {len(paths) - len(missed)} of "
                f"{len(paths)} file(s); {len(missed)} with suffix "
                f"{', '.join(_suffixes(missed))} or outside a framework scope "
                "are analyzed by none"
            )
        else:
            state = CapabilityState.APPLICABLE
            reason = "declared analysis targets analyze every file of this language"
        result.append(
            LanguageCapability(
                language=language,
                state=state,
                file_count=len(paths),
                sample_paths=paths[:_SAMPLE_LIMIT],
                reason=reason,
                unanalyzed_file_count=len(missed),
            )
        )
    return tuple(result)


def _suffixes(paths: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({PurePosixPath(path).suffix.lower() for path in paths}))


def _odoo_framework(
    all_files: tuple[str, ...],
    manifests: tuple[ManifestEvidence, ...],
) -> FrameworkCapability:
    addon_manifests = [item for item in manifests if item.kind == "odoo-addon"]
    if not addon_manifests:
        return FrameworkCapability(
            framework="odoo",
            state=CapabilityState.NOT_APPLICABLE,
            languages=_ODOO_LANGUAGES,
            language_file_counts={},
            evidence_count=0,
            evidence_paths=(),
            reason=(f"no Odoo addon manifest among {len(all_files)} examined file(s)"),
        )
    valid = [
        item for item in addon_manifests if item.state is CapabilityState.APPLICABLE
    ]
    addon_roots = tuple(
        sorted({str(PurePosixPath(item.path).parent) for item in valid})
    )
    counts = {language: 0 for language in _ODOO_LANGUAGES}
    for file_name in all_files:
        language = _LANGUAGE_SUFFIXES.get(PurePosixPath(file_name).suffix.lower())
        if language not in counts:
            continue
        if any(_is_within(file_name, addon_root) for addon_root in addon_roots):
            counts[language] += 1
    evidence = tuple(item.path for item in addon_manifests)
    if not valid:
        state = CapabilityState.FAILED
        reason = "every Odoo addon manifest found is malformed"
    elif len(valid) < len(addon_manifests):
        state = CapabilityState.FAILED
        reason = (
            f"{len(addon_manifests) - len(valid)} of {len(addon_manifests)} "
            "Odoo addon manifest(s) are malformed"
        )
    else:
        state = CapabilityState.APPLICABLE
        reason = f"{len(valid)} Odoo addon manifest(s) parsed"
    return FrameworkCapability(
        framework="odoo",
        state=state,
        languages=_ODOO_LANGUAGES,
        language_file_counts=counts,
        evidence_count=len(evidence),
        evidence_paths=evidence[:_SAMPLE_LIMIT],
        reason=reason,
    )


def _is_within(file_name: str, directory: str) -> bool:
    if directory == ".":
        return True
    return file_name.startswith(directory + "/")


def _framework_files(
    all_files: tuple[str, ...],
    manifests: tuple[ManifestEvidence, ...],
) -> dict[str, frozenset[str]]:
    """Files inside each detected framework, keyed by framework name."""
    roots = sorted(
        {
            str(PurePosixPath(item.path).parent)
            for item in manifests
            if item.kind == "odoo-addon" and item.state is CapabilityState.APPLICABLE
        }
    )
    return {
        "odoo": frozenset(
            file_name
            for file_name in all_files
            if any(_is_within(file_name, root) for root in roots)
        )
    }


def _analyzed_files(
    target: AnalysisTarget,
    by_language: Mapping[str, tuple[str, ...]],
    frameworks: Mapping[str, FrameworkCapability],
    framework_files: Mapping[str, frozenset[str]],
) -> tuple[frozenset[str], dict[str, tuple[str, ...]]]:
    """The files ``target`` would actually analyze, and those its scope drops.

    A file counts when it belongs to one of the target's languages, has one of
    its suffixes (any suffix when none are declared), for a framework target
    lies inside an applicable framework, and is not excluded by the target's
    declared scan scope. Excluded files are returned grouped by the scope
    entry that excluded them.
    """
    candidates = [
        path for language in target.languages for path in by_language.get(language, ())
    ]
    if target.suffixes:
        allowed = set(target.suffixes)
        candidates = [
            path for path in candidates if PurePosixPath(path).suffix.lower() in allowed
        ]
    if target.scope == "framework":
        framework = frameworks.get(target.name)
        if framework is None or framework.state is not CapabilityState.APPLICABLE:
            return frozenset(), {}
        scope = framework_files.get(target.name, frozenset())
        candidates = [path for path in candidates if path in scope]
    excluded: dict[str, list[str]] = {}
    if target.scope_exclusion is not None:
        kept = []
        for path in candidates:
            label = target.scope_exclusion(path)
            if label is None:
                kept.append(path)
            else:
                excluded.setdefault(label, []).append(path)
        candidates = kept
    return frozenset(candidates), {
        label: tuple(sorted(paths)) for label, paths in sorted(excluded.items())
    }


def _target_file_count(
    target: AnalysisTarget,
    analyzed: frozenset[str],
    frameworks: Mapping[str, FrameworkCapability],
    examined: int,
    excluded: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[int, CapabilityState | None, str]:
    """Return the file count a target would analyze and why it may not apply.

    The second element is ``None`` when the target applies, otherwise the
    state that explains why it does not (``not_applicable`` or ``failed``).
    """
    if target.scope == "framework":
        framework = frameworks.get(target.name)
        if framework is None:
            return (
                0,
                CapabilityState.FAILED,
                f"framework {target.name!r} has no detector in this SDK",
            )
        if framework.state is CapabilityState.NOT_APPLICABLE:
            return 0, CapabilityState.NOT_APPLICABLE, framework.reason
        if framework.state is not CapabilityState.APPLICABLE:
            return 0, CapabilityState.FAILED, framework.reason
    if not analyzed and excluded:
        kind = " or ".join(target.languages)
        count = sum(len(paths) for paths in excluded.values())
        detail = ", ".join(
            f"{label} ({len(paths)}: {', '.join(paths[:3])})"
            for label, paths in excluded.items()
        )
        return (
            0,
            CapabilityState.NOT_APPLICABLE,
            f"no {kind} file this target analyzes is inside the declared scan "
            f"scope: {count} file(s) excluded by {detail}",
        )
    if not analyzed:
        kind = " or ".join(target.languages)
        where = f"{target.name} source " if target.scope == "framework" else ""
        return (
            0,
            CapabilityState.NOT_APPLICABLE,
            f"no {where}{kind} file this target analyzes among {examined} "
            "examined file(s)",
        )
    return len(analyzed), None, ""


def _prerequisites(
    targets: Sequence[AnalysisTarget],
    analyzed_by_target: Mapping[
        str, tuple[frozenset[str], Mapping[str, tuple[str, ...]]]
    ],
    frameworks: Mapping[str, FrameworkCapability],
    examined: int,
) -> tuple[ProviderPrerequisite, ...]:
    result = []
    for target in sorted(targets, key=lambda item: (item.provider_id, item.target)):
        analyzed, excluded = analyzed_by_target[f"{target.provider_id} {target.target}"]
        file_count, blocked, why = _target_file_count(
            target,
            analyzed,
            frameworks,
            examined,
            excluded,
        )
        state: CapabilityState
        if blocked is not None:
            state = blocked
            reason = why
        elif not target.rulepack_resolved:
            state = CapabilityState.FAILED
            reason = "packaged rulepack did not resolve"
        elif target.executable == "missing":
            state = CapabilityState.INCOMPLETE
            reason = "provider executable is not available"
        else:
            state = CapabilityState.APPLICABLE
            reason = f"{file_count} file(s) and a resolved rulepack"
        result.append(
            ProviderPrerequisite(
                provider_id=target.provider_id,
                target=target.target,
                state=state,
                file_count=file_count,
                rulepack=target.rulepack,
                executable=target.executable,
                executable_version=target.executable_version,
                reason=reason,
            )
        )
    return tuple(result)


def _overall(
    languages: tuple[LanguageCapability, ...],
    frameworks: tuple[FrameworkCapability, ...],
    manifests: tuple[ManifestEvidence, ...],
    prerequisites: tuple[ProviderPrerequisite, ...],
    examined: int,
) -> tuple[CapabilityState, tuple[str, ...]]:
    failures = [
        f"{item.path}: {item.reason}"
        for item in manifests
        if item.state is CapabilityState.FAILED
    ]
    failures += [
        f"framework {item.framework}: {item.reason}"
        for item in frameworks
        if item.state is CapabilityState.FAILED
    ]
    failures += [
        f"{item.provider_id} {item.target}: {item.reason}"
        for item in prerequisites
        if item.state is CapabilityState.FAILED
    ]
    if failures:
        return CapabilityState.FAILED, tuple(failures)
    incomplete = [
        f"{item.provider_id} {item.target}: {item.reason}"
        for item in prerequisites
        if item.state is CapabilityState.INCOMPLETE
    ]
    if incomplete:
        return CapabilityState.INCOMPLETE, tuple(incomplete)
    unsupported = tuple(
        f"language {item.language}: {item.reason}"
        for item in languages
        if item.state is CapabilityState.UNSUPPORTED or item.unanalyzed_file_count > 0
    )
    applicable = [
        f"{item.provider_id} {item.target}: {item.reason}"
        for item in prerequisites
        if item.state is CapabilityState.APPLICABLE
    ]
    if applicable:
        return CapabilityState.APPLICABLE, tuple(applicable) + unsupported
    if any(item.state is CapabilityState.UNSUPPORTED for item in languages):
        return CapabilityState.UNSUPPORTED, unsupported
    return (
        CapabilityState.NOT_APPLICABLE,
        (f"no source file in a recognized language among {examined} examined file(s)",),
    )


def build_capability_inventory(
    root: Path,
    *,
    targets: Sequence[AnalysisTarget],
    SDK_version: str,
) -> CapabilityInventory:
    """Inventory every capability fact for the snapshot at ``root``.

    ``targets`` is every analysis target the caller can run. Each one becomes
    exactly one provider prerequisite, in a stated state, whether or not this
    snapshot calls for it. The result is a pure function of the snapshot's
    paths, the content of its manifests and ``targets``.

    ``SDK_version`` is the producing SDK version. Every version-negotiated
    artifact carries it (``.l9/integration-contract.yaml``), and this package
    does not guess it.
    """
    if not isinstance(SDK_version, str) or not SDK_version.strip():
        raise ValueError("SDK_version must be a non-empty string")
    keys = [f"{target.provider_id} {target.target}" for target in targets]
    if len(set(keys)) != len(keys):
        raise ValueError("two analysis targets share a provider and target name")
    root = root.resolve()
    snapshot = build_repository_snapshot(root)
    all_files = snapshot.files

    grouped: dict[str, list[str]] = {}
    unclassified = 0
    manifest_paths: list[str] = []
    for file_name in all_files:
        path = PurePosixPath(file_name)
        if path.name in _MANIFESTS:
            manifest_paths.append(file_name)
        language = _LANGUAGE_SUFFIXES.get(path.suffix.lower())
        if language is None:
            unclassified += 1
            continue
        grouped.setdefault(language, []).append(file_name)
    by_language = {
        language: tuple(sorted(paths)) for language, paths in grouped.items()
    }

    manifests = tuple(_read_manifest(root, path) for path in sorted(manifest_paths))
    package_managers = tuple(
        sorted(
            {
                manager
                for item in manifests
                if (manager := _MANIFESTS[PurePosixPath(item.path).name][1])
            }
        )
    )
    frameworks = (_odoo_framework(all_files, manifests),)
    by_framework = {item.framework: item for item in frameworks}
    framework_files = _framework_files(all_files, manifests)
    analyzed_by_target = {
        f"{target.provider_id} {target.target}": _analyzed_files(
            target, by_language, by_framework, framework_files
        )
        for target in targets
    }
    prerequisites = _prerequisites(
        targets, analyzed_by_target, by_framework, len(all_files)
    )
    analyzed = frozenset().union(*(files for files, _ in analyzed_by_target.values()))
    out_of_scope = (
        frozenset(
            path
            for _, excluded in analyzed_by_target.values()
            for paths in excluded.values()
            for path in paths
        )
        - analyzed
    )
    languages = _languages(by_language, analyzed, out_of_scope)
    status, reasons = _overall(
        languages, frameworks, manifests, prerequisites, len(all_files)
    )
    return CapabilityInventory(
        SDK_version=SDK_version,
        snapshot_id=snapshot.snapshot_id,
        revision=snapshot.revision,
        dirty=snapshot.dirty,
        source=snapshot.source,
        examined_file_count=len(all_files),
        unclassified_file_count=unclassified,
        languages=languages,
        frameworks=frameworks,
        manifests=manifests,
        package_managers=package_managers,
        provider_prerequisites=prerequisites,
        status=status,
        reasons=reasons,
    )


def validate_capability_inventory(payload: Mapping[str, Any]) -> None:
    """Validate a serialized inventory against the bundled v1 schema.

    Schema conformance is not enough to trust ``status``: a payload whose
    ``status`` disagrees with its own entries is rejected, so a consumer cannot
    be handed ``applicable`` over a failed manifest.
    """
    schema_path = files("l9_ci").joinpath(
        "schemas", "v1", "capability-inventory.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(dict(payload)),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        rendered = []
        for error in errors:
            path = "/".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{path}: {error.message}")
        raise ValueError(
            "capability inventory schema validation failed:\n"
            + "\n".join(f"- {item}" for item in rendered)
        )

    entries = (
        list(payload["manifests"])
        + list(payload["frameworks"])
        + list(payload["provider_prerequisites"])
    )
    states = {str(entry["state"]) for entry in entries}
    prerequisite_states = {
        str(entry["state"]) for entry in payload["provider_prerequisites"]
    }
    language_states = {str(entry["state"]) for entry in payload["languages"]}
    if CapabilityState.FAILED.value in states:
        expected = CapabilityState.FAILED
    elif CapabilityState.INCOMPLETE.value in prerequisite_states:
        expected = CapabilityState.INCOMPLETE
    elif CapabilityState.APPLICABLE.value in prerequisite_states:
        expected = CapabilityState.APPLICABLE
    elif CapabilityState.UNSUPPORTED.value in language_states:
        expected = CapabilityState.UNSUPPORTED
    else:
        expected = CapabilityState.NOT_APPLICABLE
    if payload["status"] != expected.value:
        raise ValueError(
            "capability inventory status is inconsistent with its entries: "
            f"status={payload['status']!r}, entries require {expected.value!r}"
        )
    if not payload["reasons"]:
        raise ValueError("capability inventory status carries no reason")
