"""Gate evaluation over canonical findings and provider state."""

from __future__ import annotations
from l9_ci.contracts import (
    CoverageStatus,
    FindingBundle,
    RuleMode,
)
from .model import GateResult, GateStatus


def evaluate_gate(
    bundle: FindingBundle,
    *,
    strict_unresolved: bool = True,
) -> GateResult:
    """Evaluate a validated canonical bundle.
    Evaluation order:
    1. Invalid references or missing classifications produce INVALID.
    2. Fatal required-provider failures or incomplete required coverage
       produce INCOMPLETE.
    3. Blocking findings produce FAIL.
    4. Strict unresolved findings produce INCOMPLETE.
    5. Otherwise the result is PASS.
    """
    finding_ids = {finding.finding_id for finding in bundle.findings}
    classifications = {
        classification.finding_id: classification
        for classification in bundle.classifications
    }
    reasons: list[str] = []
    missing_classifications = finding_ids - set(classifications)
    if missing_classifications:
        reasons.append(
            "findings are missing classifications: "
            + ", ".join(sorted(missing_classifications))
        )
        return GateResult(
            status=GateStatus.INVALID,
            blocking_finding_ids=(),
            unresolved_finding_ids=tuple(missing_classifications),
            fatal_provider_ids=(),
            incomplete_provider_ids=(),
            reasons=tuple(reasons),
        )
    fatal_provider_ids = {
        failure.provider_id
        for failure in bundle.provider_failures
        if failure.required and failure.fatal
    }
    required_provider_ids = {
        provider.provider_id for provider in bundle.providers if provider.required
    }
    coverage_by_provider = {
        coverage.provider_id: coverage for coverage in bundle.coverage
    }
    incomplete_provider_ids: set[str] = set()
    for provider_id in required_provider_ids:
        coverage = coverage_by_provider.get(provider_id)
        if coverage is None:
            incomplete_provider_ids.add(provider_id)
            continue
        if coverage.status in {
            CoverageStatus.FAILED,
            CoverageStatus.PARTIAL,
            CoverageStatus.SKIPPED,
            CoverageStatus.UNSUPPORTED,
        }:
            incomplete_provider_ids.add(provider_id)
    if fatal_provider_ids:
        reasons.append(
            "required providers failed: " + ", ".join(sorted(fatal_provider_ids))
        )
    if incomplete_provider_ids:
        reasons.append(
            "required provider coverage is incomplete: "
            + ", ".join(sorted(incomplete_provider_ids))
        )
    if fatal_provider_ids or incomplete_provider_ids:
        return GateResult(
            status=GateStatus.INCOMPLETE,
            blocking_finding_ids=(),
            unresolved_finding_ids=(),
            fatal_provider_ids=tuple(fatal_provider_ids),
            incomplete_provider_ids=tuple(incomplete_provider_ids),
            reasons=tuple(reasons),
        )
    blocking_ids = tuple(
        sorted(
            classification.finding_id
            for classification in bundle.classifications
            if classification.mode is RuleMode.BLOCKING
        )
    )
    unresolved_ids = tuple(
        sorted(
            classification.finding_id
            for classification in bundle.classifications
            if classification.mode is RuleMode.UNRESOLVED
        )
    )
    if blocking_ids:
        reasons.append("blocking findings exist: " + ", ".join(blocking_ids))
        return GateResult(
            status=GateStatus.FAIL,
            blocking_finding_ids=blocking_ids,
            unresolved_finding_ids=unresolved_ids,
            fatal_provider_ids=(),
            incomplete_provider_ids=(),
            reasons=tuple(reasons),
        )
    if strict_unresolved and unresolved_ids:
        reasons.append(
            "unresolved findings exist under strict evaluation: "
            + ", ".join(unresolved_ids)
        )
        return GateResult(
            status=GateStatus.INCOMPLETE,
            blocking_finding_ids=(),
            unresolved_finding_ids=unresolved_ids,
            fatal_provider_ids=(),
            incomplete_provider_ids=(),
            reasons=tuple(reasons),
        )
    return GateResult(
        status=GateStatus.PASS,
        blocking_finding_ids=(),
        unresolved_finding_ids=unresolved_ids,
        fatal_provider_ids=(),
        incomplete_provider_ids=(),
        reasons=(),
    )
