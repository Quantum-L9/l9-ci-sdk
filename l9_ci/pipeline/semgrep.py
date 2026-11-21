"""End-to-end Semgrep report or bounded execution pipeline."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from l9_ci.artifacts import validate_bundle, write_bundle_atomic
from l9_ci.contracts import (
    Coverage,
    Finding,
    FindingBundle,
    FindingClassification,
    ProviderRun,
    SnapshotDescriptor,
    SourceLocation,
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

from .overlaps import supersede_findings
from .lifecycle import ProviderAcquisitionMode, resolve_provider
from .runner import execute_and_normalize


# Registry rule-ID prefixes that model one framework's conventions. A finding
# from such a rule applies only to a repository using that framework.
FRAMEWORK_RULE_PREFIXES: Mapping[str, tuple[str, ...]] = {
    "django": ("python.django.",),
}


def _framework_applicability(
    findings: tuple[Finding, ...], detected: Mapping[str, bool | None]
) -> tuple[tuple[Finding, ...], tuple[str, ...]]:
    """Withhold findings of rules whose framework is known to be absent.

    Only an explicit ``False`` withholds. ``None`` (detection could not read a
    candidate file) and a framework the mapping does not name keep the finding.
    """
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
        if framework is None or detected.get(framework) is not False:
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
    # Registry rules a packaged L9 rule supersedes in this composition; their
    # findings are withdrawn only where the L9 rule reported the same call.
    # Registry rule ID -> packaged L9 rule ID (rule-overlaps.yaml).
    superseded_rules: Mapping[str, str] = field(default_factory=dict)
    # The declared scope record (``l9.semgrep-scan-scope/v1``) of a required
    # run. When set it is carried into the bundle's coverage with the
    # provider's own ``paths.scanned``, so scope evidence travels with the
    # findings it qualifies.
    scan_scope: Mapping[str, Any] | None = None
    # Frameworks detected in the repository under analysis (name -> detected).
    # When set, a finding from a framework-scoped registry rule whose framework
    # is not detected is withheld: its evidence is kept and the bundle records
    # why (FRAMEWORK_RULE_PREFIXES).
    detected_frameworks: Mapping[str, bool | None] | None = None


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


def _paths_scanned(report_path: Path) -> dict[str, Any] | None:
    """Summarise the report's ``paths.scanned``; ``None`` when it is unreadable.

    A missing report, a non-object payload or a ``paths.scanned`` that is not a
    list of strings yields ``None``: the bundle then states that the scanned
    inventory is unknown rather than inventing one. Coverage status is decided
    by the provider, not here.
    """
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    paths = report.get("paths") if isinstance(report, dict) else None
    scanned = paths.get("scanned") if isinstance(paths, dict) else None
    if not isinstance(scanned, list) or not all(
        isinstance(path, str) for path in scanned
    ):
        return None
    normalized = sorted({SourceLocation(path).normalized_path for path in scanned})
    digest = hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()
    return {"count": len(normalized), "sha256": digest}


def _with_scan_scope(
    coverage: Coverage, scan_scope: Mapping[str, Any], report_path: Path
) -> Coverage:
    return replace(
        coverage,
        scan_scope={
            "declared": dict(scan_scope),
            "paths_scanned": _paths_scanned(report_path),
        },
    )


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
    findings = normalization.findings
    limitations = normalization.limitations
    if request.superseded_rules:
        findings, superseded = supersede_findings(findings, request.superseded_rules)
        limitations = tuple(sorted((*limitations, *superseded)))
    if request.strict:
        unresolved = tuple(
            finding for finding in findings if finding.canonical_rule_id is None
        )
        if unresolved:
            raise ValueError(describe_unresolved_identity(unresolved))

    classifications: tuple[FindingClassification, ...] = ()
    if request.policy_path:
        policy = FindingPolicy.load(request.policy_path)
        classifications = classify_findings(
            findings,
            policy,
            strict=request.strict,
        ).classifications
    elif request.strict and findings:
        raise ValueError("strict mode requires a policy for non-empty findings")

    bundle_findings = findings
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
        coverage=(
            normalization.coverage
            if request.scan_scope is None
            else _with_scan_scope(
                normalization.coverage, request.scan_scope, request.report_path
            ),
        ),
        limitations=tuple(sorted({*limitations, *framework_limitations})),
    )
    if request.generated_at is not None:
        bundle = replace(bundle, generated_at=request.generated_at)
    validation = validate_bundle(bundle)
    validation.require_valid()
    validate_redaction(bundle.to_dict()).require_valid()
    write_bundle_atomic(bundle, request.output_path)
    return SemgrepPipelineResult(bundle=bundle, output_path=request.output_path)
