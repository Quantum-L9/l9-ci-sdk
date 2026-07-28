import json
import shutil
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
from l9_ci.providers import (
    ProviderExecutionRequest,
    ProviderNormalizationContext,
)
from l9_ci.providers.semgrep import SemgrepProvider
from l9_ci.rulesets.semgrep import ruleset_dir

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


def test_build_execution_plan_uses_relative_scan_target() -> None:
    """The scan target must stay relative ("."), not the resolved absolute
    repository_root: execute() runs the command with cwd=repository_root,
    so an absolute target makes semgrep echo absolute paths in its JSON
    output, which l9_ci.contracts.source.normalize_repository_path then
    rejects as not repository-relative.
    """
    provider = SemgrepProvider()
    request = ProviderExecutionRequest(
        repository_root=Path("/tmp/some/absolute/repo/root"),
        output_path=Path("out.json"),
        timeout_seconds=60,
        output_size_limit_bytes=1_000_000,
        arguments=("--config", "p/python"),
    )
    plan = provider.build_execution_plan(request)
    assert str(request.repository_root) not in plan
    assert plan[-1] == "."


def test_execute_reports_relative_paths_for_real_semgrep_run(tmp_path: Path) -> None:
    """Regression test for the exact CI failure this fix addresses: a real
    semgrep invocation through execute()/build_execution_plan() must report
    finding paths relative to the scanned repository, not absolute paths.
    """
    if shutil.which("semgrep") is None:
        pytest.skip("semgrep executable not available on PATH")

    target_repo = tmp_path / "repo"
    target_repo.mkdir()
    (target_repo / "bad.py").write_text(
        "import subprocess\nsubprocess.run('echo hi', shell=True)\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "raw.json"
    provider = SemgrepProvider()
    # Use the packaged L9 ruleset (no network access required) instead of
    # a community registry ref, so this test is deterministic and offline.
    request = ProviderExecutionRequest(
        repository_root=target_repo.resolve(),
        output_path=output_path,
        timeout_seconds=60,
        output_size_limit_bytes=10_000_000,
        arguments=("--config", str(ruleset_dir("python"))),
    )
    result = provider.execute(request)
    assert result.report_path is not None
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    paths = [finding["path"] for finding in report.get("results", [])]
    assert paths, "expected semgrep to report at least one finding"
    for path in paths:
        assert not Path(path).is_absolute(), f"expected relative path, got {path!r}"

    normalization_result = provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=target_repo.resolve(),
            provider_version="fixture-version",
            required=False,
        ),
    )
    assert normalization_result.findings
    for finding in normalization_result.findings:
        for location in finding.locations:
            assert not Path(location.normalized_path).is_absolute()
