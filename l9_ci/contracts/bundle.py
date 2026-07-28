"""Canonical finding-bundle contracts."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from .classification import FindingClassification
from .coverage import Coverage
from .evidence import EvidenceRecord
from .failure import ProviderFailure
from .finding import Finding

FINDING_BUNDLE_PROTOCOL = "l9.finding-bundle/v1"
FINDING_BUNDLE_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class SnapshotDescriptor:
    """Identity of the repository state analyzed by the SDK."""

    snapshot_id: str
    repository_root: str
    revision: str | None = None
    dirty: bool | None = None

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip():
            raise ValueError("snapshot_id must be non-empty")
        if not self.repository_root.strip():
            raise ValueError("repository_root must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "snapshot_id": self.snapshot_id,
            "repository_root": self.repository_root,
        }
        if self.revision is not None:
            payload["revision"] = self.revision
        if self.dirty is not None:
            payload["dirty"] = self.dirty
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SnapshotDescriptor":
        return cls(
            snapshot_id=str(payload["snapshot_id"]),
            repository_root=str(payload["repository_root"]),
            revision=payload.get("revision"),
            dirty=payload.get("dirty"),
        )


@dataclass(frozen=True, slots=True)
class ProviderRun:
    """Metadata for a requested provider execution or import."""

    provider_id: str
    adapter_version: str
    provider_version: str | None
    mode: str
    required: bool

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must be non-empty")
        if not self.adapter_version.strip():
            raise ValueError("adapter_version must be non-empty")
        if self.mode not in {"execute", "import"}:
            raise ValueError("mode must be execute or import")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "provider_id": self.provider_id,
            "adapter_version": self.adapter_version,
            "mode": self.mode,
            "required": self.required,
        }
        if self.provider_version is not None:
            payload["provider_version"] = self.provider_version
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ProviderRun":
        return cls(
            provider_id=str(payload["provider_id"]),
            adapter_version=str(payload["adapter_version"]),
            provider_version=payload.get("provider_version"),
            mode=str(payload["mode"]),
            required=bool(payload["required"]),
        )


@dataclass(frozen=True, slots=True)
class FindingBundle:
    """Versioned, validated SDK output bundle."""

    SDK_version: str
    snapshot: SnapshotDescriptor
    providers: tuple[ProviderRun, ...]
    evidence: tuple[EvidenceRecord, ...]
    findings: tuple[Finding, ...]
    classifications: tuple[FindingClassification, ...]
    provider_failures: tuple[ProviderFailure, ...]
    coverage: tuple[Coverage, ...]
    limitations: tuple[str, ...] = ()
    generated_at: str = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    )
    schema: str = FINDING_BUNDLE_PROTOCOL
    schema_version: str = FINDING_BUNDLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.SDK_version.strip():
            raise ValueError("SDK_version must be non-empty")
        for field_name in (
            "providers",
            "evidence",
            "findings",
            "classifications",
            "provider_failures",
            "coverage",
            "limitations",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))

    def summary(self) -> dict[str, int]:
        return {
            "provider_count": len(self.providers),
            "evidence_count": len(self.evidence),
            "finding_count": len(self.findings),
            "classification_count": len(self.classifications),
            "provider_failure_count": len(self.provider_failures),
            "coverage_count": len(self.coverage),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "SDK_version": self.SDK_version,
            "generated_at": self.generated_at,
            "snapshot": self.snapshot.to_dict(),
            "providers": [item.to_dict() for item in self.providers],
            "evidence": [item.to_dict() for item in self.evidence],
            "findings": [item.to_dict() for item in self.findings],
            "classifications": [item.to_dict() for item in self.classifications],
            "provider_failures": [item.to_dict() for item in self.provider_failures],
            "coverage": [item.to_dict() for item in self.coverage],
            "limitations": list(self.limitations),
            "summary": self.summary(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FindingBundle":
        return cls(
            schema=str(payload["schema"]),
            schema_version=str(payload["schema_version"]),
            SDK_version=str(payload["SDK_version"]),
            generated_at=str(payload["generated_at"]),
            snapshot=SnapshotDescriptor.from_dict(payload["snapshot"]),
            providers=tuple(
                ProviderRun.from_dict(item) for item in payload.get("providers", [])
            ),
            evidence=tuple(
                EvidenceRecord.from_dict(item) for item in payload.get("evidence", [])
            ),
            findings=tuple(
                Finding.from_dict(item) for item in payload.get("findings", [])
            ),
            classifications=tuple(
                FindingClassification.from_dict(item)
                for item in payload.get("classifications", [])
            ),
            provider_failures=tuple(
                ProviderFailure.from_dict(item)
                for item in payload.get("provider_failures", [])
            ),
            coverage=tuple(
                Coverage.from_dict(item) for item in payload.get("coverage", [])
            ),
            limitations=tuple(str(item) for item in payload.get("limitations", [])),
        )
