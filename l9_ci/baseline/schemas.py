"""Versioned baseline-ratchet ledger contracts.

Every accepted debt entry is an explicit, owned, expiring exception.
The schema is fail-closed: entries missing any required field are
rejected at construction time, and ledgers containing malformed
entries are rejected at load time.

No LLM participates in validation, normalization, or comparison.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Mapping

from l9_ci.contracts.source import normalize_repository_path

BASELINE_SCHEMA_VERSION = "1.0.0"
BASELINE_PROTOCOL = "l9-ci/baseline"

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]{2,127}$")
_ISSUE_PATTERN = re.compile(
    r"^(https://github\.com/[\w.-]+/[\w.-]+/issues/\d+|[\w.-]+/[\w.-]+#\d+|#\d+)$"
)
_OWNER_PATTERN = re.compile(r"^@?[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(/[\w.-]+)?$")
_FINGERPRINT_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_PLACEHOLDER_TOKENS = frozenset(
    {
        "tbd",
        "todo",
        "fixme",
        "placeholder",
        "unknown",
        "n/a",
        "na",
        "none",
        "xxx",
        "changeme",
        "@tbd",
        "@todo",
        "@owner",
        "@someone",
    }
)

#: Machine-evaluable removal-condition kinds.
#:
#: - ``finding-absent``: entry is removable when the fingerprint no longer
#:   appears in a fresh scan (evaluated automatically by the comparator).
#: - ``test-passes``: entry is removable when the quarantined test node
#:   passes in a fresh run (evaluated automatically by the comparator).
#: - ``migrated-to``: entry is removable when the referenced symbol is
#:   migrated (evaluated as finding-absent plus a documented target).
REMOVAL_CONDITION_KINDS = frozenset({"finding-absent", "test-passes", "migrated-to"})


def _require_non_empty(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _reject_placeholder(name: str, value: str) -> str:
    if value.strip().lower() in _PLACEHOLDER_TOKENS:
        raise ValueError(f"{name} must not be a placeholder value: {value!r}")
    return value


def _parse_iso_date(name: str, value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(
                f"{name} must be an ISO date (YYYY-MM-DD): {value!r}"
            ) from exc
    raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD)")


def validate_owner(owner: Any) -> str:
    """Validate a GitHub owner handle or team slug."""
    value = _require_non_empty("owner", owner)
    _reject_placeholder("owner", value)
    if not _OWNER_PATTERN.match(value):
        raise ValueError(f"owner must be a GitHub handle or org/team slug: {value!r}")
    return value


def validate_issue(issue: Any) -> str:
    """Validate a GitHub issue reference (URL, owner/repo#N, or #N)."""
    value = _require_non_empty("issue", issue)
    _reject_placeholder("issue", value)
    if not _ISSUE_PATTERN.match(value):
        raise ValueError(
            "issue must be a GitHub issue URL, owner/repo#N, or #N reference: "
            f"{value!r}"
        )
    return value


@dataclass(frozen=True, slots=True)
class RemovalCondition:
    """A machine-evaluable condition under which a debt entry is removed."""

    kind: str
    target: str | None = None

    def __post_init__(self) -> None:
        kind = _require_non_empty("removal_condition.kind", self.kind)
        if kind not in REMOVAL_CONDITION_KINDS:
            raise ValueError(
                "removal_condition.kind must be one of "
                f"{sorted(REMOVAL_CONDITION_KINDS)}: {kind!r}"
            )
        object.__setattr__(self, "kind", kind)
        if kind == "migrated-to":
            target = _require_non_empty("removal_condition.target", self.target)
            _reject_placeholder("removal_condition.target", target)
            object.__setattr__(self, "target", target)
        elif self.target is not None:
            target = _require_non_empty("removal_condition.target", self.target)
            object.__setattr__(self, "target", target)

    @classmethod
    def from_value(cls, value: Any) -> "RemovalCondition":
        if isinstance(value, RemovalCondition):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if ":" in raw:
                kind, _, target = raw.partition(":")
                return cls(kind=kind.strip(), target=target.strip() or None)
            return cls(kind=raw)
        if isinstance(value, Mapping):
            return cls(kind=value.get("kind", ""), target=value.get("target"))
        raise ValueError("removal_condition must be a string or mapping")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind}
        if self.target is not None:
            payload["target"] = self.target
        return payload


@dataclass(frozen=True, slots=True)
class BaselineEntry:
    """A single tolerated scanner finding, fully owned and expiring."""

    id: str
    gate: str
    rule: str
    fingerprint: str
    path: str
    owner: str
    issue: str
    introduced_before: str
    expires: date
    removal_condition: RemovalCondition
    root_cause_group: str | None = None
    evidence: str | None = None
    last_verified_commit: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        entry_id = _require_non_empty("id", self.id)
        if not _ID_PATTERN.match(entry_id):
            raise ValueError(f"id must match {_ID_PATTERN.pattern}: {entry_id!r}")
        object.__setattr__(self, "id", entry_id)
        object.__setattr__(self, "gate", _require_non_empty("gate", self.gate))
        object.__setattr__(self, "rule", _require_non_empty("rule", self.rule))
        fingerprint = _require_non_empty("fingerprint", self.fingerprint)
        if not _FINGERPRINT_PATTERN.match(fingerprint):
            raise ValueError("fingerprint must be a 64-char lowercase hex SHA-256")
        object.__setattr__(self, "fingerprint", fingerprint)
        object.__setattr__(
            self,
            "path",
            normalize_repository_path(_require_non_empty("path", self.path)),
        )
        object.__setattr__(self, "owner", validate_owner(self.owner))
        object.__setattr__(self, "issue", validate_issue(self.issue))
        object.__setattr__(
            self,
            "introduced_before",
            _require_non_empty("introduced_before", self.introduced_before),
        )
        object.__setattr__(self, "expires", _parse_iso_date("expires", self.expires))
        object.__setattr__(
            self,
            "removal_condition",
            RemovalCondition.from_value(self.removal_condition),
        )

    def is_expired(self, today: date) -> bool:
        return today > self.expires

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "gate": self.gate,
            "rule": self.rule,
            "fingerprint": self.fingerprint,
            "path": self.path,
            "owner": self.owner,
            "issue": self.issue,
            "introduced_before": self.introduced_before,
            "expires": self.expires.isoformat(),
            "removal_condition": self.removal_condition.to_dict(),
        }
        if self.root_cause_group is not None:
            payload["root_cause_group"] = self.root_cause_group
        if self.evidence is not None:
            payload["evidence"] = self.evidence
        if self.last_verified_commit is not None:
            payload["last_verified_commit"] = self.last_verified_commit
        if self.attributes:
            payload["attributes"] = dict(self.attributes)
        return payload


@dataclass(frozen=True, slots=True)
class TestQuarantineEntry:
    """A single quarantined failing test node, fully owned and expiring."""

    id: str
    test_node_id: str
    fingerprint: str
    exception_type: str
    failure_signature: str
    owner: str
    issue: str
    introduced_before: str
    expires: date
    removal_condition: RemovalCondition
    root_cause_group: str | None = None
    evidence: str | None = None
    last_verified_commit: str | None = None

    def __post_init__(self) -> None:
        entry_id = _require_non_empty("id", self.id)
        if not _ID_PATTERN.match(entry_id):
            raise ValueError(f"id must match {_ID_PATTERN.pattern}: {entry_id!r}")
        object.__setattr__(self, "id", entry_id)
        object.__setattr__(
            self, "test_node_id", _require_non_empty("test_node_id", self.test_node_id)
        )
        fingerprint = _require_non_empty("fingerprint", self.fingerprint)
        if not _FINGERPRINT_PATTERN.match(fingerprint):
            raise ValueError("fingerprint must be a 64-char lowercase hex SHA-256")
        object.__setattr__(self, "fingerprint", fingerprint)
        object.__setattr__(
            self,
            "exception_type",
            _require_non_empty("exception_type", self.exception_type),
        )
        object.__setattr__(
            self,
            "failure_signature",
            _require_non_empty("failure_signature", self.failure_signature),
        )
        object.__setattr__(self, "owner", validate_owner(self.owner))
        object.__setattr__(self, "issue", validate_issue(self.issue))
        object.__setattr__(
            self,
            "introduced_before",
            _require_non_empty("introduced_before", self.introduced_before),
        )
        object.__setattr__(self, "expires", _parse_iso_date("expires", self.expires))
        object.__setattr__(
            self,
            "removal_condition",
            RemovalCondition.from_value(self.removal_condition),
        )

    def is_expired(self, today: date) -> bool:
        return today > self.expires

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "test_node_id": self.test_node_id,
            "fingerprint": self.fingerprint,
            "exception_type": self.exception_type,
            "failure_signature": self.failure_signature,
            "owner": self.owner,
            "issue": self.issue,
            "introduced_before": self.introduced_before,
            "expires": self.expires.isoformat(),
            "removal_condition": self.removal_condition.to_dict(),
        }
        if self.root_cause_group is not None:
            payload["root_cause_group"] = self.root_cause_group
        if self.evidence is not None:
            payload["evidence"] = self.evidence
        if self.last_verified_commit is not None:
            payload["last_verified_commit"] = self.last_verified_commit
        return payload


@dataclass(frozen=True, slots=True)
class RuleWaiverEntry:
    """A narrowly scoped waiver for one rule on one path, owned and expiring.

    A waiver never waives a whole gate; it waives one rule on one
    repository-relative path. Aggregate waivers are rejected by design.
    """

    id: str
    gate: str
    rule: str
    path: str
    owner: str
    issue: str
    expires: date
    reason: str
    removal_condition: RemovalCondition

    def __post_init__(self) -> None:
        entry_id = _require_non_empty("id", self.id)
        if not _ID_PATTERN.match(entry_id):
            raise ValueError(f"id must match {_ID_PATTERN.pattern}: {entry_id!r}")
        object.__setattr__(self, "id", entry_id)
        object.__setattr__(self, "gate", _require_non_empty("gate", self.gate))
        rule = _require_non_empty("rule", self.rule)
        if rule in {"*", "all", "ALL"}:
            raise ValueError("rule waivers must target a single rule, not a wildcard")
        object.__setattr__(self, "rule", rule)
        path = _require_non_empty("path", self.path)
        if path in {"*", "**", "."}:
            raise ValueError("rule waivers must target a single path, not a wildcard")
        object.__setattr__(self, "path", normalize_repository_path(path))
        object.__setattr__(self, "owner", validate_owner(self.owner))
        object.__setattr__(self, "issue", validate_issue(self.issue))
        object.__setattr__(self, "expires", _parse_iso_date("expires", self.expires))
        object.__setattr__(self, "reason", _require_non_empty("reason", self.reason))
        object.__setattr__(
            self,
            "removal_condition",
            RemovalCondition.from_value(self.removal_condition),
        )

    def is_expired(self, today: date) -> bool:
        return today > self.expires

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "gate": self.gate,
            "rule": self.rule,
            "path": self.path,
            "owner": self.owner,
            "issue": self.issue,
            "expires": self.expires.isoformat(),
            "reason": self.reason,
            "removal_condition": self.removal_condition.to_dict(),
        }


def utc_today() -> date:
    """Deterministic 'today' anchor in UTC for expiry evaluation."""
    return datetime.now(timezone.utc).date()
