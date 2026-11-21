"""End-to-end Semgrep report or bounded execution pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from l9_ci.artifacts import validate_bundle, write_bundle_atomic
from l9_ci.contracts import (
    Finding,
    FindingBundle,
    FindingClassification,
    ProviderRun,
    SnapshotDescriptor,
)
from l9_ci.identity import RuleIdentityMap, describe_unresolved_identity
from l9_ci.integration import (
    OperationalLimits,
    validate_record_counts,
    validate_redaction,
    validate_report_size,
)
from l9_ci.policy import FindingPolicy, classify_findings
from l9_ci.policy.remediation import RemediationMap, apply_remediation_classes
from l9_ci.providers import ProviderExecutionRequest, ProviderNormalizationContext
from l9_ci.providers.semgrep import require_supported_semgrep_version
from l9_ci.repository import build_repository_snapshot

from .lifecycle import ProviderAcquisitionMode, resolve_provider
from .runner import execute_and_normalize


# Registry rule-ID prefixes that model one framework's conventions. A finding
# from such a rule applies only to a repository using that framework.
FRAMEWORK_RULE_PREFIXES: Mapping[str, tuple[str, ...]] = {
    "django": ("python.django.",),
}


def _framework_applicability(
    findings: tuple[Finding, ...], detected: Mapping[str, bool]
) -> tuple[tuple[Finding, ...], tuple[str, ...]]:
    """Withhold findings of rules whose framework is not in the repository."""
    kept: list[Finding] = []
    withheld: dict[tuple[str, str], list[str]] = {}
    for finding in findings:
        framework = next(
            (
                name
                for name, prefixes in FRAMEWORK_RULE_PREFIXES.items()
                if finding.provider_rule_id.startswith(prefixes)
            ),
            None,
        )
        if framework is None or detected.get(framework, False):
            kept.append(finding)
            continue
        location = finding.locations[0] if finding.locations else None
        where = f"{location.normalized_path}:{location.start_line}" if location else "?"
        withheld.setdefault((framework, finding.provider_rule_id), []).append(where)
    limitations = tuple(
        f"framework rule {rule} not applicable: {framework} is not detected in "
        f"this repository; {len(where)} finding(s) withheld, evidence kept "
        f"({', '.join(sorted(where))})"
        for (framework, rule), where in sorted(withheld.items())
    )
    return tuple(kept), limitations


class UnsupportedProviderVersionError(ValueError):
    """Raised when supplied or detected Semgrep provenance is unsupported."""


@dataclass(frozen=True, slots=True)
class SemgrepPipelineRequest:
    report_path: Path
    repository_root: Path
    SDK_version: str
    output_path: Path
    snapshot_id: str | None = None
    provider_version: str | None = None
    identity_map_path: Path | None = None
    policy_path: Path | None = None
    strict: bool = False
    required: bool = False
    generated_at: str | None = None
    revision: str | None = None
    dirty: bool | None = None
    derive_snapshot: bool = False
    limits: OperationalLimits = OperationalLimits()
    execute: bool = False
    timeout_seconds: int = 300
    output_size_limit_bytes: int = 50_000_000
    execution_arguments: tuple[str, ...] = ()
    execution_targets: tuple[str, ...] = ()
    remediation_map_path: Path | None = None
    # Frameworks detected in the repository under analysis (name -> detected).
    # When set, a finding from a framework-scoped registry rule whose framework
    # is not detected is withheld: its evidence is kept and the bundle records
    # why (FRAMEWORK_RULE_PREFIXES).
    detected_frameworks: Mapping[str, bool] | None = None


@dataclass(frozen=True, slots=True)
class SemgrepPipelineResult:
    bundle: FindingBundle
    output_path: Path


def _supported_version(raw: str) -> str:
    try:
        require_supported_semgrep_version(raw)
    except ValueError as exc:
        raise UnsupportedProviderVersionError(str(exc)) from exc
    return raw.strip()


def run_semgrep_pipeline(request: SemgrepPipelineRequest) -> SemgrepPipelineResult:
    identity_map = (
        RuleIdentityMap.load(request.identity_map_path)
        if request.identity_map_path
        else None
    )
    mode = (
        ProviderAcquisitionMode.EXECUTE
        if request.execute
        else ProviderAcquisitionMode.IMPORT
    )
    provider = resolve_provider(
        "semgrep",
        mode=mode,
        repository_root=request.repository_root,
        identity_map=identity_map,
    )

    repository_snapshot = None
    if request.derive_snapshot:
        repository_snapshot = build_repository_snapshot(request.repository_root)
    snapshot_id = request.snapshot_id
    if repository_snapshot is not None:
        snapshot_id = repository_snapshot.snapshot_id
    if not snapshot_id:
        raise ValueError("snapshot_id is required unless derive_snapshot is enabled")

    if request.execute:
        detected_version = provider.detect_version()
        provider_version = (
            _supported_version(detected_version)
            if detected_version is not None
            else None
        )
    else:
        if request.provider_version is None or not request.provider_version.strip():
            raise ValueError(
                "provider_version is required when importing a Semgrep report"
            )
        provider_version = _supported_version(request.provider_version)

    context = ProviderNormalizationContext(
        snapshot_id=snapshot_id,
        repository_root=request.repository_root,
        provider_version=provider_version,
        required=request.required,
    )
    if request.execute:
        normalization = execute_and_normalize(
            provider,
            request=ProviderExecutionRequest(
                repository_root=request.repository_root,
                output_path=request.report_path,
                timeout_seconds=request.timeout_seconds,
                output_size_limit_bytes=request.output_size_limit_bytes,
                arguments=tuple(request.execution_arguments),
                targets=tuple(request.execution_targets),
            ),
            context=context,
        )
    else:
        validate_report_size(request.report_path, request.limits)
        report = provider.import_report(request.report_path)
        shape_errors = tuple(provider.validate_report_shape(report))
        if shape_errors:
            raise ValueError(
                "Semgrep report failed structural validation: "
                + "; ".join(shape_errors)
            )
        normalization = provider.normalize(report, context)

    framework_limitations: tuple[str, ...] = ()
    if request.detected_frameworks is not None:
        applicable, framework_limitations = _framework_applicability(
            normalization.findings, request.detected_frameworks
        )
        normalization = replace(normalization, findings=applicable)

    validate_record_counts(
        finding_count=len(normalization.findings),
        evidence_count=len(normalization.evidence),
        limits=request.limits,
    )
    if request.strict:
        unresolved = tuple(
            finding
            for finding in normalization.findings
            if finding.canonical_rule_id is None
        )
        if unresolved:
            raise ValueError(describe_unresolved_identity(unresolved))

    classifications: tuple[FindingClassification, ...] = ()
    if request.policy_path:
        policy = FindingPolicy.load(request.policy_path)
        classifications = classify_findings(
            normalization.findings,
            policy,
            strict=request.strict,
        ).classifications
    elif request.strict and normalization.findings:
        raise ValueError("strict mode requires a policy for non-empty findings")

    bundle_findings = normalization.findings
    if request.remediation_map_path is not None:
        remediation_map = RemediationMap.load(request.remediation_map_path)
        bundle_findings = apply_remediation_classes(bundle_findings, remediation_map)

    bundle = FindingBundle(
        SDK_version=request.SDK_version,
        snapshot=SnapshotDescriptor(
            snapshot_id=snapshot_id,
            repository_root=".",
            revision=request.revision,
            dirty=request.dirty,
        ),
        providers=(
            ProviderRun(
                provider_id="semgrep",
                adapter_version=provider.metadata.adapter_version,
                provider_version=provider_version,
                mode=mode.value,
                required=request.required,
            ),
        ),
        evidence=normalization.evidence,
        findings=bundle_findings,
        classifications=classifications,
        provider_failures=normalization.failures,
        coverage=(normalization.coverage,),
        limitations=tuple(sorted({*normalization.limitations, *framework_limitations})),
    )
    if request.generated_at is not None:
        bundle = replace(bundle, generated_at=request.generated_at)
    validation = validate_bundle(bundle)
    validation.require_valid()
    validate_redaction(bundle.to_dict()).require_valid()
    write_bundle_atomic(bundle, request.output_path)
    return SemgrepPipelineResult(bundle=bundle, output_path=request.output_path)
