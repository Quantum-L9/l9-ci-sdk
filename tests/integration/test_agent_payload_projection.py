import pytest
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    EvidenceRecord,
    Finding,
    FindingBundle,
    FindingClassification,
    ProviderRun,
    ResolutionStatus,
    RuleMode,
    Severity,
    SnapshotDescriptor,
    SourceLocation,
)
from l9_ci.integration import project_agent_review_payload


def build_bundle(mode: RuleMode) -> FindingBundle:
    location = SourceLocation("src/example.py", start_line=1)
    evidence = EvidenceRecord(
        evidence_id="evidence-1",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="rule.one",
        evidence_type="static-analysis-match",
        message="Example",
        locations=(location,),
    )
    finding = Finding(
        finding_id="finding-1",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="rule.one",
        canonical_rule_id=(None if mode is RuleMode.UNRESOLVED else "L9-RULE-ONE"),
        category="security",
        message="Example",
        evidence_ids=("evidence-1",),
        locations=(location,),
        fingerprint="fingerprint-1",
        severity=Severity.HIGH,
        remediation_class="safe-autofix",
    )
    classification = FindingClassification(
        finding_id="finding-1",
        mode=mode,
        resolution_status=(
            ResolutionStatus.UNRESOLVED
            if mode is RuleMode.UNRESOLVED
            else ResolutionStatus.EXPLICIT
        ),
        used_default=False,
        policy_key=(None if mode is RuleMode.UNRESOLVED else "L9-RULE-ONE"),
        policy_version="1.0.0",
    )
    return FindingBundle(
        SDK_version="1.0.0",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor(
            snapshot_id="snapshot-1",
            repository_root=".",
        ),
        providers=(
            ProviderRun(
                provider_id="semgrep",
                adapter_version="1.0.0",
                provider_version="1.100.0",
                mode="import",
                required=True,
            ),
        ),
        evidence=(evidence,),
        findings=(finding,),
        classifications=(classification,),
        provider_failures=(),
        coverage=(
            Coverage(
                provider_id="semgrep",
                status=CoverageStatus.COMPLETE,
                files_considered=1,
                files_analyzed=1,
                limitations=(),
            ),
        ),
    )


def test_blocking_finding_projects_to_blocking_bucket() -> None:
    payload = project_agent_review_payload(
        build_bundle(RuleMode.BLOCKING),
        strict=True,
    )
    assert len(payload.blocking_findings) == 1
    assert len(payload.autofix_candidates) == 1
    assert payload.advisory_findings == ()


def test_unresolved_finding_projects_non_strict() -> None:
    payload = project_agent_review_payload(
        build_bundle(RuleMode.UNRESOLVED),
        strict=False,
    )
    assert len(payload.unresolved_findings) == 1
    assert payload.autofix_candidates == ()


def test_unresolved_finding_fails_strict_projection() -> None:
    with pytest.raises(ValueError, match="unresolved"):
        project_agent_review_payload(
            build_bundle(RuleMode.UNRESOLVED),
            strict=True,
        )
