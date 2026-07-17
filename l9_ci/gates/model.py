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
                "incomplete_provider_count": len(self.incomplete_provider_ids),
            },
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GateResult":
        return cls(
            status=GateStatus(str(payload["status"])),
            blocking_finding_ids=tuple(
                str(item) for item in payload.get("blocking_finding_ids", [])
            ),
            unresolved_finding_ids=tuple(
                str(item) for item in payload.get("unresolved_finding_ids", [])
            ),
            fatal_provider_ids=tuple(
                str(item) for item in payload.get("fatal_provider_ids", [])
            ),
            incomplete_provider_ids=tuple(
                str(item) for item in payload.get("incomplete_provider_ids", [])
            ),
            reasons=tuple(str(item) for item in payload.get("reasons", [])),
            schema=str(payload.get("schema", GATE_RESULT_PROTOCOL)),
            schema_version=str(
                payload.get(
                    "schema_version",
                    GATE_RESULT_SCHEMA_VERSION,
                )
            ),
        )
