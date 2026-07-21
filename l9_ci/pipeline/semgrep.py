"""End-to-end Semgrep report to canonical bundle pipeline."""

from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
from l9_ci.artifacts import validate_bundle, write_bundle_atomic
from l9_ci.contracts import (
    FindingBundle,
    FindingClassification,
    ProviderRun,
    SnapshotDescriptor,
)
from l9_ci.identity import RuleIdentityMap
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
from .lifecycle import resolve_import_provider
from .runner import execute_and_normalize


class UnsupportedProviderVersionError(ValueError):
    """Raised when a supplied provider version fails the version policy.

    Distinct from generic ValueError so the CLI can map it to the
    INCOMPATIBLE_VERSION (exit 8) contract without fragile message matching.
    """


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
    # SDK-owned bounded execution (DWA-002). When execute is True, the provider
    # is run through the generic runner (which writes report_path) instead of
    # importing a pre-produced report. Default False keeps the import-only path.
    execute: bool = False
    timeout_seconds: int = 300
    output_size_limit_bytes: int = 50_000_000
    execution_arguments: tuple[str, ...] = ()
    # Trusted canonical-rule -> remediation-class mapping (DWA-007). When set,
    # findings whose canonical rule id is mapped get a remediation_class, so the
    # projection can emit autofix candidates. Omitted -> no autofix classes.
    remediation_map_path: Path | None = None


@dataclass(frozen=True, slots=True)
class SemgrepPipelineResult:
    bundle: FindingBundle
    output_path: Path


def run_semgrep_pipeline(
    request: SemgrepPipelineRequest,
) -> SemgrepPipelineResult:
    identity_map = (
        RuleIdentityMap.load(request.identity_map_path)
        if request.identity_map_path
        else None
    )
    # Enforce the report-producing provider version before normalization. An
    # unsupported (or unparseable) version must not reach a canonical bundle.
    # This validates the version that generated the imported report, which is
    # independent of any locally installed Semgrep executable.
    if request.provider_version is not None:
        try:
            require_supported_semgrep_version(request.provider_version)
        except ValueError as exc:
            raise UnsupportedProviderVersionError(str(exc)) from exc
    # Resolve the provider through the registry-backed lifecycle seam so the
    # canonical import path exercises capability detection and execution-profile
    # selection rather than constructing the provider ad hoc.
    provider = resolve_import_provider(
        "semgrep",
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
    context = ProviderNormalizationContext(
        snapshot_id=snapshot_id,
        repository_root=request.repository_root,
        provider_version=request.provider_version,
        required=request.required,
    )
    if request.execute:
        # SDK-owned bounded execution: run the provider through the generic
        # runner (validate -> execute -> classify -> import -> normalize)
        # instead of importing a pre-produced report (DWA-002).
        execution_request = ProviderExecutionRequest(
            repository_root=request.repository_root,
            output_path=request.report_path,
            timeout_seconds=request.timeout_seconds,
            output_size_limit_bytes=request.output_size_limit_bytes,
            arguments=request.execution_arguments,
        )
        normalization = execute_and_normalize(
            provider, request=execution_request, context=context
        )
    else:
        validate_report_size(request.report_path, request.limits)
        report = provider.import_report(request.report_path)
        normalization = provider.normalize(report, context)
    validate_record_counts(
        finding_count=len(normalization.findings),
        evidence_count=len(normalization.evidence),
        limits=request.limits,
    )
    if request.strict:
        unresolved_identity = tuple(
            finding.finding_id
            for finding in normalization.findings
            if finding.canonical_rule_id is None
        )
        if unresolved_identity:
            joined = ", ".join(sorted(unresolved_identity))
            raise ValueError(
                f"strict identity resolution failed for findings: {joined}"
            )
    classifications: tuple[FindingClassification, ...] = ()
    if request.policy_path:
        policy = FindingPolicy.load(request.policy_path)
        classification_result = classify_findings(
            normalization.findings,
            policy,
            strict=request.strict,
        )
        classifications = classification_result.classifications
    elif request.strict and normalization.findings:
        raise ValueError("strict mode requires a policy for non-empty findings")
    # Assign trusted remediation classes after canonical identity resolution so
    # the projection can emit autofix candidates (DWA-007). No-op without a map.
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
                provider_version=request.provider_version,
                mode="import",
                required=request.required,
            ),
        ),
        evidence=normalization.evidence,
        findings=bundle_findings,
        classifications=classifications,
        provider_failures=normalization.failures,
        coverage=(normalization.coverage,),
        limitations=normalization.limitations,
    )
    # generated_at is explicit invocation provenance; override the wall-clock
    # default only when the caller supplied it (QA-003).
    if request.generated_at is not None:
        bundle = replace(bundle, generated_at=request.generated_at)
    validation = validate_bundle(bundle)
    validation.require_valid()
    validate_redaction(bundle.to_dict()).require_valid()
    write_bundle_atomic(bundle, request.output_path)
    return SemgrepPipelineResult(
        bundle=bundle,
        output_path=request.output_path,
    )
