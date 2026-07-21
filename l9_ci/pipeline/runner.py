"""Generic bounded-execution runner (DWA-002).

Chains a provider's bounded execution → failure classification → import →
report-shape validation → normalization, giving ``Provider.execute`` /
``Provider.execution_failure`` and ``ProviderExecutionRequest`` (timeout, output
limit, environment allowlist) a real production caller. Previously that
machinery existed and was unit-tested but was never invoked — scanners were run
in the workflow shell and the SDK only imported the raw report, so the bounded
controls protected nothing.

Any failure (timeout, output-limit, missing report, malformed report, bad exit)
becomes a structured ``ProviderFailure`` plus FAILED coverage, so a required
provider that fails execution drives the gate to INCOMPLETE (fail-closed).
"""

from __future__ import annotations
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    ProviderFailure,
    ProviderFailureType,
)
from l9_ci.providers import (
    Provider,
    ProviderExecutionRequest,
    ProviderNormalizationContext,
    ProviderNormalizationResult,
)


def _failed(
    provider: Provider,
    failures: tuple[ProviderFailure, ...],
) -> ProviderNormalizationResult:
    return ProviderNormalizationResult(
        evidence=(),
        findings=(),
        coverage=Coverage(
            provider_id=provider.metadata.provider_id,
            status=CoverageStatus.FAILED,
            files_considered=0,
            files_analyzed=0,
            limitations=(),
        ),
        failures=failures,
        limitations=tuple(failure.message for failure in failures),
    )


def _failure(
    provider: Provider,
    context: ProviderNormalizationContext,
    failure_type: ProviderFailureType,
    message: str,
) -> ProviderFailure:
    return ProviderFailure(
        provider_id=provider.metadata.provider_id,
        provider_version=context.provider_version,
        failure_type=failure_type,
        message=message,
        required=context.required,
        fatal=context.required,
    )


def execute_and_normalize(
    provider: Provider,
    *,
    request: ProviderExecutionRequest,
    context: ProviderNormalizationContext,
) -> ProviderNormalizationResult:
    """Run bounded execution and normalize, or return a failed result."""
    result = provider.execute(request)
    failure = provider.execution_failure(
        result,
        required=context.required,
        provider_version=context.provider_version,
    )
    if failure is not None:
        return _failed(provider, (failure,))
    if result.report_path is None:
        return _failed(
            provider,
            (
                _failure(
                    provider,
                    context,
                    ProviderFailureType.REPORT_MISSING,
                    "provider produced no report",
                ),
            ),
        )
    report = provider.import_report(result.report_path)
    shape_errors = provider.validate_report_shape(report)
    if shape_errors:
        return _failed(
            provider,
            (
                _failure(
                    provider,
                    context,
                    ProviderFailureType.REPORT_MALFORMED,
                    "; ".join(shape_errors),
                ),
            ),
        )
    return provider.normalize(report, context)
