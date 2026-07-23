"""Generic bounded provider execution and normalization runner."""

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
    limitations = tuple(failure.message for failure in failures)
    return ProviderNormalizationResult(
        evidence=(),
        findings=(),
        coverage=Coverage(
            provider_id=provider.metadata.provider_id,
            status=CoverageStatus.FAILED,
            files_considered=0,
            files_analyzed=0,
            limitations=limitations,
        ),
        failures=failures,
        limitations=limitations,
    )


def _failure(
    provider: Provider,
    context: ProviderNormalizationContext,
    failure_type: ProviderFailureType,
    message: str,
    *,
    diagnostics: dict[str, object] | None = None,
) -> ProviderFailure:
    return ProviderFailure(
        provider_id=provider.metadata.provider_id,
        provider_version=context.provider_version,
        failure_type=failure_type,
        message=message,
        required=context.required,
        fatal=context.required,
        diagnostics=diagnostics or {},
    )


def execute_and_normalize(
    provider: Provider,
    *,
    request: ProviderExecutionRequest,
    context: ProviderNormalizationContext,
) -> ProviderNormalizationResult:
    """Run detect/configure/execute/import/validate/normalize, failing closed."""
    if not provider.detect(request.repository_root):
        return _failed(
            provider,
            (
                _failure(
                    provider,
                    context,
                    ProviderFailureType.NOT_INSTALLED,
                    f"{provider.metadata.display_name} is not installed",
                ),
            ),
        )

    if context.provider_version is None:
        return _failed(
            provider,
            (
                _failure(
                    provider,
                    context,
                    ProviderFailureType.CONFIGURATION_ERROR,
                    f"{provider.metadata.display_name} version could not be detected",
                ),
            ),
        )

    configuration_errors = tuple(
        provider.validate_configuration(request.repository_root)
    )
    if configuration_errors:
        return _failed(
            provider,
            (
                _failure(
                    provider,
                    context,
                    ProviderFailureType.CONFIGURATION_ERROR,
                    f"{provider.metadata.display_name} configuration is invalid",
                    diagnostics={"errors": list(configuration_errors)},
                ),
            ),
        )

    try:
        result = provider.execute(request)
    except Exception as exc:  # provider process boundary; convert to contract failure
        return _failed(
            provider,
            (
                _failure(
                    provider,
                    context,
                    ProviderFailureType.EXECUTION_ERROR,
                    f"provider execution raised {type(exc).__name__}: {exc}",
                ),
            ),
        )

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

    try:
        report = provider.import_report(result.report_path)
    except ValueError as exc:
        return _failed(
            provider,
            (
                _failure(
                    provider,
                    context,
                    ProviderFailureType.REPORT_MALFORMED,
                    str(exc),
                ),
            ),
        )
    shape_errors = tuple(provider.validate_report_shape(report))
    if shape_errors:
        return _failed(
            provider,
            (
                _failure(
                    provider,
                    context,
                    ProviderFailureType.REPORT_MALFORMED,
                    "provider report failed structural validation",
                    diagnostics={"errors": list(shape_errors)},
                ),
            ),
        )
    try:
        return provider.normalize(report, context)
    except Exception as exc:
        return _failed(
            provider,
            (
                _failure(
                    provider,
                    context,
                    ProviderFailureType.NORMALIZATION_ERROR,
                    f"normalization raised {type(exc).__name__}: {exc}",
                ),
            ),
        )
