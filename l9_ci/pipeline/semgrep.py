"""End-to-end Semgrep report or bounded execution pipeline."""

from __future__ import annotations

import functools
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from l9_ci.artifacts import validate_bundle, write_bundle_atomic
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    Finding,
    FindingBundle,
    FindingClassification,
    ProviderFailure,
    ProviderFailureType,
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
from l9_ci.policy import (
    FindingPolicy,
    FindingWaiverLedger,
    apply_waivers,
    classify_findings,
)
from l9_ci.policy import source_sha256 as waiver_source_sha256
from l9_ci.policy.remediation import RemediationMap, apply_remediation_classes
from l9_ci.providers import (
    Provider,
    ProviderExecutionRequest,
    ProviderNormalizationContext,
)
from l9_ci.providers.semgrep import require_supported_semgrep_version
from l9_ci.contracts.subjects import subject_reason
from l9_ci.repository import build_repository_snapshot
from l9_ci.repository.git import resolve_commit, tracked_changes

from .baseline import apply_baseline
from .overlaps import supersede_findings
from .precision import withhold_declared_non_security
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
    # Central finding waivers (l9.finding-waivers/v1). Applied after policy
    # classification, for ``repository`` on day ``waiver_date``.
    waivers_path: Path | None = None
    repository: str | None = None
    waiver_date: date | None = None
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
    # Registry rule ID -> keyword (rule-precision.yaml, ADR 0024): a finding of
    # that rule is withheld where its call passes ``keyword=False`` literally.
    precision_keywords: Mapping[str, str] = field(default_factory=dict)
    # A baseline commit (ADR 0023): the scan runs a second time with Semgrep's
    # ``--baseline-commit`` and each finding is classified new, pre-existing or
    # unknown. Requires execute mode and a finding policy.
    baseline_commit: str | None = None


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


_BASELINE_COMMIT = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")


def _baseline_new_fingerprints(
    provider: Provider,
    request: SemgrepPipelineRequest,
    context: ProviderNormalizationContext,
) -> tuple[frozenset[str] | None, str | None]:
    """Run the baseline scan; the fingerprints it reports, or why it cannot.

    Fails closed: an unresolvable commit, tracked changes in the working tree
    (Semgrep would compare them against the baseline without aborting), and a
    baseline scan that failed or did not complete all return ``None``.
    """
    assert request.baseline_commit is not None
    root = request.repository_root
    resolved = resolve_commit(root, request.baseline_commit)
    if resolved is None:
        return None, (
            f"commit {request.baseline_commit} is not in this repository "
            "(unknown, or absent from a shallow clone)"
        )
    if resolved != request.baseline_commit:
        return None, (
            f"{request.baseline_commit} resolves to a different commit: {resolved}"
        )
    changed = tracked_changes(root)
    if changed:
        return None, subject_reason(
            f"{len(changed)} tracked file(s) differ from HEAD; the baseline "
            "comparison needs a clean working tree",
            changed,
        )
    report = request.report_path.with_name(f"{request.report_path.stem}.baseline.json")
    baseline = execute_and_normalize(
        provider,
        request=ProviderExecutionRequest(
            repository_root=root,
            output_path=report,
            timeout_seconds=request.timeout_seconds,
            output_size_limit_bytes=request.output_size_limit_bytes,
            arguments=(
                *request.execution_arguments,
                "--baseline-commit",
                request.baseline_commit,
            ),
            targets=tuple(request.execution_targets),
        ),
        context=context,
    )
    if baseline.failures:
        return None, subject_reason(
            "the baseline scan failed",
            (
                f"{failure.failure_type.value}: {failure.message}"
                for failure in baseline.failures
            ),
        )
    if baseline.coverage.status is not CoverageStatus.COMPLETE:
        return None, subject_reason(
            f"the baseline scan is incomplete (coverage {baseline.coverage.status})",
            baseline.coverage.limitations or ("no limitation recorded",),
        )
    return frozenset(finding.fingerprint for finding in baseline.findings), None


def run_semgrep_pipeline(request: SemgrepPipelineRequest) -> SemgrepPipelineResult:
    if request.baseline_commit is not None:
        if not _BASELINE_COMMIT.fullmatch(request.baseline_commit):
            raise ValueError("baseline_commit must be a full lowercase commit ID")
        if not request.execute:
            raise ValueError("a baseline commit requires execute mode")
        if not request.policy_path:
            raise ValueError("a baseline commit requires a finding policy")
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
    precision_limitations: tuple[str, ...] = ()
    if request.precision_keywords:
        precise, precision_limitations = withhold_declared_non_security(
            normalization.findings,
            request.repository_root,
            request.precision_keywords,
        )
        normalization = replace(normalization, findings=precise)

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

    waiver_limitations: tuple[str, ...] = ()
    if request.waivers_path is not None:
        ledger_path = request.waivers_path.resolve()
        if ledger_path.is_relative_to(request.repository_root.resolve()):
            raise ValueError(
                "the waiver ledger must live outside the repository under "
                "analysis: a consumer cannot waive its own findings"
            )
        if not request.policy_path:
            raise ValueError("a waiver ledger requires a finding policy")
        if not request.repository:
            raise ValueError("a waiver ledger requires the repository identity")
        application = apply_waivers(
            findings,
            classifications,
            FindingWaiverLedger.load(request.waivers_path),
            repository=request.repository,
            on=request.waiver_date or datetime.now(tz=UTC).date(),
            source_digest=functools.partial(
                waiver_source_sha256, request.repository_root.resolve()
            ),
        )
        classifications = application.classifications
        waiver_limitations = application.limitations

    failures = tuple(normalization.failures)
    baseline_limitations: tuple[str, ...] = ()
    if request.baseline_commit is not None:
        new_fingerprints, reason = _baseline_new_fingerprints(
            provider, request, context
        )
        baseline_result = apply_baseline(
            findings,
            classifications,
            baseline_commit=request.baseline_commit,
            new_fingerprints=new_fingerprints,
            unresolved_reason=reason,
        )
        classifications = baseline_result.classifications
        baseline_limitations = baseline_result.limitations
        if new_fingerprints is None:
            # Fail closed: an unresolved baseline is a required failure whatever
            # the run's own requiredness, so the gate is never PASS.
            failures = (
                *failures,
                ProviderFailure(
                    provider_id="semgrep",
                    provider_version=provider_version,
                    failure_type=ProviderFailureType.CONFIGURATION_ERROR,
                    message=f"baseline {request.baseline_commit} unresolved: {reason}",
                    required=True,
                    fatal=True,
                ),
            )

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
        provider_failures=failures,
        coverage=(
            normalization.coverage
            if request.scan_scope is None
            else _with_scan_scope(
                normalization.coverage, request.scan_scope, request.report_path
            ),
        ),
        limitations=tuple(
            sorted(
                {
                    *limitations,
                    *framework_limitations,
                    *waiver_limitations,
                    *precision_limitations,
                    *baseline_limitations,
                }
            )
        ),
    )
    if request.generated_at is not None:
        bundle = replace(bundle, generated_at=request.generated_at)
    validation = validate_bundle(bundle)
    validation.require_valid()
    validate_redaction(bundle.to_dict()).require_valid()
    write_bundle_atomic(bundle, request.output_path)
    return SemgrepPipelineResult(bundle=bundle, output_path=request.output_path)
