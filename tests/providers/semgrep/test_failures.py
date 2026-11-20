import json
from pathlib import Path
from l9_ci.contracts import (
    CoverageStatus,
    ProviderFailureType,
)
from l9_ci.providers import ProviderNormalizationContext
from l9_ci.providers.semgrep import SemgrepProvider

FIXTURE_ROOT = Path("tests/fixtures/semgrep")


def test_malformed_report_becomes_structured_failure() -> None:
    provider = SemgrepProvider()
    report = json.loads((FIXTURE_ROOT / "malformed.json").read_text(encoding="utf-8"))
    result = provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=Path(".").resolve(),
            provider_version="fixture-version",
            required=True,
        ),
    )
    assert result.evidence == ()
    assert result.findings == ()
    assert result.coverage.status is CoverageStatus.FAILED
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.failure_type is ProviderFailureType.REPORT_MALFORMED
    assert failure.required
    assert failure.fatal


def test_report_errors_produce_partial_coverage() -> None:
    provider = SemgrepProvider()
    report = {
        "results": [],
        "errors": [{"type": "ParseError", "message": "Unable to parse one file."}],
    }
    result = provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=Path(".").resolve(),
            provider_version="fixture-version",
            required=False,
        ),
    )
    assert result.coverage.status is CoverageStatus.PARTIAL
    assert len(result.failures) == 1
    assert not result.failures[0].fatal


def _normalize_inline(report: dict, *, required: bool):
    provider = SemgrepProvider()
    return provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=Path(".").resolve(),
            provider_version="fixture-version",
            required=required,
        ),
    )


def test_warn_level_timeout_is_not_a_failure_but_coverage_is_partial() -> None:
    """A rule that timed out on a file never evaluated it (B5, 2026-11-20).

    Semgrep reports it at level=warn, so it stays non-fatal (no failure),
    but the file is not fully analyzed: coverage is PARTIAL and the
    limitation names the rule/file pair.
    """
    report = json.loads(
        (FIXTURE_ROOT / "report-error-warn.json").read_text(encoding="utf-8")
    )
    result = _normalize_inline(report, required=True)
    assert result.failures == ()
    assert result.coverage.status is CoverageStatus.PARTIAL
    assert result.coverage.files_considered == 1
    assert result.coverage.files_analyzed == 0
    assert (
        "incomplete analysis: rule "
        "python.lang.security.audit.dangerous-system-call-tainted-env-args "
        "did not finish on src/example.py (Timeout)"
    ) in result.coverage.limitations


def test_other_warn_level_errors_stay_limitations_with_complete_coverage() -> None:
    """Honour level=warn for everything that is not unfinished analysis."""
    report = json.loads(
        (FIXTURE_ROOT / "report-error-warn-parse.json").read_text(encoding="utf-8")
    )
    result = _normalize_inline(report, required=True)
    assert result.failures == ()
    assert result.coverage.status is CoverageStatus.COMPLETE
    assert any("Syntax error" in item for item in result.coverage.limitations)


def test_error_level_report_error_stays_fatal_when_required() -> None:
    report = json.loads(
        (FIXTURE_ROOT / "report-error-error.json").read_text(encoding="utf-8")
    )
    result = _normalize_inline(report, required=True)
    assert len(result.failures) == 1
    assert result.failures[0].fatal
    assert result.failures[0].diagnostics.get("semgrep_level") == "error"
    assert result.coverage.status is CoverageStatus.PARTIAL


def test_missing_level_report_error_stays_fail_closed() -> None:
    result = _normalize_inline(
        {
            "results": [],
            "errors": [{"message": "Semgrep timed out scanning src/large.py"}],
            "paths": {"scanned": ["src/example.py"], "skipped": []},
        },
        required=True,
    )
    assert len(result.failures) == 1
    assert result.failures[0].fatal
    assert result.coverage.status is CoverageStatus.PARTIAL
