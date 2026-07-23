"""Deterministic baseline comparator.

Implements the ratchet decision table:

==========================================  =========
Condition                                   Outcome
==========================================  =========
observed fingerprint in ledger, unexpired   tolerated
observed fingerprint not in ledger          FAIL new-finding
same identity, different fingerprint        FAIL changed-signature
identity seen more times than ledgered      FAIL increased-finding
ledger entry past expiry                    FAIL expired-exception
ledger entry missing/invalid owner          FAIL missing-owner (load-time)
ledger entry missing/invalid issue          FAIL missing-issue (load-time)
ledger entry duplicated / unparseable       FAIL malformed-baseline
quarantined test passes, entry remains      FAIL resolved-not-removed
scanner finding gone, entry remains         FAIL stale-entry
==========================================  =========

The comparator never mutates the ledger. CI must not write baseline
files; it may only publish the suggested-removal delta for a human PR.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Iterable, Mapping, Sequence

from .comparison import (
    COMPARISON_SCHEMA_VERSION,
    BaselineComparison,
    BaselineSummary,
    BaselineViolation,
    ObservedFinding,
    ViolationKind,
    sort_violations,
)
from .schemas import BaselineEntry, TestQuarantineEntry


def _entry_identity(entry: BaselineEntry | TestQuarantineEntry) -> str:
    if isinstance(entry, TestQuarantineEntry):
        return entry.test_node_id
    return f"{entry.rule}::{entry.path}"


def _entry_gate(entry: BaselineEntry | TestQuarantineEntry, default_gate: str) -> str:
    if isinstance(entry, BaselineEntry):
        return entry.gate
    return default_gate


def _entry_rule(entry: BaselineEntry | TestQuarantineEntry, default_rule: str) -> str:
    if isinstance(entry, BaselineEntry):
        return entry.rule
    return default_rule


def compare(
    gate: str,
    observed: Sequence[ObservedFinding],
    entries: Sequence[BaselineEntry | TestQuarantineEntry],
    *,
    evaluated_on: date,
    resolved_requires_removal: bool = True,
    default_rule: str = "pytest-failure",
    passing_identities: Iterable[str] = (),
) -> BaselineComparison:
    """Compare fresh observations against the ledger for one gate.

    ``passing_identities`` is used by the test adapter: quarantined test
    nodes that now pass must have their entries removed
    (resolved-but-not-removed enforcement). For scanner gates the same
    enforcement happens via absence (stale-entry).
    """
    violations: list[BaselineViolation] = []
    known: list[ObservedFinding] = []
    new: list[ObservedFinding] = []
    changed: list[ObservedFinding] = []

    entry_by_fingerprint: dict[str, BaselineEntry | TestQuarantineEntry] = {}
    entries_by_identity: dict[str, list[BaselineEntry | TestQuarantineEntry]] = {}
    for entry in entries:
        if entry.fingerprint in entry_by_fingerprint:
            violations.append(
                BaselineViolation(
                    kind=ViolationKind.MALFORMED_BASELINE,
                    gate=gate,
                    rule=_entry_rule(entry, default_rule),
                    identity=_entry_identity(entry),
                    detail=(
                        "duplicate fingerprint in ledger: "
                        f"{entry.fingerprint} (entries "
                        f"{entry_by_fingerprint[entry.fingerprint].id!r} and {entry.id!r})"
                    ),
                    fingerprint=entry.fingerprint,
                    entry_id=entry.id,
                )
            )
            continue
        entry_by_fingerprint[entry.fingerprint] = entry
        entries_by_identity.setdefault(_entry_identity(entry), []).append(entry)

    expired_fingerprints: set[str] = set()
    for entry in entry_by_fingerprint.values():
        if entry.is_expired(evaluated_on):
            expired_fingerprints.add(entry.fingerprint)

    observed_by_fingerprint: dict[str, list[ObservedFinding]] = {}
    observed_identities: set[str] = set()
    for finding in observed:
        observed_by_fingerprint.setdefault(finding.fingerprint, []).append(finding)
        observed_identities.add(finding.identity)

    fingerprint_counts: Counter[str] = Counter(
        finding.fingerprint for finding in observed
    )
    for fingerprint, count in sorted(fingerprint_counts.items()):
        if fingerprint in entry_by_fingerprint and count > 1:
            sample = observed_by_fingerprint[fingerprint][0]
            violations.append(
                BaselineViolation(
                    kind=ViolationKind.INCREASED_FINDING,
                    gate=gate,
                    rule=sample.rule,
                    identity=sample.identity,
                    detail=(
                        f"fingerprint {fingerprint} observed {count} times but the "
                        "ledger tolerates exactly one occurrence"
                    ),
                    fingerprint=fingerprint,
                    entry_id=entry_by_fingerprint[fingerprint].id,
                    path=sample.path,
                )
            )

    for finding in observed:
        entry = entry_by_fingerprint.get(finding.fingerprint)
        if entry is not None:
            if entry.is_expired(evaluated_on):
                violations.append(
                    BaselineViolation(
                        kind=ViolationKind.EXPIRED_EXCEPTION,
                        gate=gate,
                        rule=finding.rule,
                        identity=finding.identity,
                        detail=(
                            f"ledger entry {entry.id!r} expired on "
                            f"{entry.expires.isoformat()}; the finding is still present"
                        ),
                        fingerprint=finding.fingerprint,
                        entry_id=entry.id,
                        path=finding.path,
                    )
                )
            else:
                known.append(finding)
            continue

        identity_entries = entries_by_identity.get(finding.identity, [])
        if identity_entries:
            entry_ids = ", ".join(repr(entry.id) for entry in identity_entries)
            changed.append(finding)
            violations.append(
                BaselineViolation(
                    kind=ViolationKind.CHANGED_SIGNATURE,
                    gate=gate,
                    rule=finding.rule,
                    identity=finding.identity,
                    detail=(
                        "identity is ledgered but the observed failure fingerprint "
                        f"{finding.fingerprint} does not match any ledger entry "
                        f"({entry_ids}); the failure has changed and must be "
                        "re-triaged"
                    ),
                    fingerprint=finding.fingerprint,
                    entry_id=identity_entries[0].id,
                    path=finding.path,
                )
            )
        else:
            new.append(finding)
            violations.append(
                BaselineViolation(
                    kind=ViolationKind.NEW_FINDING,
                    gate=gate,
                    rule=finding.rule,
                    identity=finding.identity,
                    detail=(
                        f"unledgered finding {finding.fingerprint}: "
                        f"{finding.message or finding.identity}"
                    ),
                    fingerprint=finding.fingerprint,
                    path=finding.path,
                )
            )

    passing = set(passing_identities)
    resolved_entry_ids: list[str] = []
    for fingerprint, entry in sorted(entry_by_fingerprint.items()):
        if fingerprint in observed_by_fingerprint:
            continue
        identity = _entry_identity(entry)
        if identity in observed_identities:
            # Identity still failing with a different signature;
            # already reported as CHANGED_SIGNATURE above.
            continue
        resolved_entry_ids.append(entry.id)
        if not resolved_requires_removal:
            continue
        if isinstance(entry, TestQuarantineEntry):
            if identity in passing:
                violations.append(
                    BaselineViolation(
                        kind=ViolationKind.RESOLVED_NOT_REMOVED,
                        gate=gate,
                        rule=_entry_rule(entry, default_rule),
                        identity=identity,
                        detail=(
                            f"quarantined test {identity!r} now passes; remove ledger "
                            f"entry {entry.id!r} to keep the ledger truthful"
                        ),
                        fingerprint=fingerprint,
                        entry_id=entry.id,
                    )
                )
            else:
                violations.append(
                    BaselineViolation(
                        kind=ViolationKind.STALE_ENTRY,
                        gate=gate,
                        rule=_entry_rule(entry, default_rule),
                        identity=identity,
                        detail=(
                            f"ledger entry {entry.id!r} references test {identity!r} "
                            "which was not observed in this run (renamed, deleted, or "
                            "not collected); remove or update the entry"
                        ),
                        fingerprint=fingerprint,
                        entry_id=entry.id,
                    )
                )
        else:
            violations.append(
                BaselineViolation(
                    kind=ViolationKind.STALE_ENTRY,
                    gate=gate,
                    rule=entry.rule,
                    identity=identity,
                    detail=(
                        f"ledger entry {entry.id!r} no longer matches any observed "
                        "finding; the debt is resolved — remove the entry to ratchet "
                        "the baseline down"
                    ),
                    fingerprint=fingerprint,
                    entry_id=entry.id,
                    path=entry.path,
                )
            )

    ordered_violations = sort_violations(violations)
    summary = BaselineSummary(
        observed_total=len(observed),
        known_total=len(known),
        new_total=len(new),
        changed_total=len(changed),
        resolved_total=len(resolved_entry_ids),
        expired_total=len(expired_fingerprints),
        malformed_total=sum(
            1
            for violation in ordered_violations
            if violation.kind is ViolationKind.MALFORMED_BASELINE
        ),
        violations_total=len(ordered_violations),
    )
    return BaselineComparison(
        schema_version=COMPARISON_SCHEMA_VERSION,
        gate=gate,
        evaluated_on=evaluated_on,
        passed=not ordered_violations,
        summary=summary,
        violations=ordered_violations,
        known=tuple(known),
        new=tuple(new),
        resolved_entry_ids=tuple(sorted(resolved_entry_ids)),
        suggested_removals=tuple(sorted(resolved_entry_ids)),
    )


def load_entries_strict(
    raw_entries: Sequence[Mapping[str, object]],
    *,
    entry_kind: str,
) -> tuple[list[BaselineEntry | TestQuarantineEntry], list[BaselineViolation]]:
    """Parse raw ledger mappings fail-closed.

    Malformed entries (missing owner, missing issue, missing any
    required field, bad types) become MALFORMED_BASELINE /
    MISSING_OWNER / MISSING_ISSUE violations instead of being silently
    dropped, so a broken ledger can never produce a green result.
    """
    entries: list[BaselineEntry | TestQuarantineEntry] = []
    violations: list[BaselineViolation] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, Mapping):
            violations.append(
                BaselineViolation(
                    kind=ViolationKind.MALFORMED_BASELINE,
                    gate=entry_kind,
                    rule="ledger",
                    identity=f"entry[{index}]",
                    detail=f"entry {index} is not a mapping",
                )
            )
            continue
        raw_id = str(raw.get("id", f"entry[{index}]"))
        owner_raw = str(raw.get("owner", "") or "")
        issue_raw = str(raw.get("issue", "") or "")
        try:
            entry: BaselineEntry | TestQuarantineEntry
            if entry_kind == "test-quarantine":
                entry = TestQuarantineEntry(
                    id=str(raw.get("id", "")),
                    test_node_id=str(raw.get("test_node_id", "")),
                    fingerprint=str(raw.get("fingerprint", "")),
                    exception_type=str(raw.get("exception_type", "")),
                    failure_signature=str(raw.get("failure_signature", "")),
                    owner=owner_raw,
                    issue=issue_raw,
                    introduced_before=str(raw.get("introduced_before", "")),
                    expires=raw.get("expires", ""),  # type: ignore[arg-type]
                    removal_condition=raw.get("removal_condition", ""),  # type: ignore[arg-type]
                    root_cause_group=(
                        str(raw["root_cause_group"])
                        if raw.get("root_cause_group") is not None
                        else None
                    ),
                    evidence=(
                        str(raw["evidence"])
                        if raw.get("evidence") is not None
                        else None
                    ),
                    last_verified_commit=(
                        str(raw["last_verified_commit"])
                        if raw.get("last_verified_commit") is not None
                        else None
                    ),
                )
            else:
                entry = BaselineEntry(
                    id=str(raw.get("id", "")),
                    gate=str(raw.get("gate", "")),
                    rule=str(raw.get("rule", "")),
                    fingerprint=str(raw.get("fingerprint", "")),
                    path=str(raw.get("path", "")),
                    owner=owner_raw,
                    issue=issue_raw,
                    introduced_before=str(raw.get("introduced_before", "")),
                    expires=raw.get("expires", ""),  # type: ignore[arg-type]
                    removal_condition=raw.get("removal_condition", ""),  # type: ignore[arg-type]
                    root_cause_group=(
                        str(raw["root_cause_group"])
                        if raw.get("root_cause_group") is not None
                        else None
                    ),
                    evidence=(
                        str(raw["evidence"])
                        if raw.get("evidence") is not None
                        else None
                    ),
                    last_verified_commit=(
                        str(raw["last_verified_commit"])
                        if raw.get("last_verified_commit") is not None
                        else None
                    ),
                )
        except ValueError as exc:
            message = str(exc)
            if message.startswith("owner"):
                kind = ViolationKind.MISSING_OWNER
            elif message.startswith("issue"):
                kind = ViolationKind.MISSING_ISSUE
            else:
                kind = ViolationKind.MALFORMED_BASELINE
            violations.append(
                BaselineViolation(
                    kind=kind,
                    gate=entry_kind,
                    rule="ledger",
                    identity=raw_id,
                    detail=f"invalid ledger entry {raw_id!r}: {message}",
                )
            )
            continue
        if entry.id in seen_ids:
            violations.append(
                BaselineViolation(
                    kind=ViolationKind.MALFORMED_BASELINE,
                    gate=entry_kind,
                    rule="ledger",
                    identity=entry.id,
                    detail=f"duplicate ledger entry id {entry.id!r}",
                    entry_id=entry.id,
                )
            )
            continue
        seen_ids.add(entry.id)
        entries.append(entry)
    return entries, violations
