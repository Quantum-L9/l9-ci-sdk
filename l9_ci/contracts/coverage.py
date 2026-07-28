"""Provider coverage contracts."""

from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class CoverageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Coverage:
    """Coverage and limitation information for one provider run."""

    provider_id: str
    status: CoverageStatus
    files_considered: int
    files_analyzed: int
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must be non-empty")
        if self.files_considered < 0:
            raise ValueError("files_considered must be non-negative")
        if self.files_analyzed < 0:
            raise ValueError("files_analyzed must be non-negative")
        if self.files_analyzed > self.files_considered:
            raise ValueError("files_analyzed must not exceed files_considered")
        object.__setattr__(self, "limitations", tuple(self.limitations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "status": self.status.value,
            "files_considered": self.files_considered,
            "files_analyzed": self.files_analyzed,
            "limitations": list(self.limitations),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Coverage":
        return cls(
            provider_id=str(payload["provider_id"]),
            status=CoverageStatus(str(payload["status"])),
            files_considered=int(payload["files_considered"]),
            files_analyzed=int(payload["files_analyzed"]),
            limitations=tuple(str(item) for item in payload.get("limitations", [])),
        )
