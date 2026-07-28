"""Finding policy classification contracts."""

from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class RuleMode(StrEnum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"
    SHADOW = "shadow"
    DISABLED = "disabled"
    UNRESOLVED = "unresolved"


class ResolutionStatus(StrEnum):
    EXPLICIT = "explicit"
    DEFAULTED = "defaulted"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class FindingClassification:
    """Policy classification attached to a canonical finding."""

    finding_id: str
    mode: RuleMode
    resolution_status: ResolutionStatus
    used_default: bool
    policy_key: str | None = None
    policy_version: str | None = None
    waiver_id: str | None = None

    def __post_init__(self) -> None:
        if not self.finding_id.strip():
            raise ValueError("finding_id must be non-empty")
        if self.resolution_status is ResolutionStatus.EXPLICIT and not self.policy_key:
            raise ValueError("explicit classifications require policy_key")
        if self.mode is RuleMode.UNRESOLVED:
            if self.resolution_status is not ResolutionStatus.UNRESOLVED:
                raise ValueError(
                    "unresolved mode requires unresolved resolution_status"
                )
        if self.resolution_status is ResolutionStatus.UNRESOLVED:
            if self.mode is not RuleMode.UNRESOLVED:
                raise ValueError(
                    "unresolved resolution_status requires unresolved mode"
                )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "finding_id": self.finding_id,
            "mode": self.mode.value,
            "resolution_status": self.resolution_status.value,
            "used_default": self.used_default,
        }
        for key in ("policy_key", "policy_version", "waiver_id"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FindingClassification":
        return cls(
            finding_id=str(payload["finding_id"]),
            mode=RuleMode(str(payload["mode"])),
            resolution_status=ResolutionStatus(str(payload["resolution_status"])),
            used_default=bool(payload["used_default"]),
            policy_key=payload.get("policy_key"),
            policy_version=payload.get("policy_version"),
            waiver_id=payload.get("waiver_id"),
        )
