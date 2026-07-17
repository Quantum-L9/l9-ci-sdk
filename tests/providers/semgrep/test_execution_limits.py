from pathlib import Path
from l9_ci.contracts import ProviderFailureType
from l9_ci.providers import ProviderExecutionResult
from l9_ci.providers.semgrep import SemgrepProvider


def test_timeout_maps_to_structured_failure() -> None:
    provider = SemgrepProvider()
    failure = provider.execution_failure(
        ProviderExecutionResult(
            exit_code=-1,
            report_path=None,
            stdout="",
            stderr="",
            timed_out=True,
        ),
        required=True,
        provider_version="1.100.0",
    )
    assert failure is not None
    assert failure.failure_type is ProviderFailureType.TIMEOUT
    assert failure.fatal


def test_output_limit_maps_to_structured_failure(
    tmp_path: Path,
) -> None:
    provider = SemgrepProvider()
    failure = provider.execution_failure(
        ProviderExecutionResult(
            exit_code=1,
            report_path=tmp_path / "results.json",
            stdout="",
            stderr="",
            output_limit_exceeded=True,
        ),
        required=False,
        provider_version="1.100.0",
    )
    assert failure is not None
    assert failure.failure_type is ProviderFailureType.OUTPUT_LIMIT_EXCEEDED
    assert not failure.fatal
