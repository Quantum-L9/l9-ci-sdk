"""Fail-closed decision matrix for the gate evaluator.

This suite replaces the original two-case test. It exercises every decision
branch of ``evaluate_gate`` (INVALID, INCOMPLETE, FAIL, strict-unresolved
INCOMPLETE, PASS), every ``CoverageStatus`` for a required provider, required
fatal and non-fatal provider failures, optional-provider failures, and the
precedence order when multiple conditions coexist.

The row marked ``required_nonfatal_failure_is_incomplete`` is the direct
regression guard for AUD-003: a required provider that records a *non-fatal*
failure must not permit PASS even when coverage is otherwise COMPLETE.
"""

from __future__ import annotations
import pytest
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    Finding,
    FindingBundle,
    FindingClassification,
    ProviderFailure,
    ProviderFailureType,
    ProviderRun,
    ResolutionStatus,
    RuleMode,
    SnapshotDescriptor,
)
from l9_ci.gates import GateStatus, evaluate_gate


def _coverage(status: CoverageStatus, provider_id: str = "semgrep") -> Coverage:
    analyzed = 1 if status is CoverageStatus.COMPLETE else 0
    return Coverage(provider_id, status, 1, analyzed, ())


def _failure(
    *, required: bool, fatal: bool, provider_id: str = "semgrep"
) -> ProviderFailure:
    return ProviderFailure(
        provider_id=provider_id,
        failure_type=ProviderFailureType.EXECUTION_ERROR,
        message="provider reported a failure",
        required=required,
        fatal=fatal,
    )


def _classification(finding_id: str, mode: RuleMode) -> FindingClassification:
    if mode is RuleMode.UNRESOLVED:
        return FindingClassification(
            finding_id=finding_id,
            mode=mode,
            resolution_status=ResolutionStatus.UNRESOLVED,
            used_default=False,
        )
    return FindingClassification(
        finding_id=finding_id,
        mode=mode,
        resolution_status=ResolutionStatus.EXPLICIT,
        used_default=False,
        policy_key="policy",
        policy_version="1.0.0",
    )


def _finding(finding_id: str) -> Finding:
    return Finding(
        finding_id=finding_id,
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="rule",
        category="security",
        message="issue",
        evidence_ids=(f"{finding_id}-e1",),
        locations=(),
        fingerprint=f"{finding_id}-fp",
    )


def make_bundle(
    *,
    providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", True),),
    coverage=(_coverage(CoverageStatus.COMPLETE),),
    provider_failures=(),
    classifications=(),
    findings=(),
) -> FindingBundle:
    return FindingBundle(
        SDK_version="1.0.0",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor("snapshot-1", "."),
        providers=providers,
        evidence=(),
        findings=findings,
        classifications=classifications,
        provider_failures=provider_failures,
        coverage=coverage,
    )


# --- Single-condition decision matrix ---------------------------------------

CASES = {
    "complete_empty_passes": (make_bundle(), GateStatus.PASS),
    "required_partial_coverage_incomplete": (
        make_bundle(coverage=(_coverage(CoverageStatus.PARTIAL),)),
        GateStatus.INCOMPLETE,
    ),
    "required_skipped_coverage_incomplete": (
        make_bundle(coverage=(_coverage(CoverageStatus.SKIPPED),)),
        GateStatus.INCOMPLETE,
    ),
    "required_unsupported_coverage_incomplete": (
        make_bundle(coverage=(_coverage(CoverageStatus.UNSUPPORTED),)),
        GateStatus.INCOMPLETE,
    ),
    "required_failed_coverage_incomplete": (
        make_bundle(coverage=(_coverage(CoverageStatus.FAILED),)),
        GateStatus.INCOMPLETE,
    ),
    "required_missing_coverage_incomplete": (
        make_bundle(coverage=()),
        GateStatus.INCOMPLETE,
    ),
    "required_fatal_failure_incomplete": (
        make_bundle(provider_failures=(_failure(required=True, fatal=True),)),
        GateStatus.INCOMPLETE,
    ),
    # AUD-003 regression: required + non-fatal must NOT pass.
    "required_nonfatal_failure_is_incomplete": (
        make_bundle(provider_failures=(_failure(required=True, fatal=False),)),
        GateStatus.INCOMPLETE,
    ),
    "optional_nonfatal_failure_passes": (
        make_bundle(
            providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", False),),
            provider_failures=(_failure(required=False, fatal=False),),
        ),
        GateStatus.PASS,
    ),
    "optional_fatal_failure_does_not_fail_gate": (
        make_bundle(
            providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", False),),
            provider_failures=(_failure(required=False, fatal=True),),
        ),
        GateStatus.PASS,
    ),
    "blocking_classification_fails": (
        make_bundle(classifications=(_classification("f1", RuleMode.BLOCKING),)),
        GateStatus.FAIL,
    ),
    "advisory_classification_passes": (
        make_bundle(classifications=(_classification("f1", RuleMode.ADVISORY),)),
        GateStatus.PASS,
    ),
    "missing_classification_invalid": (
        make_bundle(findings=(_finding("f1"),)),
        GateStatus.INVALID,
    ),
}


@pytest.mark.parametrize(
    "bundle,expected",
    list(CASES.values()),
    ids=list(CASES.keys()),
)
def test_gate_decision_matrix(bundle, expected):
    assert evaluate_gate(bundle).status is expected


# --- strict_unresolved toggle -----------------------------------------------


def test_unresolved_is_incomplete_under_strict():
    bundle = make_bundle(classifications=(_classification("f1", RuleMode.UNRESOLVED),))
    assert evaluate_gate(bundle, strict_unresolved=True).status is GateStatus.INCOMPLETE


def test_unresolved_passes_under_permissive():
    bundle = make_bundle(classifications=(_classification("f1", RuleMode.UNRESOLVED),))
    result = evaluate_gate(bundle, strict_unresolved=False)
    assert result.status is GateStatus.PASS
    assert result.unresolved_finding_ids == ("f1",)


# --- AUD-003 detail: reported sets and reasons ------------------------------


def test_required_nonfatal_failure_reported_as_incomplete_not_fatal():
    bundle = make_bundle(provider_failures=(_failure(required=True, fatal=False),))
    result = evaluate_gate(bundle)
    assert result.status is GateStatus.INCOMPLETE
    assert "semgrep" in result.incomplete_provider_ids
    assert result.fatal_provider_ids == ()
    assert any("non-fatal" in reason for reason in result.reasons)


def test_required_fatal_failure_reported_as_fatal():
    bundle = make_bundle(provider_failures=(_failure(required=True, fatal=True),))
    result = evaluate_gate(bundle)
    assert result.status is GateStatus.INCOMPLETE
    assert "semgrep" in result.fatal_provider_ids


# --- Precedence when conditions coexist -------------------------------------


def test_invalid_precedes_all():
    # Missing classification (INVALID) coexisting with a fatal failure and a
    # blocking classification still resolves to INVALID.
    bundle = make_bundle(
        findings=(_finding("f1"),),
        classifications=(_classification("f2", RuleMode.BLOCKING),),
        provider_failures=(_failure(required=True, fatal=True),),
    )
    assert evaluate_gate(bundle).status is GateStatus.INVALID


def test_incomplete_precedes_fail():
    # A fatal required failure (INCOMPLETE) outranks a blocking finding (FAIL).
    bundle = make_bundle(
        classifications=(_classification("f1", RuleMode.BLOCKING),),
        provider_failures=(_failure(required=True, fatal=True),),
    )
    assert evaluate_gate(bundle).status is GateStatus.INCOMPLETE


def test_fail_precedes_strict_unresolved():
    bundle = make_bundle(
        classifications=(
            _classification("f1", RuleMode.BLOCKING),
            _classification("f2", RuleMode.UNRESOLVED),
        ),
    )
    assert evaluate_gate(bundle, strict_unresolved=True).status is GateStatus.FAIL


# --- Summary counts ----------------------------------------------------------


def test_summary_counts_reported():
    bundle = make_bundle(
        coverage=(_coverage(CoverageStatus.PARTIAL),),
        provider_failures=(_failure(required=True, fatal=True),),
    )
    payload = evaluate_gate(bundle).to_dict()
    summary = payload["summary"]
    assert summary["fatal_provider_count"] == 1
    assert summary["incomplete_provider_count"] == 1
