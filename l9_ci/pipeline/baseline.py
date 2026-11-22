"""Classify findings as new or pre-existing against a baseline commit (ADR 0023).

The classification comes from Semgrep's own baseline mechanism: the same scan
run again with ``--baseline-commit <sha>`` reports only results that are absent
at that commit. Semgrep re-scans the baseline itself in a git worktree, so a
finding that moved lines or whose file was renamed stays pre-existing. Both
scans read the same working tree, so a finding of the full scan is ``new``
exactly when the baseline scan reports a result with the same fingerprint.

Fail closed (L9-UNKNOWN-001): when the baseline cannot be resolved or the
baseline scan is not complete, every finding is ``unknown`` and keeps its
policy mode, and the pipeline records a required provider failure so the gate
is never PASS.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from l9_ci.contracts import (
    BaselineStatus,
    Finding,
    FindingClassification,
    RuleMode,
)


@dataclass(frozen=True, slots=True)
class BaselineApplication:
    classifications: tuple[FindingClassification, ...]
    limitations: tuple[str, ...]
    new_count: int
    pre_existing_count: int
    unknown_count: int


def apply_baseline(
    findings: Iterable[Finding],
    classifications: Iterable[FindingClassification],
    *,
    baseline_commit: str,
    new_fingerprints: frozenset[str] | None,
    unresolved_reason: str | None = None,
) -> BaselineApplication:
    """Stamp each classification with its baseline status.

    ``new_fingerprints`` is the set of fingerprints the baseline scan still
    reported, or ``None`` when the baseline is unresolved. A ``pre_existing``
    finding whose policy mode is ``blocking`` is reported as ``advisory``; its
    policy key, version and waiver are kept. A ``new`` or ``unknown`` finding
    keeps its policy mode.
    """
    by_id = {finding.finding_id: finding for finding in findings}
    result: list[FindingClassification] = []
    counts = {status: 0 for status in BaselineStatus}
    downgraded = 0
    for classification in classifications:
        finding = by_id.get(classification.finding_id)
        if new_fingerprints is None or finding is None:
            status = BaselineStatus.UNKNOWN
        elif finding.fingerprint in new_fingerprints:
            status = BaselineStatus.NEW
        else:
            status = BaselineStatus.PRE_EXISTING
        counts[status] += 1
        mode = classification.mode
        if status is BaselineStatus.PRE_EXISTING and mode is RuleMode.BLOCKING:
            mode = RuleMode.ADVISORY
            downgraded += 1
        result.append(replace(classification, mode=mode, baseline_status=status))
    short = baseline_commit[:12]
    limitations = [
        f"baseline {short}: {counts[BaselineStatus.NEW]} new, "
        f"{counts[BaselineStatus.PRE_EXISTING]} pre-existing "
        f"({downgraded} blocking reported as advisory), "
        f"{counts[BaselineStatus.UNKNOWN]} unknown"
    ]
    if new_fingerprints is None:
        limitations.append(
            f"baseline {short} unresolved: {unresolved_reason or 'unknown reason'}; "
            "every finding keeps its policy mode and the run fails closed"
        )
    return BaselineApplication(
        classifications=tuple(result),
        limitations=tuple(limitations),
        new_count=counts[BaselineStatus.NEW],
        pre_existing_count=counts[BaselineStatus.PRE_EXISTING],
        unknown_count=counts[BaselineStatus.UNKNOWN],
    )


__all__ = ["BaselineApplication", "apply_baseline"]
