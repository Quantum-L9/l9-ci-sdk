"""Canonical gate evaluation contracts."""

from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

GATE_RESULT_PROTOCOL = "l9.gate-result/v1"
GATE_RESULT_SCHEMA_VERSION = "1.1.0"


class GateStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"


class ReasonCode(StrEnum):
    """Why a gate is not PASS; each code's subjects are named in ADR 0025."""

    MISSING_CLASSIFICATIONS = "missing_classifications"
    REQUIRED_PROVIDER_FAILED = "required_provider_failed"
    REQUIRED_PROVIDER_NONFATAL_FAILURE = "required_provider_nonfatal_failure"
    REQUIRED_COVERAGE_INCOMPLETE = "required_coverage_incomplete"
    BLOCKING_FINDINGS = "blocking_findings"
    UNRESOLVED_FINDINGS = "unresolved_findings"


@dataclass(frozen=True, slots=True)
class ReasonDetail:
    """One gate reason in machine form: its code and the subjects it names.

    ``subjects`` holds at most ``SUBJECT_CAP`` sorted entries; ``omitted``
    counts the rest. A detail always names at least one subject.
    """

    code: ReasonCode
    subjects: tuple[str, ...]
    omitted: int = 0

    def __post_init__(self) -> None:
        if not self.subjects:
            raise ValueError(f"reason {self.code.value} must name a subject")
        if self.omitted < 0:
            raise ValueError("omitted must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "subjects": list(self.subjects),
            "omitted": self.omitted,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReasonDetail":
        return cls(
            code=ReasonCode(str(payload["code"])),
            subjects=tuple(str(item) for item in payload["subjects"]),
            omitted=int(payload.get("omitted", 0)),
        )


@dataclass(frozen=True, slots=True)
class GateResult:
    """Result of evaluating a canonical finding bundle."""

    status: GateStatus
    blocking_finding_ids: tuple[str, ...]
    unresolved_finding_ids: tuple[str, ...]
    fatal_provider_ids: tuple[str, ...]
    incomplete_provider_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    reason_details: tuple[ReasonDetail, ...] = ()
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
        object.__setattr__(
            self,
            "reason_details",
            tuple(sorted(self.reason_details, key=lambda item: item.code.value)),
        )

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
            "reason_details": [item.to_dict() for item in self.reason_details],
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
            reason_details=tuple(
                ReasonDetail.from_dict(item)
                for item in payload.get("reason_details", [])
            ),
            schema=str(payload.get("schema", GATE_RESULT_PROTOCOL)),
            schema_version=str(
                payload.get(
                    "schema_version",
                    GATE_RESULT_SCHEMA_VERSION,
                )
            ),
        )
