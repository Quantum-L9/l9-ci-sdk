Phase 4 — Spec Closure

Phase 4 closes the remaining gaps between the consolidated implementation and the narrow l9.tool-stack-spec/v1.

It adds:

* dedicated gate evaluation;
* Git-aware repository snapshots;
* capability detection;
* execution profiles and provider selection;
* centralized CLI output and exit codes;
* Semgrep version compatibility;
* bounded-execution failure mapping;
* runtime fixture provenance enforcement;
* raw summary validation;
* complete architecture-layer enforcement;
* repository hygiene cleanup.

It does not add a second provider, Tree-sitter, SQLite, LSP behavior, repair behavior, or Core workflow code. gitingest_l9_ci_sdk_consolidated_phases_1_3.md

⸻

Repository delta

.l9/
├── architecture.yaml                  # replace
├── ownership.yaml                     # replace
├── release-policy.yaml                # update
├── roadmap.yaml                       # replace
└── tool-stack.yaml                    # update
docs/
├── adr/
│   ├── 0006-gate-evaluation.md
│   ├── 0007-repository-snapshot-identity.md
│   └── 0008-agent-payload-is-a-projection.md
└── architecture/
    ├── capability-detection.md
    ├── cli-contract.md
    ├── execution-profiles.md
    ├── gate-evaluation.md
    └── repository-snapshots.md
l9_ci/
├── capabilities/
│   ├── __init__.py
│   ├── detector.py
│   └── model.py
├── cli/
│   ├── __init__.py
│   ├── diagnostics.py
│   ├── exit_codes.py
│   └── output.py
├── execution/
│   ├── __init__.py
│   ├── profiles.py
│   └── selection.py
├── gates/
│   ├── __init__.py
│   ├── evaluator.py
│   └── model.py
├── repository/
│   ├── __init__.py
│   ├── enumerator.py
│   ├── git.py
│   └── snapshot.py
├── providers/
│   └── semgrep/
│       └── versioning.py
└── schemas/
    └── v1/
        ├── gate-result.schema.json
        └── repository-snapshot.schema.json
tests/
├── capabilities/
│   └── test_detector.py
├── cli/
│   ├── test_exit_codes.py
│   └── test_output.py
├── execution/
│   ├── test_profiles.py
│   └── test_selection.py
├── gates/
│   ├── test_evaluator.py
│   └── test_gate_result_schema.py
├── repository/
│   ├── test_enumerator.py
│   └── test_snapshot.py
├── providers/
│   └── semgrep/
│       ├── test_execution_limits.py
│       └── test_versioning.py
└── compatibility/
    └── fixtures/
        └── finding-bundle-v1-bad-summary.json

Delete:

.ruff_cache/

⸻

1. Gate evaluation

l9_ci/gates/model.py

"""Canonical gate evaluation contracts."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping
GATE_RESULT_PROTOCOL = "l9.gate-result/v1"
GATE_RESULT_SCHEMA_VERSION = "1.0.0"
class GateStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"
@dataclass(frozen=True, slots=True)
class GateResult:
    """Result of evaluating a canonical finding bundle."""
    status: GateStatus
    blocking_finding_ids: tuple[str, ...]
    unresolved_finding_ids: tuple[str, ...]
    fatal_provider_ids: tuple[str, ...]
    incomplete_provider_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    schema: str = GATE_RESULT_PROTOCOL
    schema_version: str = GATE_RESULT_SCHEMA_VERSION
    def __post_init__(self) -> None:
        for field_name in (
            "blocking_finding_ids",
            "unresolved_finding_ids",
            "fatal_provider_ids",
            "incomplete_provider_ids",
            "reasons",
        ):
            values = tuple(sorted(set(getattr(self, field_name))))
            object.__setattr__(self, field_name, values)
    @property
    def successful(self) -> bool:
        return self.status is GateStatus.PASS
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "status": self.status.value,
            "blocking_finding_ids": list(self.blocking_finding_ids),
            "unresolved_finding_ids": list(self.unresolved_finding_ids),
            "fatal_provider_ids": list(self.fatal_provider_ids),
            "incomplete_provider_ids": list(self.incomplete_provider_ids),
            "reasons": list(self.reasons),
            "summary": {
                "blocking_count": len(self.blocking_finding_ids),
                "unresolved_count": len(self.unresolved_finding_ids),
                "fatal_provider_count": len(self.fatal_provider_ids),
                "incomplete_provider_count": len(
                    self.incomplete_provider_ids
                ),
            },
        }
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GateResult":
        return cls(
            status=GateStatus(str(payload["status"])),
            blocking_finding_ids=tuple(
                str(item)
                for item in payload.get("blocking_finding_ids", [])
            ),
            unresolved_finding_ids=tuple(
                str(item)
                for item in payload.get("unresolved_finding_ids", [])
            ),
            fatal_provider_ids=tuple(
                str(item)
                for item in payload.get("fatal_provider_ids", [])
            ),
            incomplete_provider_ids=tuple(
                str(item)
                for item in payload.get("incomplete_provider_ids", [])
            ),
            reasons=tuple(
                str(item) for item in payload.get("reasons", [])
            ),
            schema=str(payload.get("schema", GATE_RESULT_PROTOCOL)),
            schema_version=str(
                payload.get(
                    "schema_version",
                    GATE_RESULT_SCHEMA_VERSION,
                )
            ),
        )

⸻

l9_ci/gates/evaluator.py

"""Gate evaluation over canonical findings and provider state."""
from __future__ import annotations
from l9_ci.contracts import (
    CoverageStatus,
    FindingBundle,
    RuleMode,
)
from .model import GateResult, GateStatus
def evaluate_gate(
    bundle: FindingBundle,
    *,
    strict_unresolved: bool = True,
) -> GateResult:
    """Evaluate a validated canonical bundle.
    Evaluation order:
    1. Invalid references or missing classifications produce INVALID.
    2. Fatal required-provider failures or incomplete required coverage
       produce INCOMPLETE.
    3. Blocking findings produce FAIL.
    4. Strict unresolved findings produce INCOMPLETE.
    5. Otherwise the result is PASS.
    """
    finding_ids = {finding.finding_id for finding in bundle.findings}
    classifications = {
        classification.finding_id: classification
        for classification in bundle.classifications
    }
    reasons: list[str] = []
    missing_classifications = finding_ids - set(classifications)
    if missing_classifications:
        reasons.append(
            "findings are missing classifications: "
            + ", ".join(sorted(missing_classifications))
        )
        return GateResult(
            status=GateStatus.INVALID,
            blocking_finding_ids=(),
            unresolved_finding_ids=tuple(missing_classifications),
            fatal_provider_ids=(),
            incomplete_provider_ids=(),
            reasons=tuple(reasons),
        )
    fatal_provider_ids = {
        failure.provider_id
        for failure in bundle.provider_failures
        if failure.required and failure.fatal
    }
    required_provider_ids = {
        provider.provider_id
        for provider in bundle.providers
        if provider.required
    }
    coverage_by_provider = {
        coverage.provider_id: coverage
        for coverage in bundle.coverage
    }
    incomplete_provider_ids: set[str] = set()
    for provider_id in required_provider_ids:
        coverage = coverage_by_provider.get(provider_id)
        if coverage is None:
            incomplete_provider_ids.add(provider_id)
            continue
        if coverage.status in {
            CoverageStatus.FAILED,
            CoverageStatus.PARTIAL,
            CoverageStatus.SKIPPED,
            CoverageStatus.UNSUPPORTED,
        }:
            incomplete_provider_ids.add(provider_id)
    if fatal_provider_ids:
        reasons.append(
            "required providers failed: "
            + ", ".join(sorted(fatal_provider_ids))
        )
    if incomplete_provider_ids:
        reasons.append(
            "required provider coverage is incomplete: "
            + ", ".join(sorted(incomplete_provider_ids))
        )
    if fatal_provider_ids or incomplete_provider_ids:
        return GateResult(
            status=GateStatus.INCOMPLETE,
            blocking_finding_ids=(),
            unresolved_finding_ids=(),
            fatal_provider_ids=tuple(fatal_provider_ids),
            incomplete_provider_ids=tuple(incomplete_provider_ids),
            reasons=tuple(reasons),
        )
    blocking_ids = tuple(
        sorted(
            classification.finding_id
            for classification in bundle.classifications
            if classification.mode is RuleMode.BLOCKING
        )
    )
    unresolved_ids = tuple(
        sorted(
            classification.finding_id
            for classification in bundle.classifications
            if classification.mode is RuleMode.UNRESOLVED
        )
    )
    if blocking_ids:
        reasons.append(
            "blocking findings exist: " + ", ".join(blocking_ids)
        )
        return GateResult(
            status=GateStatus.FAIL,
            blocking_finding_ids=blocking_ids,
            unresolved_finding_ids=unresolved_ids,
            fatal_provider_ids=(),
            incomplete_provider_ids=(),
            reasons=tuple(reasons),
        )
    if strict_unresolved and unresolved_ids:
        reasons.append(
            "unresolved findings exist under strict evaluation: "
            + ", ".join(unresolved_ids)
        )
        return GateResult(
            status=GateStatus.INCOMPLETE,
            blocking_finding_ids=(),
            unresolved_finding_ids=unresolved_ids,
            fatal_provider_ids=(),
            incomplete_provider_ids=(),
            reasons=tuple(reasons),
        )
    return GateResult(
        status=GateStatus.PASS,
        blocking_finding_ids=(),
        unresolved_finding_ids=unresolved_ids,
        fatal_provider_ids=(),
        incomplete_provider_ids=(),
        reasons=(),
    )

⸻

l9_ci/gates/__init__.py

"""Public gate evaluation API."""
from .evaluator import evaluate_gate
from .model import (
    GATE_RESULT_PROTOCOL,
    GATE_RESULT_SCHEMA_VERSION,
    GateResult,
    GateStatus,
)
__all__ = [
    "GATE_RESULT_PROTOCOL",
    "GATE_RESULT_SCHEMA_VERSION",
    "GateResult",
    "GateStatus",
    "evaluate_gate",
]

⸻

l9_ci/schemas/v1/gate-result.schema.json

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.quantum-l9.dev/l9-ci-sdk/v1/gate-result.schema.json",
  "title": "GateResult",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema",
    "schema_version",
    "status",
    "blocking_finding_ids",
    "unresolved_finding_ids",
    "fatal_provider_ids",
    "incomplete_provider_ids",
    "reasons",
    "summary"
  ],
  "properties": {
    "schema": {
      "const": "l9.gate-result/v1"
    },
    "schema_version": {
      "type": "string",
      "pattern": "^1\\.[0-9]+\\.[0-9]+$"
    },
    "status": {
      "enum": [
        "pass",
        "fail",
        "incomplete",
        "invalid"
      ]
    },
    "blocking_finding_ids": {
      "$ref": "#/$defs/stringArray"
    },
    "unresolved_finding_ids": {
      "$ref": "#/$defs/stringArray"
    },
    "fatal_provider_ids": {
      "$ref": "#/$defs/stringArray"
    },
    "incomplete_provider_ids": {
      "$ref": "#/$defs/stringArray"
    },
    "reasons": {
      "$ref": "#/$defs/stringArray"
    },
    "summary": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "blocking_count",
        "unresolved_count",
        "fatal_provider_count",
        "incomplete_provider_count"
      ],
      "properties": {
        "blocking_count": {
          "type": "integer",
          "minimum": 0
        },
        "unresolved_count": {
          "type": "integer",
          "minimum": 0
        },
        "fatal_provider_count": {
          "type": "integer",
          "minimum": 0
        },
        "incomplete_provider_count": {
          "type": "integer",
          "minimum": 0
        }
      }
    }
  },
  "$defs": {
    "stringArray": {
      "type": "array",
      "uniqueItems": true,
      "items": {
        "type": "string",
        "minLength": 1
      }
    }
  }
}

⸻

2. Repository enumeration and snapshots

l9_ci/repository/enumerator.py

"""Repository file enumeration."""
from __future__ import annotations
from pathlib import Path
from typing import Iterable
_DEFAULT_EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
}
def enumerate_repository_files(
    root: Path,
    *,
    include_untracked: bool = True,
    excluded_directories: Iterable[str] = (),
) -> tuple[str, ...]:
    """Enumerate deterministic repository-relative files.
    The generic fallback is filesystem-based. Git-aware enumeration is
    provided by ``l9_ci.repository.git``.
    """
    root = root.resolve()
    if not root.exists():
        raise ValueError(f"repository root does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")
    excluded = _DEFAULT_EXCLUDED_DIRECTORIES | set(excluded_directories)
    files: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        files.append(relative.as_posix())
    del include_untracked
    return tuple(sorted(files))

⸻

l9_ci/repository/git.py

"""Git-backed repository inspection."""
from __future__ import annotations
import subprocess
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True, slots=True)
class GitRepositoryState:
    revision: str
    dirty: bool
    tracked_files: tuple[str, ...]
    untracked_files: tuple[str, ...]
    @property
    def all_files(self) -> tuple[str, ...]:
        return tuple(
            sorted(set(self.tracked_files) | set(self.untracked_files))
        )
def inspect_git_repository(
    root: Path,
    *,
    include_untracked: bool = True,
) -> GitRepositoryState:
    root = root.resolve()
    revision = _run_git(root, "rev-parse", "HEAD").strip()
    status_output = _run_git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    tracked_output = _run_git(
        root,
        "ls-files",
        "-z",
    )
    tracked_files = tuple(
        sorted(
            item
            for item in tracked_output.split("\0")
            if item
        )
    )
    untracked_files: tuple[str, ...] = ()
    if include_untracked:
        untracked_files = tuple(
            sorted(
                line[3:]
                for line in status_output.splitlines()
                if line.startswith("?? ")
            )
        )
    return GitRepositoryState(
        revision=revision,
        dirty=bool(status_output.strip()),
        tracked_files=tracked_files,
        untracked_files=untracked_files,
    )
def is_git_repository(root: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"
def _run_git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(
            f"git command failed: {' '.join(arguments)}: {message}"
        )
    return completed.stdout

⸻

l9_ci/repository/snapshot.py

"""Deterministic repository snapshot identity."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from .enumerator import enumerate_repository_files
from .git import inspect_git_repository, is_git_repository
@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    snapshot_id: str
    revision: str | None
    dirty: bool
    files: tuple[str, ...]
    file_count: int
    source: str
    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "revision": self.revision,
            "dirty": self.dirty,
            "files": list(self.files),
            "file_count": self.file_count,
            "source": self.source,
        }
def build_repository_snapshot(
    root: Path,
    *,
    include_untracked: bool = True,
) -> RepositorySnapshot:
    root = root.resolve()
    if is_git_repository(root):
        state = inspect_git_repository(
            root,
            include_untracked=include_untracked,
        )
        files = state.all_files
        revision = state.revision
        dirty = state.dirty
        source = "git"
    else:
        files = enumerate_repository_files(
            root,
            include_untracked=include_untracked,
        )
        revision = None
        dirty = False
        source = "filesystem"
    digest = _snapshot_digest(
        revision=revision,
        dirty=dirty,
        files=files,
    )
    return RepositorySnapshot(
        snapshot_id=f"snapshot_{digest}",
        revision=revision,
        dirty=dirty,
        files=files,
        file_count=len(files),
        source=source,
    )
def _snapshot_digest(
    *,
    revision: str | None,
    dirty: bool,
    files: tuple[str, ...],
) -> str:
    payload = {
        "revision": revision,
        "dirty": dirty,
        "files": list(files),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

⸻

l9_ci/repository/__init__.py

"""Public repository inspection API."""
from .enumerator import enumerate_repository_files
from .git import GitRepositoryState, inspect_git_repository, is_git_repository
from .snapshot import RepositorySnapshot, build_repository_snapshot
__all__ = [
    "GitRepositoryState",
    "RepositorySnapshot",
    "build_repository_snapshot",
    "enumerate_repository_files",
    "inspect_git_repository",
    "is_git_repository",
]

⸻

l9_ci/schemas/v1/repository-snapshot.schema.json

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.quantum-l9.dev/l9-ci-sdk/v1/repository-snapshot.schema.json",
  "title": "RepositorySnapshot",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "snapshot_id",
    "dirty",
    "files",
    "file_count",
    "source"
  ],
  "properties": {
    "snapshot_id": {
      "type": "string",
      "minLength": 1
    },
    "revision": {
      "type": [
        "string",
        "null"
      ]
    },
    "dirty": {
      "type": "boolean"
    },
    "files": {
      "type": "array",
      "uniqueItems": true,
      "items": {
        "type": "string",
        "minLength": 1,
        "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$)).+$"
      }
    },
    "file_count": {
      "type": "integer",
      "minimum": 0
    },
    "source": {
      "enum": [
        "git",
        "filesystem"
      ]
    }
  }
}

⸻

3. Capability detection

l9_ci/capabilities/model.py

"""Repository capability contracts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
@dataclass(frozen=True, slots=True)
class RepositoryCapabilities:
    root: str
    languages: tuple[str, ...]
    package_managers: tuple[str, ...]
    configuration_files: tuple[str, ...]
    provider_candidates: tuple[str, ...]
    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "languages": list(self.languages),
            "package_managers": list(self.package_managers),
            "configuration_files": list(self.configuration_files),
            "provider_candidates": list(self.provider_candidates),
        }

⸻

l9_ci/capabilities/detector.py

"""Deterministic repository capability detection."""
from __future__ import annotations
from pathlib import Path
from l9_ci.repository import enumerate_repository_files
from .model import RepositoryCapabilities
_LANGUAGE_SUFFIXES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
}
_PACKAGE_FILES = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "go.mod": "go",
    "Cargo.toml": "cargo",
    "pom.xml": "maven",
    "build.gradle": "gradle",
}
_CONFIGURATION_FILES = {
    ".semgrep.yml",
    ".semgrep.yaml",
    "semgrep.yml",
    "semgrep.yaml",
}
def detect_repository_capabilities(
    root: Path,
) -> RepositoryCapabilities:
    files = enumerate_repository_files(root)
    languages: set[str] = set()
    package_managers: set[str] = set()
    configuration_files: set[str] = set()
    for file_name in files:
        path = Path(file_name)
        language = _LANGUAGE_SUFFIXES.get(path.suffix.lower())
        if language:
            languages.add(language)
        package_manager = _PACKAGE_FILES.get(path.name)
        if package_manager:
            package_managers.add(package_manager)
        if path.name in _CONFIGURATION_FILES:
            configuration_files.add(file_name)
    provider_candidates: set[str] = set()
    if languages:
        provider_candidates.add("semgrep")
    return RepositoryCapabilities(
        root=".",
        languages=tuple(sorted(languages)),
        package_managers=tuple(sorted(package_managers)),
        configuration_files=tuple(sorted(configuration_files)),
        provider_candidates=tuple(sorted(provider_candidates)),
    )

⸻

l9_ci/capabilities/__init__.py

"""Public repository capability API."""
from .detector import detect_repository_capabilities
from .model import RepositoryCapabilities
__all__ = [
    "RepositoryCapabilities",
    "detect_repository_capabilities",
]

⸻

4. Execution profiles and provider selection

l9_ci/execution/profiles.py

"""SDK execution profile definitions."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
class ExecutionProfileName(StrEnum):
    NATIVE = "native"
    IMPORT_ONLY = "import_only"
    ALL_SUPPORTED = "all_supported"
@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    name: ExecutionProfileName
    execute_providers: bool
    import_reports: bool
    supported_only: bool
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "execute_providers": self.execute_providers,
            "import_reports": self.import_reports,
            "supported_only": self.supported_only,
        }
PROFILES = {
    ExecutionProfileName.NATIVE: ExecutionProfile(
        name=ExecutionProfileName.NATIVE,
        execute_providers=False,
        import_reports=False,
        supported_only=True,
    ),
    ExecutionProfileName.IMPORT_ONLY: ExecutionProfile(
        name=ExecutionProfileName.IMPORT_ONLY,
        execute_providers=False,
        import_reports=True,
        supported_only=False,
    ),
    ExecutionProfileName.ALL_SUPPORTED: ExecutionProfile(
        name=ExecutionProfileName.ALL_SUPPORTED,
        execute_providers=True,
        import_reports=True,
        supported_only=True,
    ),
}
def get_execution_profile(
    name: str | ExecutionProfileName,
) -> ExecutionProfile:
    profile_name = ExecutionProfileName(name)
    return PROFILES[profile_name]

⸻

l9_ci/execution/selection.py

"""Provider selection from registry, capabilities, and execution profile."""
from __future__ import annotations
from pathlib import Path
from l9_ci.capabilities import RepositoryCapabilities
from l9_ci.providers import Provider, ProviderRegistry, ProviderState
from .profiles import ExecutionProfile
def select_providers(
    *,
    registry: ProviderRegistry,
    capabilities: RepositoryCapabilities,
    profile: ExecutionProfile,
    repository_root: Path,
) -> tuple[Provider, ...]:
    selected: list[Provider] = []
    candidate_ids = set(capabilities.provider_candidates)
    for provider in registry.providers():
        metadata = provider.metadata
        if metadata.provider_id not in candidate_ids:
            continue
        if profile.supported_only:
            if metadata.state is not ProviderState.SUPPORTED:
                continue
        if profile.execute_providers and not metadata.execution_support:
            continue
        if not profile.execute_providers and not metadata.import_support:
            continue
        if not provider.detect(repository_root) and profile.execute_providers:
            continue
        selected.append(provider)
    return tuple(
        sorted(
            selected,
            key=lambda provider: provider.metadata.provider_id,
        )
    )

⸻

l9_ci/execution/__init__.py

"""Public execution profile and provider selection API."""
from .profiles import (
    PROFILES,
    ExecutionProfile,
    ExecutionProfileName,
    get_execution_profile,
)
from .selection import select_providers
__all__ = [
    "PROFILES",
    "ExecutionProfile",
    "ExecutionProfileName",
    "get_execution_profile",
    "select_providers",
]

⸻

5. Centralized CLI contract

l9_ci/cli/exit_codes.py

"""Stable SDK CLI exit codes."""
from enum import IntEnum
class ExitCode(IntEnum):
    SUCCESS = 0
    GATE_FAILURE = 1
    INVALID_ARGUMENTS = 2
    PROVIDER_EXECUTION_FAILURE = 3
    PROVIDER_REPORT_FAILURE = 4
    ARTIFACT_VALIDATION_FAILURE = 5
    UNRESOLVED_STRICT_CONTRACT = 6
    INTERNAL_ERROR = 7
    INCOMPATIBLE_VERSION = 8
    OPERATIONAL_LIMIT_EXCEEDED = 9

⸻

l9_ci/cli/output.py

"""Machine-readable CLI output."""
from __future__ import annotations
import json
from enum import StrEnum
from typing import Any, Mapping
class OutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"
def render_success(
    payload: Mapping[str, Any],
    *,
    output_format: OutputFormat,
) -> str:
    if output_format is OutputFormat.JSON:
        return json.dumps(
            {
                "ok": True,
                "result": dict(payload),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    return "\n".join(
        f"{key}={value}"
        for key, value in sorted(payload.items())
    )

⸻

l9_ci/cli/diagnostics.py

"""Structured CLI diagnostics."""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Mapping
from .output import OutputFormat
@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    details: Mapping[str, Any]
    def render(self, output_format: OutputFormat) -> str:
        if output_format is OutputFormat.JSON:
            return json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": self.code,
                        "message": self.message,
                        "details": dict(self.details),
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        return f"error[{self.code}]: {self.message}"

⸻

l9_ci/cli/__init__.py

"""Public CLI support API."""
from .diagnostics import Diagnostic
from .exit_codes import ExitCode
from .output import OutputFormat, render_success
__all__ = [
    "Diagnostic",
    "ExitCode",
    "OutputFormat",
    "render_success",
]

Replace command-local integer constants in:

l9_ci/commands/semgrep.py
l9_ci/commands/artifacts.py
l9_ci/commands/integration.py

with imports from:

from l9_ci.cli import Diagnostic, ExitCode, OutputFormat, render_success

Add to each command parser:

parser.add_argument(
    "--format",
    choices=("text", "json"),
    default="text",
)

⸻

6. Provider listing and detection commands

Create l9_ci/commands/providers.py:

"""Generic provider registry commands."""
from __future__ import annotations
import argparse
from pathlib import Path
from l9_ci.capabilities import detect_repository_capabilities
from l9_ci.cli import ExitCode, OutputFormat, render_success
from l9_ci.providers import ProviderRegistry, SemgrepProvider
def default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(SemgrepProvider())
    return registry
def register_provider_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    providers = subparsers.add_parser("providers")
    provider_subparsers = providers.add_subparsers(
        dest="providers_command",
        required=True,
    )
    list_parser = provider_subparsers.add_parser("list")
    list_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    list_parser.set_defaults(handler=handle_list)
    detect_parser = provider_subparsers.add_parser("detect")
    detect_parser.add_argument("--root", type=Path, default=Path("."))
    detect_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    detect_parser.set_defaults(handler=handle_detect)
def handle_list(args: argparse.Namespace) -> int:
    registry = default_registry()
    payload = {
        "providers": [
            provider.metadata.to_dict()
            for provider in registry.providers()
        ]
    }
    print(
        render_success(
            payload,
            output_format=OutputFormat(args.format),
        )
    )
    return int(ExitCode.SUCCESS)
def handle_detect(args: argparse.Namespace) -> int:
    registry = default_registry()
    root = args.root.resolve()
    capabilities = detect_repository_capabilities(root)
    providers = []
    for provider in registry.providers():
        providers.append(
            {
                "provider_id": provider.metadata.provider_id,
                "installed": provider.detect(root),
                "version": provider.detect_version(),
                "candidate": (
                    provider.metadata.provider_id
                    in capabilities.provider_candidates
                ),
            }
        )
    print(
        render_success(
            {
                "capabilities": capabilities.to_dict(),
                "providers": providers,
            },
            output_format=OutputFormat(args.format),
        )
    )
    return int(ExitCode.SUCCESS)

Update l9_ci/commands/__init__.py:

from .providers import register_provider_commands

and add:

"register_provider_commands",

⸻

7. Gate CLI

Create l9_ci/commands/gates.py:

"""Gate evaluation commands."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from l9_ci.artifacts import (
    canonical_json_bytes,
    load_and_validate_bundle,
)
from l9_ci.cli import ExitCode
from l9_ci.gates import GateStatus, evaluate_gate
def register_gate_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    gate = subparsers.add_parser("gate")
    gate_subparsers = gate.add_subparsers(
        dest="gate_command",
        required=True,
    )
    evaluate = gate_subparsers.add_parser("evaluate")
    evaluate.add_argument("--bundle", required=True, type=Path)
    evaluate.add_argument("--output", type=Path)
    evaluate.add_argument(
        "--strict-unresolved",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    evaluate.set_defaults(handler=handle_evaluate)
def handle_evaluate(args: argparse.Namespace) -> int:
    try:
        bundle = load_and_validate_bundle(args.bundle)
        result = evaluate_gate(
            bundle,
            strict_unresolved=args.strict_unresolved,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.ARTIFACT_VALIDATION_FAILURE)
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)
    content = canonical_json_bytes(result.to_dict())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(content)
    else:
        sys.stdout.buffer.write(content)
    if result.status is GateStatus.PASS:
        return int(ExitCode.SUCCESS)
    if result.status is GateStatus.FAIL:
        return int(ExitCode.GATE_FAILURE)
    if result.status is GateStatus.INCOMPLETE:
        return int(ExitCode.UNRESOLVED_STRICT_CONTRACT)
    return int(ExitCode.ARTIFACT_VALIDATION_FAILURE)

⸻

8. Semgrep version compatibility

l9_ci/providers/semgrep/versioning.py

"""Supported Semgrep version checks."""
from __future__ import annotations
import re
from dataclasses import dataclass
from l9_ci.integration import SemanticVersion
_VERSION_PATTERN = re.compile(r"(?P<version>[0-9]+\.[0-9]+\.[0-9]+)")
@dataclass(frozen=True, slots=True)
class SemgrepVersionPolicy:
    minimum: SemanticVersion
    maximum_exclusive: SemanticVersion | None = None
    def supports(self, version: SemanticVersion) -> bool:
        if version < self.minimum:
            return False
        if (
            self.maximum_exclusive is not None
            and version >= self.maximum_exclusive
        ):
            return False
        return True
DEFAULT_SEMGREP_VERSION_POLICY = SemgrepVersionPolicy(
    minimum=SemanticVersion.parse("1.100.0"),
    maximum_exclusive=None,
)
def parse_semgrep_version(raw: str) -> SemanticVersion:
    match = _VERSION_PATTERN.search(raw)
    if not match:
        raise ValueError(
            f"unable to parse Semgrep version from {raw!r}"
        )
    return SemanticVersion.parse(match.group("version"))
def require_supported_semgrep_version(
    raw: str,
    *,
    policy: SemgrepVersionPolicy = DEFAULT_SEMGREP_VERSION_POLICY,
) -> SemanticVersion:
    version = parse_semgrep_version(raw)
    if not policy.supports(version):
        raise ValueError(
            f"unsupported Semgrep version: {raw!r}; "
            f"minimum is "
            f"{policy.minimum.major}."
            f"{policy.minimum.minor}."
            f"{policy.minimum.patch}"
        )
    return version

Update SemgrepProvider.validate_configuration() to validate the detected version when Semgrep is installed.

⸻

9. Execution failure mapping

Update SemgrepProvider.execute() so timeout and output-limit conditions can be converted into structured failures by a helper.

Add:

def execution_failure(
    self,
    result: ProviderExecutionResult,
    *,
    required: bool,
    provider_version: str | None,
) -> ProviderFailure | None:
    if result.timed_out:
        return ProviderFailure(
            provider_id="semgrep",
            provider_version=provider_version,
            failure_type=ProviderFailureType.TIMEOUT,
            message="Semgrep execution timed out",
            required=required,
            fatal=required,
        )
    if result.output_limit_exceeded:
        return ProviderFailure(
            provider_id="semgrep",
            provider_version=provider_version,
            failure_type=ProviderFailureType.OUTPUT_LIMIT_EXCEEDED,
            message="Semgrep output exceeded the configured limit",
            required=required,
            fatal=required,
            exit_code=result.exit_code,
        )
    if result.report_path is None:
        return ProviderFailure(
            provider_id="semgrep",
            provider_version=provider_version,
            failure_type=ProviderFailureType.REPORT_MISSING,
            message="Semgrep did not produce a report",
            required=required,
            fatal=required,
            exit_code=result.exit_code,
        )
    if result.exit_code not in {0, 1}:
        return ProviderFailure(
            provider_id="semgrep",
            provider_version=provider_version,
            failure_type=ProviderFailureType.EXECUTION_ERROR,
            message="Semgrep exited unsuccessfully",
            required=required,
            fatal=required,
            exit_code=result.exit_code,
        )
    return None

Do not treat Semgrep finding exit behavior as a generic execution failure unless the pinned Semgrep invocation contract confirms it.

⸻

10. Raw summary validation

Update l9_ci/artifacts/validator.py.

Add:

def validate_raw_summary(
    payload: Mapping[str, Any],
) -> ValidationResult:
    expected = {
        "provider_count": len(payload.get("providers", [])),
        "evidence_count": len(payload.get("evidence", [])),
        "finding_count": len(payload.get("findings", [])),
        "classification_count": len(
            payload.get("classifications", [])
        ),
        "provider_failure_count": len(
            payload.get("provider_failures", [])
        ),
        "coverage_count": len(payload.get("coverage", [])),
    }
    actual = payload.get("summary")
    if actual != expected:
        return ValidationResult(
            valid=False,
            errors=(
                "bundle summary does not match raw record counts",
            ),
        )
    return ValidationResult(valid=True, errors=())

In load_and_validate_bundle() add before deserialization:

summary_result = validate_raw_summary(payload)
summary_result.require_valid()

Export from l9_ci/artifacts/__init__.py.

⸻

tests/compatibility/fixtures/finding-bundle-v1-bad-summary.json

Use the minimal fixture but set:

"summary": {
  "provider_count": 999,
  "evidence_count": 0,
  "finding_count": 0,
  "classification_count": 0,
  "provider_failure_count": 0,
  "coverage_count": 0
}

⸻

11. Snapshot integration into Semgrep pipeline

Update SemgrepPipelineRequest:

snapshot_id: str | None = None
derive_snapshot: bool = False

Before normalization:

from l9_ci.repository import build_repository_snapshot
repository_snapshot = None
if request.derive_snapshot:
    repository_snapshot = build_repository_snapshot(
        request.repository_root
    )
snapshot_id = request.snapshot_id
if repository_snapshot is not None:
    snapshot_id = repository_snapshot.snapshot_id
if not snapshot_id:
    raise ValueError(
        "snapshot_id is required unless derive_snapshot is enabled"
    )

Use snapshot_id throughout normalization and bundle construction.

Snapshot descriptor:

snapshot=SnapshotDescriptor(
    snapshot_id=snapshot_id,
    repository_root=".",
    revision=(
        repository_snapshot.revision
        if repository_snapshot
        else request.revision
    ),
    dirty=(
        repository_snapshot.dirty
        if repository_snapshot
        else request.dirty
    ),
),

Add CLI flag:

--derive-snapshot

Make --snapshot-id optional only when --derive-snapshot is supplied.

⸻

12. Agent payload terminology correction

The bundle remains canonical.

The agent payload is explicitly a projection.

Modify constants in l9_ci/integration/agent_payload.py:

AGENT_REVIEW_PAYLOAD_PROTOCOL = "l9.agent-review-projection/v1"

Rename the schema title:

"title": "AgentReviewProjection"

Update:

.l9/integration-contract.yaml
docs/architecture/agent-review-payload.md
docs/architecture/artifact-protocol.md
docs/adr/0004-versioned-artifact-protocol.md

Do not necessarily rename the Python classes in v1. The compatibility-visible protocol distinction is the important part.

⸻

Architecture specification

Replace .l9/architecture.yaml

schema: l9.architecture-spec/v1
metadata:
  repository: Quantum-L9/l9-ci-sdk
  version: 1.1.0
  status: authoritative
layers:
  contracts:
    package: l9_ci.contracts
    responsibility:
      - immutable canonical models
      - canonical enums
      - model invariants
    may_depend_on:
      - Python standard library
  repository:
    package: l9_ci.repository
    responsibility:
      - repository enumeration
      - Git inspection
      - deterministic snapshot identity
    may_depend_on:
      - Python standard library
    must_not_depend_on:
      - providers
      - policy
      - gates
      - integration
  capabilities:
    package: l9_ci.capabilities
    responsibility:
      - repository capability detection
    may_depend_on:
      - repository
      - contracts
  providers:
    package: l9_ci.providers
    responsibility:
      - provider metadata
      - provider execution
      - report import
      - provider normalization
      - provider coverage
    may_depend_on:
      - contracts
      - identity
      - repository
    must_not_depend_on:
      - artifacts
      - gates
      - integration
      - workflow code
  identity:
    package: l9_ci.identity
    responsibility:
      - explicit canonical rule identity resolution
    may_depend_on:
      - contracts
  policy:
    package: l9_ci.policy
    responsibility:
      - policy loading
      - finding classification
    may_depend_on:
      - contracts
    must_not_depend_on:
      - providers
      - artifacts
      - gates
  execution:
    package: l9_ci.execution
    responsibility:
      - execution profiles
      - provider selection
    may_depend_on:
      - capabilities
      - providers
  artifacts:
    package: l9_ci.artifacts
    responsibility:
      - deterministic serialization
      - schema validation
      - semantic validation
      - atomic writes
    may_depend_on:
      - contracts
    must_not_depend_on:
      - providers
      - policy
      - gates
  gates:
    package: l9_ci.gates
    responsibility:
      - gate evaluation
    may_depend_on:
      - contracts
    must_not_depend_on:
      - providers
      - policy
      - integration
  pipeline:
    package: l9_ci.pipeline
    responsibility:
      - public SDK composition flows
    may_depend_on:
      - repository
      - providers
      - identity
      - policy
      - artifacts
      - integration
  integration:
    package: l9_ci.integration
    responsibility:
      - operational limits
      - compatibility negotiation
      - redaction validation
      - non-canonical projections
    may_depend_on:
      - contracts
    must_not_depend_on:
      - providers
      - pipeline
  cli:
    package: l9_ci.cli
    responsibility:
      - stable exit codes
      - structured diagnostics
      - output formatting
    may_depend_on:
      - Python standard library
  commands:
    package: l9_ci.commands
    responsibility:
      - command registration
      - public CLI composition
    may_depend_on:
      - public SDK packages
public_surface:
  packages:
    - l9_ci.contracts
    - l9_ci.repository
    - l9_ci.capabilities
    - l9_ci.providers
    - l9_ci.identity
    - l9_ci.policy
    - l9_ci.execution
    - l9_ci.artifacts
    - l9_ci.gates
    - l9_ci.integration
    - l9_ci.cli
forbidden_dependency_edges:
  - contracts_to_providers
  - contracts_to_artifacts
  - providers_to_artifacts
  - providers_to_policy
  - providers_to_gates
  - artifacts_to_providers
  - policy_to_providers
  - gates_to_providers
  - integration_to_pipeline
  - SDK_to_Core
  - SDK_to_LSP
  - SDK_to_Repair
  - SDK_to_Corpus
canonical_flow:
  - repository
  - capabilities
  - execution
  - providers
  - identity
  - policy
  - gates
  - artifacts
  - projections

⸻

Ownership specification

Replace .l9/ownership.yaml

schema: l9.ownership-spec/v1
repository: Quantum-L9/l9-ci-sdk
ownership:
  l9_ci/contracts:
    owns:
      - canonical models
      - canonical enums
      - local invariants
  l9_ci/repository:
    owns:
      - file enumeration
      - Git repository inspection
      - snapshot identity
  l9_ci/capabilities:
    owns:
      - language detection
      - repository capability detection
      - provider candidacy signals
  l9_ci/providers:
    owns:
      - provider SPI
      - provider-native parsing
      - provider execution
      - provider normalization
      - provider coverage
      - provider failures
  l9_ci/identity:
    owns:
      - canonical identity resolution
      - versioned identity maps
  l9_ci/policy:
    owns:
      - policy parsing
      - finding classification
  l9_ci/execution:
    owns:
      - execution profiles
      - provider selection
  l9_ci/artifacts:
    owns:
      - canonical serialization
      - schema validation
      - semantic validation
      - atomic writes
  l9_ci/gates:
    owns:
      - pass, fail, incomplete, and invalid gate outcomes
  l9_ci/integration:
    owns:
      - compatibility negotiation
      - operational limits
      - redaction validation
      - non-canonical projections
  l9_ci/cli:
    owns:
      - stable exit codes
      - CLI output format
      - structured diagnostics
external_boundaries:
  l9-ci-core:
    relationship: consumer
    allowed:
      - invoke public CLI
      - supply policy
      - select required providers
      - publish gate results
      - upload artifacts
    prohibited:
      - parse provider-native reports
      - reconstruct canonical findings
      - mutate canonical bundles
      - synthesize rule identity

⸻

ADRs

docs/adr/0006-gate-evaluation.md

# ADR 0006: Separate Gate Evaluation from Classification
## Status
Accepted
## Context
Classification states how governance treats a finding. Gate evaluation decides
the overall outcome of a bundle.
Provider failures and incomplete coverage can prevent a trustworthy result
even when no blocking finding exists.
## Decision
Gate evaluation is a separate SDK stage.
Gate status is one of:
- pass
- fail
- incomplete
- invalid
Missing required evidence can never produce pass.
## Consequences
- Classification remains finding-local.
- Provider completeness affects the overall decision.
- Core publishes the result but does not calculate it.

⸻

docs/adr/0007-repository-snapshot-identity.md

# ADR 0007: Derive Snapshot Identity in the SDK
## Status
Accepted
## Context
Evidence and finding identities depend on a deterministic repository snapshot.
Requiring every caller to construct snapshot identity creates inconsistent
identity semantics.
## Decision
The SDK provides Git-aware repository enumeration and snapshot construction.
Callers may provide an external snapshot ID, but the SDK can derive one from:
- revision;
- dirty state;
- normalized repository file inventory.
## Consequences
- Identity construction is consistent across consumers.
- Non-Git repositories remain supported through a filesystem fallback.
- Snapshot derivation is testable independently of providers.

⸻

docs/adr/0008-agent-payload-is-a-projection.md

# ADR 0008: Agent Payload Is a Projection
## Status
Accepted
## Context
The finding bundle is the canonical SDK artifact.
Agent consumers benefit from a smaller categorized view, but a second
canonical protocol would create competing sources of truth.
## Decision
The agent-review payload is a deterministic projection.
It must retain source finding IDs and may always be regenerated from the
canonical finding bundle.
## Consequences
- The finding bundle remains authoritative.
- Projection schemas may evolve independently.
- Consumers must not use the projection as canonical storage.

⸻

Key tests

tests/gates/test_evaluator.py

from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    FindingBundle,
    FindingClassification,
    ProviderRun,
    ResolutionStatus,
    RuleMode,
    SnapshotDescriptor,
)
from l9_ci.gates import GateStatus, evaluate_gate
def bundle(
    *,
    mode: RuleMode | None = None,
    coverage_status: CoverageStatus = CoverageStatus.COMPLETE,
) -> FindingBundle:
    classifications = ()
    if mode is not None:
        classifications = (
            FindingClassification(
                finding_id="finding-1",
                mode=mode,
                resolution_status=(
                    ResolutionStatus.UNRESOLVED
                    if mode is RuleMode.UNRESOLVED
                    else ResolutionStatus.EXPLICIT
                ),
                used_default=False,
                policy_key=(
                    None
                    if mode is RuleMode.UNRESOLVED
                    else "L9-RULE"
                ),
            ),
        )
    return FindingBundle(
        SDK_version="1.0.0",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor(
            snapshot_id="snapshot-1",
            repository_root=".",
        ),
        providers=(
            ProviderRun(
                provider_id="semgrep",
                adapter_version="1.0.0",
                provider_version="1.100.0",
                mode="import",
                required=True,
            ),
        ),
        evidence=(),
        findings=(),
        classifications=classifications,
        provider_failures=(),
        coverage=(
            Coverage(
                provider_id="semgrep",
                status=coverage_status,
                files_considered=1,
                files_analyzed=(
                    1
                    if coverage_status is CoverageStatus.COMPLETE
                    else 0
                ),
                limitations=(),
            ),
        ),
    )
def test_complete_empty_bundle_passes() -> None:
    result = evaluate_gate(bundle())
    assert result.status is GateStatus.PASS
def test_required_partial_coverage_is_incomplete() -> None:
    result = evaluate_gate(
        bundle(coverage_status=CoverageStatus.PARTIAL)
    )
    assert result.status is GateStatus.INCOMPLETE

For blocking and unresolved tests, create a complete finding/evidence pair rather than injecting orphan classifications.

⸻

tests/repository/test_snapshot.py

from pathlib import Path
from l9_ci.repository import build_repository_snapshot
def test_filesystem_snapshot_is_deterministic(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("print('b')\n", encoding="utf-8")
    first = build_repository_snapshot(tmp_path)
    second = build_repository_snapshot(tmp_path)
    assert first.snapshot_id == second.snapshot_id
    assert first.files == ("a.py", "b.py")

⸻

tests/providers/semgrep/test_versioning.py

import pytest
from l9_ci.providers.semgrep.versioning import (
    SemgrepVersionPolicy,
    parse_semgrep_version,
    require_supported_semgrep_version,
)
from l9_ci.integration import SemanticVersion
def test_parse_semgrep_version() -> None:
    assert parse_semgrep_version("1.100.0") == SemanticVersion(
        1,
        100,
        0,
    )
def test_version_with_prefix_is_parsed() -> None:
    assert parse_semgrep_version(
        "semgrep 1.101.2"
    ) == SemanticVersion(1, 101, 2)
def test_old_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        require_supported_semgrep_version("1.99.0")
def test_maximum_exclusive_is_enforced() -> None:
    policy = SemgrepVersionPolicy(
        minimum=SemanticVersion.parse("1.100.0"),
        maximum_exclusive=SemanticVersion.parse("2.0.0"),
    )
    with pytest.raises(ValueError):
        require_supported_semgrep_version(
            "2.0.0",
            policy=policy,
        )

⸻

tests/providers/semgrep/test_execution_limits.py

from pathlib import Path
from l9_ci.contracts import ProviderFailureType
from l9_ci.providers import ProviderExecutionResult
from l9_ci.providers.semgrep import SemgrepProvider
def test_timeout_maps_to_structured_failure() -> None:
    provider = SemgrepProvider()
    failure = provider.execution_failure(
        ProviderExecutionResult(
            exit_code=-1,
            report_path=None,
            stdout="",
            stderr="",
            timed_out=True,
        ),
        required=True,
        provider_version="1.100.0",
    )
    assert failure is not None
    assert failure.failure_type is ProviderFailureType.TIMEOUT
    assert failure.fatal
def test_output_limit_maps_to_structured_failure(
    tmp_path: Path,
) -> None:
    provider = SemgrepProvider()
    failure = provider.execution_failure(
        ProviderExecutionResult(
            exit_code=1,
            report_path=tmp_path / "results.json",
            stdout="",
            stderr="",
            output_limit_exceeded=True,
        ),
        required=False,
        provider_version="1.100.0",
    )
    assert failure is not None
    assert (
        failure.failure_type
        is ProviderFailureType.OUTPUT_LIMIT_EXCEEDED
    )
    assert not failure.fatal

⸻

Fixture closure

The representative fixture must not be silently relabeled as captured.

Add an actual captured fixture:

tests/fixtures/semgrep/results.captured.json

Update provenance:

schema: l9.fixture-provenance/v1
fixture: results.captured.json
provider_id: semgrep
verification_status: runtime_captured_and_redacted
provider:
  version: "<ACTUAL SEMGREP VERSION>"
capture:
  timestamp: "<UTC TIMESTAMP>"
  command:
    - semgrep
    - scan
    - --config
    - tests/fixtures/semgrep/rules.yaml
    - --json-output
    - tests/fixtures/semgrep/results.raw.json
    - tests/fixtures/semgrep/source
checksums:
  fixture_input_sha256: "<SHA256>"
  raw_output_sha256: "<SHA256>"
  redacted_output_sha256: "<SHA256>"
redaction:
  reviewed_by: "<REVIEWER>"
  removed:
    - repository-specific absolute paths
    - source snippets beyond minimal fixture content
    - environment-specific values
preserved:
  - JSON structure
  - provider rule IDs
  - severity
  - locations
  - error structure

This file cannot be truthfully completed until a real invocation occurs.

Until then:

Semgrep:
  current_state: experimental

must remain unchanged.

⸻

Schema inventory update

Add to EXPECTED_SCHEMAS:

"gate-result.schema.json",
"repository-snapshot.schema.json",

If changing the projection protocol string, update:

"agent-review-payload.schema.json",

without necessarily renaming the file in v1.

⸻

Public API test update

Add these public surfaces:

from l9_ci import (
    capabilities,
    cli,
    execution,
    gates,
    repository,
)

Test exported names:

assert {
    "RepositorySnapshot",
    "build_repository_snapshot",
}.issubset(repository.__all__)
assert {
    "RepositoryCapabilities",
    "detect_repository_capabilities",
}.issubset(capabilities.__all__)
assert {
    "ExecutionProfile",
    "ExecutionProfileName",
    "select_providers",
}.issubset(execution.__all__)
assert {
    "GateResult",
    "GateStatus",
    "evaluate_gate",
}.issubset(gates.__all__)
assert {
    "Diagnostic",
    "ExitCode",
    "OutputFormat",
}.issubset(cli.__all__)

⸻

Root command registration

Update the existing root CLI:

from l9_ci.commands import (
    register_artifact_commands,
    register_gate_commands,
    register_integration_commands,
    register_provider_commands,
    register_semgrep_commands,
)
register_artifact_commands(subparsers)
register_gate_commands(subparsers)
register_integration_commands(subparsers)
register_provider_commands(subparsers)
register_semgrep_commands(subparsers)

Update l9_ci/commands/__init__.py accordingly.

⸻

Final CLI surface

l9-ci providers list
l9-ci providers detect --root .
l9-ci semgrep detect
l9-ci semgrep normalize ...
l9-ci bundle validate BUNDLE
l9-ci bundle project-agent-payload ...
l9-ci compatibility check ...
l9-ci gate evaluate \
  --bundle artifacts/l9/finding-bundle.json \
  --output artifacts/l9/gate-result.json

Exit behavior:

0  pass / successful command
1  blocking finding gate failure
2  invalid arguments
3  provider execution failure
4  provider report failure
5  artifact validation or invalid gate input
6  incomplete or unresolved strict contract
7  internal error
8  incompatible version
9  operational limit exceeded

⸻

Repository hygiene

Delete:

.ruff_cache/

Add to .gitignore:

.ruff_cache/
.pytest_cache/
.mypy_cache/
__pycache__/
*.py[cod]
artifacts/

Do not ignore checked-in compatibility fixtures.

⸻

Roadmap closure

Replace .l9/roadmap.yaml Phase 2 entry with:

  - id: P2
    title: Integration and release readiness
    status: complete
    acceptance:
      - stable Core-facing CLI exists
      - version negotiation exists
      - canonical bundle validation exists
      - agent projection exists
      - operational limits exist
      - compatibility fixtures exist
      - release documentation exists
  - id: P3
    title: Spec closure
    status: current
    deliverables:
      - gate evaluation
      - repository snapshot derivation
      - capability detection
      - execution profiles
      - provider selection
      - centralized CLI contract
      - Semgrep version enforcement
      - bounded execution failure mapping
      - raw summary validation
      - architecture-layer enforcement
      - runtime fixture provenance
    acceptance:
      - missing required evidence cannot pass
      - snapshot identity can be SDK-derived
      - provider candidates can be detected
      - generic providers list and detect commands exist
      - exit codes have one source of truth
      - unsupported Semgrep versions fail explicitly
      - timeout and output limits produce structured failures
      - malformed raw summary is rejected
      - architecture tests cover every public SDK layer
      - repository caches are not committed

Keep the next phase as:

  - id: P4
    title: Semgrep shadow rollout
    status: blocked
    blockers:
      - runtime-captured fixture required
      - live Core integration required

⸻

Validation sequence

python -m compileall l9_ci
ruff check .
ruff format --check .
python -m pytest \
  tests/architecture \
  tests/contracts \
  tests/repository \
  tests/capabilities \
  tests/execution \
  tests/identity \
  tests/policy \
  tests/providers/semgrep \
  tests/gates \
  tests/integration \
  tests/compatibility \
  tests/cli \
  tests/pipeline

Manual CLI validation:

l9-ci providers list --format json
l9-ci providers detect \
  --root . \
  --format json
l9-ci semgrep normalize \
  --input tests/fixtures/semgrep/results.captured.json \
  --output artifacts/l9/finding-bundle.json \
  --root . \
  --derive-snapshot \
  --provider-version "$(semgrep --version)" \
  --identity-map .l9/semgrep-identity-map.yaml \
  --policy .l9/semgrep-policy.example.yaml
l9-ci bundle validate \
  artifacts/l9/finding-bundle.json
l9-ci gate evaluate \
  --bundle artifacts/l9/finding-bundle.json \
  --output artifacts/l9/gate-result.json
l9-ci bundle project-agent-payload \
  --input artifacts/l9/finding-bundle.json \
  --output artifacts/l9/agent-review-payload.json

⸻

Phase 4 completion gates

1. Gate evaluation exists as a dedicated SDK stage.
2. Gate evaluation consumes classifications, failures, and coverage.
3. Missing required evidence never produces PASS.
4. Git-aware repository enumeration exists.
5. Deterministic snapshot derivation exists.
6. Filesystem fallback snapshots exist.
7. Repository capability detection exists.
8. Generic provider list and detect commands exist.
9. Execution profiles exist.
10. Provider selection is deterministic.
11. CLI exit codes have one source of truth.
12. CLI supports machine-readable output.
13. Semgrep version compatibility is explicit.
14. Timeout maps to a structured provider failure.
15. Output limit maps to a structured provider failure.
16. Missing reports map to a structured provider failure.
17. Raw bundle summaries are validated before deserialization.
18. Agent output is explicitly non-canonical.
19. Architecture rules cover every implemented SDK layer.
20. Architecture dependency tests reflect those layers.
21. Cache files are removed from the repository.
22. Runtime Semgrep fixture provenance is complete.
23. Full test suite passes.
24. No second provider is added.
25. No Core workflow is modified.

After this phase, the narrow SDK specification is structurally complete.

The only remaining blockers before a Semgrep shadow release are empirical rather than architectural:

runtime-captured fixture
        ↓
verified Semgrep version range
        ↓
live Core invocation
        ↓
shadow telemetry