import json
from pathlib import Path
import pytest
from l9_ci.contracts import (
    CoverageStatus,
    FindingBundle,
    ProviderRun,
    Severity,
    SnapshotDescriptor,
)
from l9_ci.gates import GateStatus, evaluate_gate
from l9_ci.providers import ProviderNormalizationContext
from l9_ci.providers.semgrep import SemgrepProvider

FIXTURE = Path("tests/fixtures/semgrep/results.json")
FIXTURE_ROOT = Path("tests/fixtures/semgrep")


def _normalize(fixture_name: str, *, required: bool):
    provider = SemgrepProvider()
    report = json.loads((FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))
    return provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=Path(".").resolve(),
            provider_version="1.100.0",
            required=required,
        ),
    )


def _gate_status_for_required(normalization) -> GateStatus:
    bundle = FindingBundle(
        SDK_version="1.0.0",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor("snapshot-1", "."),
        providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", True),),
        evidence=normalization.evidence,
        findings=normalization.findings,
        classifications=(),
        provider_failures=normalization.failures,
        coverage=(normalization.coverage,),
    )
    return evaluate_gate(bundle).status


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


# --- AUD-004 / QA-002: unverified or zero-result coverage must not be COMPLETE


@pytest.mark.parametrize(
    "fixture_name",
    [
        "zero-findings-no-paths.json",
        "zero-findings-empty-scanned.json",
        "skipped-only.json",
    ],
)
def test_zero_result_without_verified_scan_is_partial(fixture_name: str) -> None:
    result = _normalize(fixture_name, required=False)
    assert result.coverage.status is CoverageStatus.PARTIAL
    assert result.coverage.files_analyzed == 0
    assert result.coverage.limitations  # provenance is recorded


def test_skipped_only_counts_skipped_as_considered_not_analyzed() -> None:
    result = _normalize("skipped-only.json", required=False)
    assert result.coverage.files_considered == 2
    assert result.coverage.files_analyzed == 0


def test_report_errors_produce_partial_and_failure() -> None:
    result = _normalize("report-errors.json", required=False)
    assert result.coverage.status is CoverageStatus.PARTIAL
    assert result.failures != ()


@pytest.mark.parametrize(
    "fixture_name",
    [
        "zero-findings-no-paths.json",
        "zero-findings-empty-scanned.json",
        "skipped-only.json",
        "report-errors.json",
    ],
)
def test_required_provider_zero_result_gates_incomplete(fixture_name: str) -> None:
    # End-to-end: an unverified/zero-result report from a REQUIRED provider must
    # drive the gate to INCOMPLETE, never PASS.
    normalization = _normalize(fixture_name, required=True)
    assert _gate_status_for_required(normalization) is GateStatus.INCOMPLETE
