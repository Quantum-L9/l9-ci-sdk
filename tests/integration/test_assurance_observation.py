from __future__ import annotations

import pytest

from l9_ci.contracts import (
    Confidence,
    EvidenceRecord,
    Finding,
    FindingBundle,
    FindingClassification,
    ResolutionStatus,
    RuleMode,
    Severity,
    SnapshotDescriptor,
    SourceLocation,
)
from l9_ci.integration import (
    build_observation,
    project_mandatory_findings_observation,
    validate_observation,
)

REVISION = "a" * 40
DIGEST = "b" * 64
STARTED = "2026-08-21T20:00:00Z"
COMPLETED = "2026-08-21T20:00:01Z"


def test_generic_observation_is_revision_bound_and_deterministic() -> None:
    kwargs = dict(
        producer_version="2.0.0",
        repository="Quantum-L9/example",
        revision=REVISION,
        check_id="l9.tests",
        configuration_digest=DIGEST,
        run_id="12345",
        attempt=1,
        status="passed",
        started_at=STARTED,
        completed_at=COMPLETED,
    )
    first = build_observation(**kwargs)
    second = build_observation(**kwargs)

    assert first == second
    assert first["schema"] == "l9.observation"
    assert first["schemaVersion"] == "1.0.0"
    assert first["producer"]["id"] == "l9-ci-sdk"
    assert first["subject"]["revision"]["commit"] == REVISION
    assert first["check"]["id"] == "l9.tests"
    assert first["check"]["configurationDigest"]["value"] == DIGEST
    assert first["observationId"].startswith("sha256:")
    validate_observation(first)


def test_observation_id_changes_with_execution_identity() -> None:
    common = dict(
        producer_version="2.0.0",
        repository="Quantum-L9/example",
        revision=REVISION,
        check_id="l9.lint",
        configuration_digest=DIGEST,
        attempt=1,
        status="passed",
        started_at=STARTED,
        completed_at=COMPLETED,
    )
    one = build_observation(run_id="run-1", **common)
    two = build_observation(run_id="run-2", **common)
    assert one["observationId"] != two["observationId"]


def _bundle(severity: Severity) -> FindingBundle:
    evidence = EvidenceRecord(
        evidence_id="ev-1",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="python.example",
        evidence_type="static-analysis",
        message="example evidence",
        locations=(SourceLocation("src/example.py", start_line=7),),
        severity=severity,
        confidence=Confidence.HIGH,
    )
    finding = Finding(
        finding_id="finding-1",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="python.example",
        canonical_rule_id="l9.example.rule",
        category="security",
        message="example finding",
        evidence_ids=("ev-1",),
        locations=(SourceLocation("src/example.py", start_line=7, end_line=7),),
        fingerprint="fingerprint-1",
        severity=severity,
        confidence=Confidence.HIGH,
    )
    classification = FindingClassification(
        finding_id="finding-1",
        mode=RuleMode.BLOCKING,
        resolution_status=ResolutionStatus.DEFAULTED,
        used_default=True,
    )
    return FindingBundle(
        SDK_version="2.0.0",
        generated_at="2026-08-21T20:00:00Z",
        snapshot=SnapshotDescriptor(
            snapshot_id="snapshot-1",
            repository_root=".",
            revision=REVISION,
            dirty=False,
        ),
        providers=(),
        evidence=(evidence,),
        findings=(finding,),
        classifications=(classification,),
        provider_failures=(),
        coverage=(),
    )


def test_mandatory_findings_projection_preserves_finding_and_not_policy_verdict() -> None:
    observation = project_mandatory_findings_observation(
        _bundle(Severity.HIGH),
        repository="Quantum-L9/example",
        configuration_digest=DIGEST,
        run_id="run-1",
        attempt=1,
        started_at=STARTED,
        completed_at=COMPLETED,
        mode="blocking",
        source_path="artifacts/l9/finding-bundle.json",
    )

    assert observation["check"]["id"] == "l9.mandatory-findings"
    assert observation["execution"]["status"] == "passed"
    assert observation["summary"]["findingCount"] == 1
    assert observation["findings"][0]["severity"] == "high"
    assert observation["findings"][0]["disposition"] == "open"
    assert observation["findings"][0]["location"]["path"] == "src/example.py"
    assert "verdict" not in observation
    validate_observation(observation)


def test_unknown_severity_is_not_silently_downgraded() -> None:
    with pytest.raises(ValueError, match="Assurance-compatible severity"):
        project_mandatory_findings_observation(
            _bundle(Severity.UNKNOWN),
            repository="Quantum-L9/example",
            configuration_digest=DIGEST,
            run_id="run-1",
            attempt=1,
            started_at=STARTED,
            completed_at=COMPLETED,
        )


def test_invalid_digest_and_unsupported_check_fail_closed() -> None:
    with pytest.raises(ValueError, match="sha256"):
        build_observation(
            producer_version="2.0.0",
            repository="Quantum-L9/example",
            revision=REVISION,
            check_id="l9.tests",
            configuration_digest="bad",
            run_id="run-1",
            attempt=1,
            status="passed",
            started_at=STARTED,
            completed_at=COMPLETED,
        )
    with pytest.raises(ValueError, match="unsupported observation check"):
        build_observation(
            producer_version="2.0.0",
            repository="Quantum-L9/example",
            revision=REVISION,
            check_id="consumer.custom-check",
            configuration_digest=DIGEST,
            run_id="run-1",
            attempt=1,
            status="passed",
            started_at=STARTED,
            completed_at=COMPLETED,
        )
