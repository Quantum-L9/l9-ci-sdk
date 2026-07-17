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
