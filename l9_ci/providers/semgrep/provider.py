"""Semgrep JSON provider adapter."""

from __future__ import annotations
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence
from l9_ci.contracts import (
    Confidence,
    Coverage,
    CoverageStatus,
    EvidenceRecord,
    Finding,
    ProviderFailure,
    ProviderFailureType,
    Severity,
    SourceLocation,
)
from l9_ci.identity import RuleIdentityMap, resolve_rule_identity
from l9_ci.providers import (
    NetworkRequirement,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderMetadata,
    ProviderNormalizationContext,
    ProviderNormalizationResult,
    ProviderState,
)
from .identities import (
    build_evidence_id,
    build_finding_fingerprint,
    build_finding_id,
)
from .report import validate_semgrep_report
from .versioning import require_supported_semgrep_version

_SEVERITY_MAP: dict[str, Severity] = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.INFORMATIONAL,
    "INVENTORY": Severity.INFORMATIONAL,
    "EXPERIMENT": Severity.UNKNOWN,
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
}


class SemgrepProvider:
    """Semgrep Community Edition JSON adapter."""

    def __init__(
        self,
        *,
        identity_map: RuleIdentityMap | None = None,
    ) -> None:
        self._identity_map = identity_map

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id="semgrep",
            display_name="Semgrep",
            adapter_version="1.0.0",
            state=ProviderState.EXPERIMENTAL,
            supported_report_formats=("semgrep-json",),
            execution_support=True,
            import_support=True,
            network_requirement=NetworkRequirement.OPTIONAL,
            default_required=False,
        )

    def detect(self, repository_root: Path) -> bool:
        del repository_root
        return shutil.which("semgrep") is not None

    def detect_version(self) -> str | None:
        executable = shutil.which("semgrep")
        if executable is None:
            return None
        completed = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if completed.returncode != 0:
            return None
        version = completed.stdout.strip() or completed.stderr.strip()
        return version or None

    def validate_configuration(
        self,
        repository_root: Path,
    ) -> Sequence[str]:
        errors: list[str] = []
        if not repository_root.exists():
            errors.append("repository root does not exist")
        elif not repository_root.is_dir():
            errors.append("repository root is not a directory")
        version = self.detect_version()
        if version is not None:
            try:
                require_supported_semgrep_version(version)
            except ValueError as exc:
                errors.append(str(exc))
        return tuple(errors)

    def build_execution_plan(
        self,
        request: ProviderExecutionRequest,
    ) -> Sequence[str]:
        executable = shutil.which("semgrep") or "semgrep"
        return (
            executable,
            "scan",
            "--json-output",
            str(request.output_path),
            *request.arguments,
            str(request.repository_root),
        )

    def execute(
        self,
        request: ProviderExecutionRequest,
    ) -> ProviderExecutionResult:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        command = list(self.build_execution_plan(request))
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "HOME", "TMPDIR", "TEMP", "TMP"}
        }
        environment.update(request.environment)
        try:
            completed = subprocess.run(
                command,
                cwd=request.repository_root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ProviderExecutionResult(
                exit_code=-1,
                report_path=(
                    request.output_path if request.output_path.exists() else None
                ),
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                timed_out=True,
            )
        stdout = completed.stdout
        stderr = completed.stderr
        output_size = len(stdout.encode()) + len(stderr.encode())
        if request.output_path.exists():
            output_size += request.output_path.stat().st_size
        if output_size > request.output_size_limit_bytes:
            return ProviderExecutionResult(
                exit_code=completed.returncode,
                report_path=(
                    request.output_path if request.output_path.exists() else None
                ),
                stdout=stdout[:4096],
                stderr=stderr[:4096],
                output_limit_exceeded=True,
            )
        return ProviderExecutionResult(
            exit_code=completed.returncode,
            report_path=(request.output_path if request.output_path.exists() else None),
            stdout=stdout,
            stderr=stderr,
        )

    def execution_failure(
        self,
        result: ProviderExecutionResult,
        *,
        required: bool,
        provider_version: str | None,
    ) -> ProviderFailure | None:
        if result.timed_out:
            return ProviderFailure(
                provider_id="semgrep",
                provider_version=provider_version,
                failure_type=ProviderFailureType.TIMEOUT,
                message="Semgrep execution timed out",
                required=required,
                fatal=required,
            )
        if result.output_limit_exceeded:
            return ProviderFailure(
                provider_id="semgrep",
                provider_version=provider_version,
                failure_type=ProviderFailureType.OUTPUT_LIMIT_EXCEEDED,
                message="Semgrep output exceeded the configured limit",
                required=required,
                fatal=required,
                exit_code=result.exit_code,
            )
        if result.report_path is None:
            return ProviderFailure(
                provider_id="semgrep",
                provider_version=provider_version,
                failure_type=ProviderFailureType.REPORT_MISSING,
                message="Semgrep did not produce a report",
                required=required,
                fatal=required,
                exit_code=result.exit_code,
            )
        if result.exit_code not in {0, 1}:
            return ProviderFailure(
                provider_id="semgrep",
                provider_version=provider_version,
                failure_type=ProviderFailureType.EXECUTION_ERROR,
                message="Semgrep exited unsuccessfully",
                required=required,
                fatal=required,
                exit_code=result.exit_code,
            )
        return None

    def import_report(
        self,
        report_path: Path,
    ) -> Mapping[str, Any]:
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError(f"Semgrep report not found: {report_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"Semgrep report is not valid JSON: {exc.msg}") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("Semgrep report root must be an object")
        return payload

    def validate_report_shape(
        self,
        report: Mapping[str, Any],
    ) -> Sequence[str]:
        return validate_semgrep_report(report).errors

    def normalize(
        self,
        report: Mapping[str, Any],
        context: ProviderNormalizationContext,
    ) -> ProviderNormalizationResult:
        validation = validate_semgrep_report(report)
        if not validation.valid:
            failure = ProviderFailure(
                provider_id="semgrep",
                provider_version=context.provider_version,
                failure_type=ProviderFailureType.REPORT_MALFORMED,
                message="Semgrep report failed structural validation",
                required=context.required,
                fatal=context.required,
                diagnostics={"errors": list(validation.errors)},
            )
            return ProviderNormalizationResult(
                evidence=(),
                findings=(),
                coverage=Coverage(
                    provider_id="semgrep",
                    status=CoverageStatus.FAILED,
                    files_considered=0,
                    files_analyzed=0,
                    limitations=validation.errors,
                ),
                failures=(failure,),
                limitations=validation.errors,
            )
        evidence_records: list[EvidenceRecord] = []
        findings: list[Finding] = []
        limitations: list[str] = []
        failures: list[ProviderFailure] = []
        results = report.get("results", [])
        for result in results:
            assert isinstance(result, Mapping)
            provider_rule_id = str(result["check_id"])
            extra = result["extra"]
            assert isinstance(extra, Mapping)
            message = str(extra["message"])
            provider_fingerprint = _optional_string(
                extra.get("fingerprint") or result.get("fingerprint")
            )
            location = _source_location(result)
            metadata = extra.get("metadata", {})
            if not isinstance(metadata, Mapping):
                metadata = {}
            trusted_canonical_rule_id = _trusted_canonical_rule_id(metadata)
            identity = resolve_rule_identity(
                provider_id="semgrep",
                provider_rule_id=provider_rule_id,
                trusted_canonical_rule_id=trusted_canonical_rule_id,
                identity_map=self._identity_map,
            )
            severity, severity_limitation = _normalize_severity(extra.get("severity"))
            finding_limitations: list[str] = []
            if severity_limitation:
                finding_limitations.append(severity_limitation)
                limitations.append(severity_limitation)
            if not identity.resolved:
                unresolved_message = (
                    f"canonical rule identity unresolved for {provider_rule_id}"
                )
                finding_limitations.append(unresolved_message)
                limitations.append(unresolved_message)
            evidence_id = build_evidence_id(
                snapshot_id=context.snapshot_id,
                provider_rule_id=provider_rule_id,
                location=location,
                provider_fingerprint=provider_fingerprint,
                message=message,
            )
            fingerprint = build_finding_fingerprint(
                provider_rule_id=provider_rule_id,
                location=location,
                provider_fingerprint=provider_fingerprint,
                message=message,
            )
            finding_id = build_finding_id(
                snapshot_id=context.snapshot_id,
                fingerprint=fingerprint,
            )
            safe_metadata = _safe_metadata(metadata)
            evidence_records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    snapshot_id=context.snapshot_id,
                    provider_id="semgrep",
                    provider_version=context.provider_version,
                    provider_rule_id=provider_rule_id,
                    canonical_rule_id=identity.canonical_rule_id,
                    evidence_type="static-analysis-match",
                    message=message,
                    severity=severity,
                    confidence=Confidence.UNKNOWN,
                    locations=(location,),
                    provider_fingerprint=provider_fingerprint,
                    identifiers={
                        "semgrep_check_id": provider_rule_id,
                    },
                    attributes={
                        "provider_severity": extra.get("severity"),
                        "metadata": safe_metadata,
                        "identity_resolution_status": identity.status.value,
                        "identity_mapping_version": identity.mapping_version,
                    },
                    limitations=tuple(finding_limitations),
                )
            )
            findings.append(
                Finding(
                    finding_id=finding_id,
                    snapshot_id=context.snapshot_id,
                    provider_id="semgrep",
                    provider_rule_id=provider_rule_id,
                    canonical_rule_id=identity.canonical_rule_id,
                    category=_category(metadata),
                    message=message,
                    evidence_ids=(evidence_id,),
                    locations=(location,),
                    fingerprint=fingerprint,
                    severity=severity,
                    confidence=Confidence.UNKNOWN,
                    attributes={
                        "semgrep_check_id": provider_rule_id,
                        "identity_resolution_status": identity.status.value,
                    },
                    limitations=tuple(finding_limitations),
                )
            )
        report_errors = report.get("errors", [])
        if isinstance(report_errors, Sequence) and not isinstance(
            report_errors,
            str | bytes,
        ):
            for index, report_error in enumerate(report_errors):
                message = _semgrep_error_message(report_error, index)
                failures.append(
                    ProviderFailure(
                        provider_id="semgrep",
                        provider_version=context.provider_version,
                        failure_type=ProviderFailureType.EXECUTION_ERROR,
                        message=message,
                        required=context.required,
                        fatal=context.required,
                        diagnostics={
                            "report_error_index": index,
                        },
                    )
                )
                limitations.append(message)
        considered_paths, analyzed_paths, coverage_limitations = _coverage_paths(
            report,
            findings,
        )
        limitations.extend(coverage_limitations)
        coverage_status = (
            CoverageStatus.PARTIAL if failures else CoverageStatus.COMPLETE
        )
        coverage = Coverage(
            provider_id="semgrep",
            status=coverage_status,
            files_considered=len(considered_paths),
            files_analyzed=len(analyzed_paths),
            limitations=tuple(sorted(set(limitations))),
        )
        return ProviderNormalizationResult(
            evidence=tuple(
                sorted(
                    evidence_records,
                    key=lambda item: item.evidence_id,
                )
            ),
            findings=tuple(
                sorted(
                    findings,
                    key=lambda item: item.finding_id,
                )
            ),
            coverage=coverage,
            failures=tuple(failures),
            limitations=tuple(sorted(set(limitations))),
        )


def _coverage_paths(
    report: Mapping[str, Any],
    findings: Sequence[Finding],
) -> tuple[set[str], set[str], tuple[str, ...]]:
    limitations: list[str] = []
    report_paths = report.get("paths")
    if isinstance(report_paths, Mapping):
        scanned_raw = report_paths.get("scanned", [])
        skipped_raw = report_paths.get("skipped", [])
        scanned: set[str] = set()
        skipped: set[str] = set()
        if isinstance(scanned_raw, Sequence) and not isinstance(
            scanned_raw, str | bytes
        ):
            for path in scanned_raw:
                if isinstance(path, str):
                    scanned.add(SourceLocation(path).normalized_path)
        if isinstance(skipped_raw, Sequence) and not isinstance(
            skipped_raw, str | bytes
        ):
            for item in skipped_raw:
                if isinstance(item, str):
                    skipped.add(SourceLocation(item).normalized_path)
                elif isinstance(item, Mapping):
                    path = item.get("path")
                    if isinstance(path, str):
                        skipped.add(SourceLocation(path).normalized_path)
        return scanned | skipped, scanned, tuple(limitations)
    finding_paths = {
        location.normalized_path
        for finding in findings
        for location in finding.locations
    }
    limitations.append(
        "Semgrep report did not expose verified paths.scanned coverage; "
        "coverage was derived from finding paths only."
    )
    return finding_paths, finding_paths, tuple(limitations)


def _source_location(result: Mapping[str, Any]) -> SourceLocation:
    start = result["start"]
    end = result["end"]
    assert isinstance(start, Mapping)
    assert isinstance(end, Mapping)
    return SourceLocation(
        normalized_path=str(result["path"]),
        start_line=int(start["line"]),
        start_column=int(start["col"]),
        end_line=int(end["line"]),
        end_column=int(end["col"]),
    )


def _normalize_severity(
    raw: Any,
) -> tuple[Severity, str | None]:
    if not isinstance(raw, str) or not raw.strip():
        return Severity.UNKNOWN, "Semgrep severity was missing"
    normalized = _SEVERITY_MAP.get(raw.upper())
    if normalized is None:
        return (
            Severity.UNKNOWN,
            f"Unmapped Semgrep severity: {raw}",
        )
    return normalized, None


def _trusted_canonical_rule_id(
    metadata: Mapping[str, Any],
) -> str | None:
    l9_metadata = metadata.get("l9")
    if not isinstance(l9_metadata, Mapping):
        return None
    candidate = l9_metadata.get("canonical_rule_id")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return None


def _safe_metadata(
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    allowed_keys = {
        "category",
        "confidence",
        "cwe",
        "impact",
        "likelihood",
        "owasp",
        "references",
        "technology",
        "vulnerability_class",
    }
    return {key: metadata[key] for key in sorted(allowed_keys) if key in metadata}


def _category(metadata: Mapping[str, Any]) -> str:
    category = metadata.get("category")
    if isinstance(category, str) and category.strip():
        return category.strip().lower().replace(" ", "-")
    vulnerability_class = metadata.get("vulnerability_class")
    if isinstance(vulnerability_class, Sequence) and not isinstance(
        vulnerability_class,
        str | bytes,
    ):
        first = next(
            (
                item
                for item in vulnerability_class
                if isinstance(item, str) and item.strip()
            ),
            None,
        )
        if first:
            return first.strip().lower().replace(" ", "-")
    return "static-analysis"


def _semgrep_error_message(error: Any, index: int) -> str:
    if isinstance(error, Mapping):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return f"Semgrep report error: {message.strip()}"
        error_type = error.get("type")
        if isinstance(error_type, str) and error_type.strip():
            return f"Semgrep report error: {error_type.strip()}"
    return f"Semgrep report contained error entry {index}"


def _optional_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
