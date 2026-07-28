"""Canonical evidence contracts."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence
from .source import SourceLocation


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """A provider-derived factual observation.
    Evidence records contain provider facts only. They do not contain policy
    modes, gate decisions, or workflow outcomes.
    """

    evidence_id: str
    snapshot_id: str
    provider_id: str
    provider_rule_id: str
    evidence_type: str
    message: str
    locations: tuple[SourceLocation, ...]
    attributes: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    provider_version: str | None = None
    canonical_rule_id: str | None = None
    severity: Severity | None = None
    confidence: Confidence | None = None
    provider_fingerprint: str | None = None
    identifiers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_id",
            "snapshot_id",
            "provider_id",
            "provider_rule_id",
            "evidence_type",
            "message",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if not isinstance(self.locations, tuple):
            object.__setattr__(self, "locations", tuple(self.locations))
        if not isinstance(self.limitations, tuple):
            object.__setattr__(self, "limitations", tuple(self.limitations))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "snapshot_id": self.snapshot_id,
            "provider_id": self.provider_id,
            "provider_rule_id": self.provider_rule_id,
            "evidence_type": self.evidence_type,
            "message": self.message,
            "locations": [location.to_dict() for location in self.locations],
            "attributes": dict(self.attributes),
            "limitations": list(self.limitations),
            "identifiers": dict(self.identifiers),
        }
        optional_values = {
            "provider_version": self.provider_version,
            "canonical_rule_id": self.canonical_rule_id,
            "severity": self.severity.value if self.severity else None,
            "confidence": self.confidence.value if self.confidence else None,
            "provider_fingerprint": self.provider_fingerprint,
        }
        for key, value in optional_values.items():
            if value is not None:
                payload[key] = value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceRecord":
        locations_raw: Sequence[Mapping[str, Any]] = payload.get("locations", [])
        severity_raw = payload.get("severity")
        confidence_raw = payload.get("confidence")
        return cls(
            evidence_id=str(payload["evidence_id"]),
            snapshot_id=str(payload["snapshot_id"]),
            provider_id=str(payload["provider_id"]),
            provider_rule_id=str(payload["provider_rule_id"]),
            evidence_type=str(payload["evidence_type"]),
            message=str(payload["message"]),
            locations=tuple(
                SourceLocation.from_dict(dict(item)) for item in locations_raw
            ),
            attributes=dict(payload.get("attributes", {})),
            limitations=tuple(str(item) for item in payload.get("limitations", [])),
            provider_version=payload.get("provider_version"),
            canonical_rule_id=payload.get("canonical_rule_id"),
            severity=Severity(severity_raw) if severity_raw else None,
            confidence=Confidence(confidence_raw) if confidence_raw else None,
            provider_fingerprint=payload.get("provider_fingerprint"),
            identifiers={
                str(key): str(value)
                for key, value in dict(payload.get("identifiers", {})).items()
            },
        )
