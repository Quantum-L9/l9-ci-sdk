"""Baseline comparison contracts and outcome model.

The comparator consumes observed findings plus a ledger and produces a
deterministic set of violations. It is pure: same inputs always produce
the same outputs. No network, no LLM, no clock other than the injected
evaluation date.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Mapping, Sequence

COMPARISON_SCHEMA_VERSION = "1.0.0"


class ViolationKind(str, Enum):
    """All blocking outcomes of a baseline comparison."""

    NEW_FINDING = "new-finding"
    INCREASED_FINDING = "increased-finding"
    CHANGED_SIGNATURE = "changed-signature"
    EXPIRED_EXCEPTION = "expired-exception"
    MISSING_OWNER = "missing-owner"
    MISSING_ISSUE = "missing-issue"
    STALE_ENTRY = "stale-entry"
    RESOLVED_NOT_REMOVED = "resolved-not-removed"
    MALFORMED_BASELINE = "malformed-baseline"


class FindingStatus(str, Enum):
    """Per-observation classification."""

    KNOWN = "known"
    NEW = "new"
    CHANGED = "changed"


@dataclass(frozen=True, slots=True)
class ObservedFinding:
    """A single observed finding from a fresh scanner or test run."""

    gate: str
    rule: str
    fingerprint: str
    path: str
    identity: str
    message: str = ""
    exception_type: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("gate", "rule", "fingerprint", "path", "identity"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"observed finding {name} must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "gate": self.gate,
            "rule": self.rule,
            "fingerprint": self.fingerprint,
            "path": self.path,
            "identity": self.identity,
            "message": self.message,
        }
        if self.exception_type is not None:
            payload["exception_type"] = self.exception_type
        if self.attributes:
            payload["attributes"] = dict(self.attributes)
        return payload


@dataclass(frozen=True, slots=True)
class BaselineViolation:
    """A single blocking violation discovered during comparison."""

    kind: ViolationKind
    gate: str
    rule: str
    identity: str
    detail: str
    fingerprint: str | None = None
    entry_id: str | None = None
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind.value,
            "gate": self.gate,
            "rule": self.rule,
            "identity": self.identity,
            "detail": self.detail,
        }
        if self.fingerprint is not None:
            payload["fingerprint"] = self.fingerprint
        if self.entry_id is not None:
            payload["entry_id"] = self.entry_id
        if self.path is not None:
            payload["path"] = self.path
        return payload


@dataclass(frozen=True, slots=True)
class BaselineSummary:
    """Aggregate counts for a comparison run."""

    observed_total: int
    known_total: int
    new_total: int
    changed_total: int
    resolved_total: int
    expired_total: int
    malformed_total: int
    violations_total: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_total": self.observed_total,
            "known_total": self.known_total,
            "new_total": self.new_total,
            "changed_total": self.changed_total,
            "resolved_total": self.resolved_total,
            "expired_total": self.expired_total,
            "malformed_total": self.malformed_total,
            "violations_total": self.violations_total,
        }


@dataclass(frozen=True, slots=True)
class BaselineComparison:
    """The full deterministic result of comparing observations to a ledger."""

    schema_version: str
    gate: str
    evaluated_on: date
    passed: bool
    summary: BaselineSummary
    violations: tuple[BaselineViolation, ...]
    known: tuple[ObservedFinding, ...]
    new: tuple[ObservedFinding, ...]
    resolved_entry_ids: tuple[str, ...]
    suggested_removals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "gate": self.gate,
            "evaluated_on": self.evaluated_on.isoformat(),
            "passed": self.passed,
            "summary": self.summary.to_dict(),
            "violations": [violation.to_dict() for violation in self.violations],
            "known": [finding.to_dict() for finding in self.known],
            "new": [finding.to_dict() for finding in self.new],
            "resolved_entry_ids": list(self.resolved_entry_ids),
            "suggested_removals": list(self.suggested_removals),
        }


def sort_violations(
    violations: Sequence[BaselineViolation],
) -> tuple[BaselineViolation, ...]:
    """Deterministic ordering: kind, gate, rule, identity."""
    return tuple(
        sorted(
            violations,
            key=lambda violation: (
                violation.kind.value,
                violation.gate,
                violation.rule,
                violation.identity,
            ),
        )
    )
