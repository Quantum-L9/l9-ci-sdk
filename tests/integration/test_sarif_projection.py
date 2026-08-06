"""Deterministic canonical-bundle -> SARIF projection tests."""

from __future__ import annotations

import pytest

from l9_ci.artifacts import canonical_json_bytes
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    EvidenceRecord,
    Finding,
    FindingBundle,
    ProviderRun,
    Severity,
    SnapshotDescriptor,
    SourceLocation,
)
from l9_ci.integration import project_sarif_log


def _finding(
    finding_id: str,
    *,
    canonical_rule_id: str | None,
    severity: Severity | None,
    path: str = "src/example.py",
    start_line: int | None = 1,
) -> Finding:
    location = SourceLocation(path, start_line=start_line)
    return Finding(
        finding_id=finding_id,
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="rule.one",
        canonical_rule_id=canonical_rule_id,
        category="security",
        message="Example finding message",
        evidence_ids=(f"evidence-{finding_id}",),
        locations=(location,),
        fingerprint=f"fingerprint-{finding_id}",
        severity=severity,
    )


def _bundle(findings: tuple[Finding, ...]) -> FindingBundle:
    evidence = tuple(
        EvidenceRecord(
            evidence_id=f"evidence-{finding.finding_id}",
            snapshot_id="snapshot-1",
            provider_id="semgrep",
            provider_rule_id="rule.one",
            evidence_type="static-analysis-match",
            message="Example",
            locations=finding.locations,
        )
        for finding in findings
    )
    return FindingBundle(
        SDK_version="1.2.3",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor(snapshot_id="snapshot-1", repository_root="."),
        providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", True),),
        evidence=evidence,
        findings=findings,
        classifications=(),
        provider_failures=(),
        coverage=(Coverage("semgrep", CoverageStatus.COMPLETE, 1, 1, ()),),
    )


def test_projects_minimal_sarif_shape() -> None:
    log = project_sarif_log(
        _bundle((_finding("f-1", canonical_rule_id="L9-A", severity=Severity.HIGH),)),
        strict=True,
    )
    assert log["version"] == "2.1.0"
    assert len(log["runs"]) == 1
    driver = log["runs"][0]["tool"]["driver"]
    assert driver["name"] == "l9-ci-sdk"
    assert driver["version"] == "1.2.3"  # sourced from the bundle SDK_version
    results = log["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "L9-A"
    assert results[0]["message"]["text"] == "Example finding message"
    assert results[0]["partialFingerprints"]["l9/fingerprint"] == "fingerprint-f-1"


def test_ruleid_falls_back_to_provider_rule_id_when_uncanonical() -> None:
    log = project_sarif_log(
        _bundle((_finding("f-1", canonical_rule_id=None, severity=Severity.LOW),)),
        strict=False,
    )
    assert log["runs"][0]["results"][0]["ruleId"] == "rule.one"


def test_severity_maps_to_sarif_level() -> None:
    cases = {
        Severity.CRITICAL: "error",
        Severity.HIGH: "error",
        Severity.MEDIUM: "warning",
        Severity.LOW: "note",
        Severity.INFORMATIONAL: "note",
        Severity.UNKNOWN: "warning",
    }
    for severity, expected in cases.items():
        log = project_sarif_log(
            _bundle((_finding("f-1", canonical_rule_id="L9-A", severity=severity),)),
            strict=True,
        )
        assert log["runs"][0]["results"][0]["level"] == expected, severity


def test_results_are_ordered_by_finding_id_and_rules_sorted() -> None:
    findings = (
        _finding("f-2", canonical_rule_id="L9-Z", severity=Severity.HIGH),
        _finding("f-1", canonical_rule_id="L9-A", severity=Severity.LOW),
    )
    log = project_sarif_log(_bundle(findings), strict=True)
    result_rules = [r["ruleId"] for r in log["runs"][0]["results"]]
    assert result_rules == ["L9-A", "L9-Z"]  # ordered by finding_id (f-1, f-2)
    driver_rules = [rule["id"] for rule in log["runs"][0]["tool"]["driver"]["rules"]]
    assert driver_rules == ["L9-A", "L9-Z"]  # sorted rule ids


def test_projection_is_byte_deterministic() -> None:
    bundle = _bundle(
        (
            _finding("f-2", canonical_rule_id="L9-Z", severity=Severity.HIGH),
            _finding("f-1", canonical_rule_id="L9-A", severity=Severity.LOW),
        )
    )
    first = canonical_json_bytes(project_sarif_log(bundle, strict=True))
    second = canonical_json_bytes(project_sarif_log(bundle, strict=True))
    assert first == second


def test_region_maps_line_and_omits_missing_coordinates() -> None:
    log = project_sarif_log(
        _bundle((_finding("f-1", canonical_rule_id="L9-A", severity=Severity.HIGH),)),
        strict=True,
    )
    physical = log["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert physical["artifactLocation"]["uri"] == "src/example.py"
    assert physical["region"] == {"startLine": 1}


def test_strict_rejects_findings_without_canonical_identity() -> None:
    bundle = _bundle((_finding("f-1", canonical_rule_id=None, severity=Severity.HIGH),))
    with pytest.raises(ValueError, match="canonical identity"):
        project_sarif_log(bundle, strict=True)
