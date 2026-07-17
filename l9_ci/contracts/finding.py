"""Canonical finding contracts."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from .evidence import Confidence, Severity
from .source import SourceLocation


@dataclass(frozen=True, slots=True)
class Finding:
    """A normalized issue derived from one or more evidence records."""

    finding_id: str
    snapshot_id: str
    provider_id: str
    provider_rule_id: str
    category: str
    message: str
    evidence_ids: tuple[str, ...]
    locations: tuple[SourceLocation, ...]
    fingerprint: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    canonical_rule_id: str | None = None
    severity: Severity | None = None
    confidence: Confidence | None = None
    remediation_class: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "finding_id",
            "snapshot_id",
            "provider_id",
            "provider_rule_id",
            "category",
            "message",
            "fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        evidence_ids = tuple(self.evidence_ids)
        if not evidence_ids:
            raise ValueError("finding must reference at least one evidence record")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("finding evidence references must be unique")
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "locations", tuple(self.locations))
        object.__setattr__(self, "limitations", tuple(self.limitations))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "finding_id": self.finding_id,
            "snapshot_id": self.snapshot_id,
            "provider_id": self.provider_id,
            "provider_rule_id": self.provider_rule_id,
            "category": self.category,
            "message": self.message,
            "evidence_ids": list(self.evidence_ids),
            "locations": [location.to_dict() for location in self.locations],
            "fingerprint": self.fingerprint,
            "attributes": dict(self.attributes),
            "limitations": list(self.limitations),
        }
        optional_values = {
            "canonical_rule_id": self.canonical_rule_id,
            "severity": self.severity.value if self.severity else None,
            "confidence": self.confidence.value if self.confidence else None,
            "remediation_class": self.remediation_class,
        }
        for key, value in optional_values.items():
            if value is not None:
                payload[key] = value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Finding":
        locations_raw: Sequence[Mapping[str, Any]] = payload.get("locations", [])
        severity_raw = payload.get("severity")
        confidence_raw = payload.get("confidence")
        return cls(
            finding_id=str(payload["finding_id"]),
            snapshot_id=str(payload["snapshot_id"]),
            provider_id=str(payload["provider_id"]),
            provider_rule_id=str(payload["provider_rule_id"]),
            category=str(payload["category"]),
            message=str(payload["message"]),
            evidence_ids=tuple(str(item) for item in payload["evidence_ids"]),
            locations=tuple(
                SourceLocation.from_dict(dict(item)) for item in locations_raw
            ),
            fingerprint=str(payload["fingerprint"]),
            attributes=dict(payload.get("attributes", {})),
            limitations=tuple(str(item) for item in payload.get("limitations", [])),
            canonical_rule_id=payload.get("canonical_rule_id"),
            severity=Severity(severity_raw) if severity_raw else None,
            confidence=Confidence(confidence_raw) if confidence_raw else None,
            remediation_class=payload.get("remediation_class"),
        )
