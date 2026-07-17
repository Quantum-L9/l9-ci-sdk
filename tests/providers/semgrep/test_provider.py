import json
from pathlib import Path
from l9_ci.contracts import (
    CoverageStatus,
    Severity,
)
from l9_ci.providers import ProviderNormalizationContext
from l9_ci.providers.semgrep import SemgrepProvider

FIXTURE = Path("tests/fixtures/semgrep/results.json")


def test_provider_preserves_native_rule_ids() -> None:
    provider = SemgrepProvider()
    report = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=Path(".").resolve(),
            provider_version="fixture-version",
            required=False,
        ),
    )
    assert {finding.provider_rule_id for finding in result.findings} == {
        "python.lang.security.audit.exec-used.exec-used",
        "python.lang.correctness.useless-comparison.useless-comparison",
    }


def test_provider_does_not_invent_canonical_identity() -> None:
    provider = SemgrepProvider()
    report = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=Path(".").resolve(),
            provider_version="fixture-version",
            required=False,
        ),
    )
    assert all(finding.canonical_rule_id is None for finding in result.findings)
    assert all(
        "unresolved" in finding.attributes["identity_resolution_status"]
        for finding in result.findings
    )


def test_provider_normalizes_severity() -> None:
    provider = SemgrepProvider()
    report = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=Path(".").resolve(),
            provider_version="fixture-version",
            required=False,
        ),
    )
    severities = {
        finding.provider_rule_id: finding.severity for finding in result.findings
    }
    assert severities["python.lang.security.audit.exec-used.exec-used"] is Severity.HIGH
    assert (
        severities["python.lang.correctness.useless-comparison.useless-comparison"]
        is Severity.MEDIUM
    )


def test_provider_reports_complete_coverage_without_errors() -> None:
    provider = SemgrepProvider()
    report = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=Path(".").resolve(),
            provider_version="fixture-version",
            required=False,
        ),
    )
    assert result.coverage.status is CoverageStatus.COMPLETE
    assert result.coverage.files_considered == 1
    assert result.coverage.files_analyzed == 1
    assert result.failures == ()
