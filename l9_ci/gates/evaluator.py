"""Gate evaluation over canonical findings and provider state.

Every reason names its subjects (L9-SIGNAL-001, ADR 0025): a finding by rule ID
and ``path:line``, a provider by ID with its failure type and error text, an
incomplete coverage record by provider ID, status and limitations. Each reason
string is mirrored by a :class:`ReasonDetail` carrying the same subjects.
"""

from __future__ import annotations

from collections.abc import Iterable

from l9_ci.contracts import (
    CoverageStatus,
    Finding,
    FindingBundle,
    ProviderFailure,
    RuleMode,
    cap_subjects,
    subject_reason,
)

from .model import GateResult, GateStatus, ReasonCode, ReasonDetail

_REASON_TEXT = {
    ReasonCode.MISSING_CLASSIFICATIONS: "findings are missing classifications",
    ReasonCode.REQUIRED_PROVIDER_FAILED: "required providers failed",
    ReasonCode.REQUIRED_PROVIDER_NONFATAL_FAILURE: (
        "required providers reported non-fatal failures"
    ),
    ReasonCode.REQUIRED_COVERAGE_INCOMPLETE: "required provider coverage is incomplete",
    ReasonCode.BLOCKING_FINDINGS: "blocking findings exist",
    ReasonCode.UNRESOLVED_FINDINGS: (
        "unresolved findings exist under strict evaluation"
    ),
}


def finding_subject(finding: Finding | None, finding_id: str) -> str:
    """``<rule> at <path>:<line>``; the finding ID when the finding is unknown."""
    if finding is None:
        return f"{finding_id} (finding not in bundle)"
    rule = finding.canonical_rule_id or finding.provider_rule_id
    if not finding.locations:
        return f"{rule} (no location; {finding_id})"
    location = finding.locations[0]
    line = location.start_line
    where = f"{location.normalized_path}:{line}" if line else location.normalized_path
    return f"{rule} at {where}"


def failure_subject(failure: ProviderFailure) -> str:
    """``<provider>: <failure type>: <message>``."""
    return f"{failure.provider_id}: {failure.failure_type.value}: {failure.message}"


def _reason(code: ReasonCode, subjects: Iterable[str]) -> tuple[str, ReasonDetail]:
    items = list(subjects)
    shown, omitted = cap_subjects(items)
    return (
        subject_reason(_REASON_TEXT[code], items),
        ReasonDetail(code=code, subjects=shown, omitted=omitted),
    )


def evaluate_gate(
    bundle: FindingBundle,
    *,
    strict_unresolved: bool = True,
) -> GateResult:
    """Evaluate a validated canonical bundle.
    Evaluation order:
    1. Invalid references or missing classifications produce INVALID.
    2. Any required-provider failure (fatal or non-fatal) or incomplete
       required coverage produces INCOMPLETE.
    3. Blocking findings produce FAIL.
    4. Strict unresolved findings produce INCOMPLETE.
    5. Otherwise the result is PASS.
    """
    findings = {finding.finding_id: finding for finding in bundle.findings}
    classifications = {
        classification.finding_id: classification
        for classification in bundle.classifications
    }
    reasons: list[str] = []
    details: list[ReasonDetail] = []

    def add(code: ReasonCode, subjects: Iterable[str]) -> None:
        text, detail = _reason(code, subjects)
        reasons.append(text)
        details.append(detail)

    missing_classifications = set(findings) - set(classifications)
    if missing_classifications:
        add(
            ReasonCode.MISSING_CLASSIFICATIONS,
            (
                finding_subject(findings.get(item), item)
                for item in missing_classifications
            ),
        )
        return GateResult(
            status=GateStatus.INVALID,
            blocking_finding_ids=(),
            unresolved_finding_ids=tuple(missing_classifications),
            fatal_provider_ids=(),
            incomplete_provider_ids=(),
            reasons=tuple(reasons),
            reason_details=tuple(details),
        )
    fatal_failures = [
        failure
        for failure in bundle.provider_failures
        if failure.required and failure.fatal
    ]
    fatal_provider_ids = {failure.provider_id for failure in fatal_failures}
    # Any failure on a REQUIRED provider is gate-significant, regardless of the
    # `fatal` flag. Fatal required failures are reported as fatal; non-fatal
    # required failures still make that provider's evidence untrustworthy, so
    # they force INCOMPLETE rather than being silently ignored (which would be
    # a fail-open result). Failures on OPTIONAL providers remain visible in the
    # bundle but do not independently fail the gate, per the integration
    # contract's requiredness semantics.
    nonfatal_failures = [
        failure
        for failure in bundle.provider_failures
        if failure.required
        and not failure.fatal
        and failure.provider_id not in fatal_provider_ids
    ]
    nonfatal_required_failure_ids = {
        failure.provider_id for failure in nonfatal_failures
    }
    required_provider_ids = {
        provider.provider_id for provider in bundle.providers if provider.required
    }
    coverage_by_provider = {
        coverage.provider_id: coverage for coverage in bundle.coverage
    }
    coverage_incomplete_ids: set[str] = set()
    coverage_subjects: list[str] = []
    for provider_id in required_provider_ids:
        coverage = coverage_by_provider.get(provider_id)
        if coverage is None:
            coverage_incomplete_ids.add(provider_id)
            coverage_subjects.append(f"{provider_id}: no coverage record")
            continue
        if coverage.status in {
            CoverageStatus.FAILED,
            CoverageStatus.PARTIAL,
            CoverageStatus.SKIPPED,
            CoverageStatus.UNSUPPORTED,
        }:
            coverage_incomplete_ids.add(provider_id)
            detail = "; ".join(sorted(coverage.limitations)) or "no limitation recorded"
            coverage_subjects.append(
                f"{provider_id}: coverage {coverage.status.value}: {detail}"
            )
    incomplete_provider_ids = coverage_incomplete_ids | nonfatal_required_failure_ids
    if fatal_failures:
        add(
            ReasonCode.REQUIRED_PROVIDER_FAILED,
            (failure_subject(failure) for failure in fatal_failures),
        )
    if nonfatal_failures:
        add(
            ReasonCode.REQUIRED_PROVIDER_NONFATAL_FAILURE,
            (failure_subject(failure) for failure in nonfatal_failures),
        )
    if coverage_subjects:
        add(ReasonCode.REQUIRED_COVERAGE_INCOMPLETE, coverage_subjects)
    if fatal_provider_ids or incomplete_provider_ids:
        return GateResult(
            status=GateStatus.INCOMPLETE,
            blocking_finding_ids=(),
            unresolved_finding_ids=(),
            fatal_provider_ids=tuple(fatal_provider_ids),
            incomplete_provider_ids=tuple(incomplete_provider_ids),
            reasons=tuple(reasons),
            reason_details=tuple(details),
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
        add(
            ReasonCode.BLOCKING_FINDINGS,
            (finding_subject(findings.get(item), item) for item in blocking_ids),
        )
        return GateResult(
            status=GateStatus.FAIL,
            blocking_finding_ids=blocking_ids,
            unresolved_finding_ids=unresolved_ids,
            fatal_provider_ids=(),
            incomplete_provider_ids=(),
            reasons=tuple(reasons),
            reason_details=tuple(details),
        )
    if strict_unresolved and unresolved_ids:
        add(
            ReasonCode.UNRESOLVED_FINDINGS,
            (finding_subject(findings.get(item), item) for item in unresolved_ids),
        )
        return GateResult(
            status=GateStatus.INCOMPLETE,
            blocking_finding_ids=(),
            unresolved_finding_ids=unresolved_ids,
            fatal_provider_ids=(),
            incomplete_provider_ids=(),
            reasons=tuple(reasons),
            reason_details=tuple(details),
        )
    return GateResult(
        status=GateStatus.PASS,
        blocking_finding_ids=(),
        unresolved_finding_ids=unresolved_ids,
        fatal_provider_ids=(),
        incomplete_provider_ids=(),
        reasons=(),
    )
