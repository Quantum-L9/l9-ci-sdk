"""Generic bounded-execution runner tests (DWA-002).

Exercises the runner with a fake provider so the bounded-execution control flow
(execute → classify → import → shape-validate → normalize) is verified without a
real scanner binary. A required provider whose execution fails must yield FAILED
coverage plus a structured failure, so the gate goes INCOMPLETE.
"""

from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence
import pytest
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    ProviderFailure,
    ProviderFailureType,
)
from l9_ci.pipeline import execute_and_normalize
from l9_ci.providers import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderNormalizationContext,
    ProviderNormalizationResult,
)


class FakeProvider:
    def __init__(
        self,
        result: ProviderExecutionResult,
        *,
        report: Mapping[str, Any] | None = None,
        shape_errors: Sequence[str] = (),
        normalization: ProviderNormalizationResult | None = None,
    ) -> None:
        self._result = result
        self._report = report or {}
        self._shape_errors = shape_errors
        self._normalization = normalization

    @property
    def metadata(self) -> Any:
        return SimpleNamespace(provider_id="fake")

    def detect(self, repository_root: Path) -> bool:
        return True

    def detect_version(self) -> str | None:
        return "1.100.0"

    def validate_configuration(self, repository_root: Path) -> Sequence[str]:
        return ()

    def build_execution_plan(self, request: ProviderExecutionRequest) -> Sequence[str]:
        return ("fake",)

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        return self._result

    def execution_failure(
        self,
        result: ProviderExecutionResult,
        *,
        required: bool,
        provider_version: str | None,
    ) -> ProviderFailure | None:
        if result.timed_out:
            return ProviderFailure(
                provider_id="fake",
                failure_type=ProviderFailureType.TIMEOUT,
                message="timed out",
                required=required,
                fatal=required,
            )
        if result.output_limit_exceeded:
            return ProviderFailure(
                provider_id="fake",
                failure_type=ProviderFailureType.OUTPUT_LIMIT_EXCEEDED,
                message="output too large",
                required=required,
                fatal=required,
            )
        return None

    def import_report(self, report_path: Path) -> Mapping[str, Any]:
        return self._report

    def validate_report_shape(self, report: Mapping[str, Any]) -> Sequence[str]:
        return self._shape_errors

    def normalize(
        self,
        report: Mapping[str, Any],
        context: ProviderNormalizationContext,
    ) -> ProviderNormalizationResult:
        assert self._normalization is not None
        return self._normalization


def _context(required: bool = True) -> ProviderNormalizationContext:
    return ProviderNormalizationContext(
        snapshot_id="s1",
        repository_root=Path("."),
        provider_version="1.100.0",
        required=required,
    )


def _request(tmp_path: Path) -> ProviderExecutionRequest:
    return ProviderExecutionRequest(
        repository_root=tmp_path,
        output_path=tmp_path / "out.json",
        timeout_seconds=5,
        output_size_limit_bytes=1000,
    )


def test_execution_request_rejects_bad_bounds(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ProviderExecutionRequest(
            repository_root=tmp_path,
            output_path=tmp_path / "o.json",
            timeout_seconds=0,
            output_size_limit_bytes=1,
        )


def test_success_path_normalizes(tmp_path: Path) -> None:
    report_path = tmp_path / "out.json"
    report_path.write_text("{}", encoding="utf-8")
    normalization = ProviderNormalizationResult(
        evidence=(),
        findings=(),
        coverage=Coverage("fake", CoverageStatus.COMPLETE, 1, 1, ()),
    )
    provider = FakeProvider(
        ProviderExecutionResult(
            exit_code=0, report_path=report_path, stdout="", stderr=""
        ),
        normalization=normalization,
    )
    result = execute_and_normalize(
        provider, request=_request(tmp_path), context=_context()
    )
    assert result.coverage.status is CoverageStatus.COMPLETE


@pytest.mark.parametrize(
    "exec_result,expected_type",
    [
        (
            ProviderExecutionResult(
                exit_code=-1, report_path=None, stdout="", stderr="", timed_out=True
            ),
            ProviderFailureType.TIMEOUT,
        ),
        (
            ProviderExecutionResult(
                exit_code=0,
                report_path=None,
                stdout="",
                stderr="",
                output_limit_exceeded=True,
            ),
            ProviderFailureType.OUTPUT_LIMIT_EXCEEDED,
        ),
        (
            ProviderExecutionResult(
                exit_code=0, report_path=None, stdout="", stderr=""
            ),
            ProviderFailureType.REPORT_MISSING,
        ),
    ],
)
def test_execution_failures_are_failed_coverage(
    tmp_path: Path,
    exec_result: ProviderExecutionResult,
    expected_type: ProviderFailureType,
) -> None:
    provider = FakeProvider(exec_result)
    result = execute_and_normalize(
        provider, request=_request(tmp_path), context=_context(required=True)
    )
    assert result.coverage.status is CoverageStatus.FAILED
    assert result.failures[0].failure_type is expected_type
    assert result.failures[0].required is True


def test_malformed_report_is_failed(tmp_path: Path) -> None:
    report_path = tmp_path / "out.json"
    report_path.write_text("{}", encoding="utf-8")
    provider = FakeProvider(
        ProviderExecutionResult(
            exit_code=0, report_path=report_path, stdout="", stderr=""
        ),
        shape_errors=("results must be an array",),
    )
    result = execute_and_normalize(
        provider, request=_request(tmp_path), context=_context()
    )
    assert result.coverage.status is CoverageStatus.FAILED
    assert result.failures[0].failure_type is ProviderFailureType.REPORT_MALFORMED
