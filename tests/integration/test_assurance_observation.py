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
from l9_ci.integration.observation import _observation_id, _timestamp_errors

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


def test_mandatory_findings_projection_preserves_finding_and_not_policy_verdict() -> (
    None
):
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


def _valid_observation() -> dict:
    return build_observation(
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


def test_validation_recomputes_the_content_address() -> None:
    # A stored or transported observation whose payload was edited keeps a
    # well-formed observationId. Schema validation alone cannot see that, so
    # validate_observation must recompute the address and reject the mismatch.
    payload = _valid_observation()
    validate_observation(payload)

    tampered = dict(payload)
    tampered["execution"] = dict(payload["execution"]) | {"status": "failed"}
    with pytest.raises(ValueError, match="does not match the content address"):
        validate_observation(tampered)


def test_validation_rejects_a_reused_identity_from_another_observation() -> None:
    first = _valid_observation()
    second = build_observation(
        producer_version="2.0.0",
        repository="Quantum-L9/example",
        revision=REVISION,
        check_id="l9.lint",
        configuration_digest=DIGEST,
        run_id="12345",
        attempt=1,
        status="passed",
        started_at=STARTED,
        completed_at=COMPLETED,
    )
    assert first["observationId"] != second["observationId"]

    forged = dict(second)
    forged["observationId"] = first["observationId"]
    with pytest.raises(ValueError, match="does not match the content address"):
        validate_observation(forged)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-08-21",  # date only
        "2026-08-21T20:00Z",  # no seconds
        "2026-08-21T20:00:00",  # no offset
        "2026-13-21T20:00:00Z",  # month 13
        "2026-02-30T20:00:00Z",  # not a real calendar day
        "not-a-timestamp",
    ],
)
def test_validation_rejects_malformed_timestamps(timestamp: str) -> None:
    # These must be rejected on a BASE install. `format: date-time` is
    # annotation-only unless jsonschema has a registered date-time checker, and
    # that library (rfc3339-validator) ships only in the `ci` extra -- which the
    # test environment happens to have, so asserting through validate_observation
    # alone would pass here for the wrong reason and still admit malformed
    # timestamps in production. _timestamp_errors is the check that does not
    # depend on what is installed, so assert on it directly.
    payload = _valid_observation()
    mutated = dict(payload)
    mutated["execution"] = dict(payload["execution"]) | {"startedAt": timestamp}

    errors = _timestamp_errors(mutated)
    assert errors, f"{timestamp!r} was accepted as an RFC3339 date-time"
    assert "startedAt" in errors[0]

    # End-to-end it must also fail, by whichever path fires first.
    mutated["observationId"] = _observation_id(
        {key: value for key, value in mutated.items() if key != "observationId"}
    )
    with pytest.raises(ValueError):
        validate_observation(mutated)


def test_validation_accepts_well_formed_rfc3339_offsets() -> None:
    # The guard above must not reject legitimate timestamps.
    for timestamp in (
        "2026-08-21T20:00:00Z",
        "2026-08-21T20:00:00.123456Z",
        "2026-08-21T20:00:00+02:00",
        "2026-08-21T20:00:00-07:30",
    ):
        payload = _valid_observation()
        mutated = dict(payload)
        mutated["execution"] = dict(payload["execution"]) | {"startedAt": timestamp}
        assert _timestamp_errors(mutated) == []


def test_validation_rejects_a_non_sdk_producer() -> None:
    # The protocol defines the producer as exactly l9-ci-sdk; a syntactically
    # valid impostor must not pass the SDK's own public validator.
    payload = _valid_observation()
    forged = dict(payload)
    forged["producer"] = dict(payload["producer"]) | {"id": "consumer.fake"}
    with pytest.raises(ValueError, match="schema validation failed"):
        validate_observation(forged)


def test_projection_attributes_the_running_sdk_not_the_bundle() -> None:
    # A bundle written by an older SDK must not yield an observation claiming
    # that older SDK produced it; the bundle version stays on its artifact.
    from l9_ci import __version__

    bundle = _bundle(Severity.HIGH)
    older = FindingBundle(
        SDK_version="1.2.3",
        generated_at=bundle.generated_at,
        snapshot=bundle.snapshot,
        providers=bundle.providers,
        evidence=bundle.evidence,
        findings=bundle.findings,
        classifications=bundle.classifications,
        provider_failures=bundle.provider_failures,
        coverage=bundle.coverage,
    )
    payload = project_mandatory_findings_observation(
        older,
        repository="Quantum-L9/example",
        configuration_digest=DIGEST,
        run_id="12345",
        attempt=1,
        started_at=STARTED,
        completed_at=COMPLETED,
    )
    assert payload["producer"]["version"] == __version__
    assert payload["artifacts"][0]["sdkVersion"] == "1.2.3"


def test_summary_category_counts_must_sum_to_finding_count() -> None:
    """Counts without findings are unrepresentable, so refuse to build them.

    Assurance requires the summary to describe the findings array on both
    axes -- `findingCount == len(findings)` and
    `findingCount == error + warning + informational`. The builder enforced
    only the first, so `observation build --check-id l9.lint --error-count 7`
    produced a well-formed observation that Assurance rejected on arrival with
    EVIDENCE_SCHEMA_INVALID. The defect surfaced one repository away from the
    caller that caused it; this keeps it here.
    """
    with pytest.raises(ValueError, match="must sum to finding_count"):
        build_observation(
            producer_version="2.0.0",
            repository="Quantum-L9/example",
            revision=REVISION,
            check_id="l9.lint",
            configuration_digest=DIGEST,
            run_id="run-1",
            attempt=1,
            status="failed",
            started_at=STARTED,
            completed_at=COMPLETED,
            error_count=7,
        )


def test_a_failed_outcome_with_zero_counts_is_representable() -> None:
    """The guard must not remove the way a caller reports a plain failure.

    A check with no per-finding detail reports its outcome through the
    execution status, and Assurance evaluates that status: a `failed` l9.lint
    observation yields `FAIL - L9.CI.LINT; l9.lint positively reported
    failure`. If this shape were refused too, the guard would have taken the
    signal with the defect.
    """
    observation = build_observation(
        producer_version="2.0.0",
        repository="Quantum-L9/example",
        revision=REVISION,
        check_id="l9.lint",
        configuration_digest=DIGEST,
        run_id="run-1",
        attempt=1,
        status="failed",
        started_at=STARTED,
        completed_at=COMPLETED,
    )
    assert observation["execution"]["status"] == "failed"
    assert observation["summary"] == {
        "findingCount": 0,
        "errorCount": 0,
        "warningCount": 0,
        "informationalCount": 0,
    }


def test_counts_that_match_their_findings_are_accepted() -> None:
    """The guard must not block a legitimate summary that does describe findings.

    Severity vocabulary and count categories are deliberately different axes:
    `critical`/`high` tally into errorCount, `medium`/`low` into warningCount,
    `informational` into informationalCount -- the mapping
    `project_mandatory_findings` applies.
    """
    findings = [
        {
            "findingId": "fn_1",
            "ruleId": "L9-EXAMPLE",
            "severity": "critical",
            "message": "example",
            "disposition": "open",
        },
        {
            "findingId": "fn_2",
            "ruleId": "L9-EXAMPLE",
            "severity": "medium",
            "message": "example",
            "disposition": "open",
        },
    ]
    observation = build_observation(
        producer_version="2.0.0",
        repository="Quantum-L9/example",
        revision=REVISION,
        check_id="l9.mandatory-findings",
        configuration_digest=DIGEST,
        run_id="run-1",
        attempt=1,
        status="passed",
        started_at=STARTED,
        completed_at=COMPLETED,
        finding_count=2,
        error_count=1,
        warning_count=1,
        findings=findings,
    )
    assert observation["summary"]["findingCount"] == 2
