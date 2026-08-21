"""Deterministic projection into the L9 Assurance observation boundary."""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from l9_ci.contracts import FindingBundle, RuleMode, Severity

OBSERVATION_PROTOCOL = "l9.observation"
OBSERVATION_SCHEMA_VERSION = "1.0.0"
SUPPORTED_OBSERVATION_CHECKS = frozenset(
    {
        "l9.repository-metadata",
        "l9.transport-packet",
        "l9.sdk-validation",
        "l9.lint",
        "l9.tests",
        "l9.mandatory-findings",
    }
)
EXECUTION_STATUSES = frozenset({"passed", "failed", "error", "skipped"})


def _sha256_digest(value: str) -> dict[str, str]:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError("digest must be a lowercase 64-character sha256 hex value")
    return {"algorithm": "sha256", "value": normalized}


def _parse_repository(repository: str) -> tuple[str, str]:
    parts = repository.strip().split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("repository must be owner/name")
    return parts[0], parts[1]


def _validate_revision(revision: str) -> str:
    value = revision.strip().lower()
    if len(value) not in {40, 64} or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("revision must be a full 40- or 64-character hex commit")
    return value


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _observation_id(payload_without_id: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_bytes(payload_without_id)).hexdigest()
    return f"sha256:{digest}"


def validate_observation(payload: Mapping[str, Any]) -> None:
    """Validate an SDK-produced observation against the bundled v1 contract."""
    schema_path = files("l9_ci").joinpath("schemas", "v1", "observation.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(dict(payload)),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        rendered = []
        for error in errors:
            path = "/".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{path}: {error.message}")
        raise ValueError(
            "observation schema validation failed:\n"
            + "\n".join(f"- {item}" for item in rendered)
        )


def build_observation(
    *,
    producer_version: str,
    repository: str,
    revision: str,
    check_id: str,
    configuration_digest: str,
    run_id: str,
    attempt: int,
    status: str,
    started_at: str,
    completed_at: str,
    finding_count: int = 0,
    error_count: int = 0,
    warning_count: int = 0,
    informational_count: int = 0,
    findings: Sequence[Mapping[str, Any]] = (),
    artifacts: Sequence[Mapping[str, Any]] = (),
    mode: str | None = None,
    producer_build_digest: str | None = None,
    execution_identity: str | None = None,
    environment_digest: str | None = None,
    invocation_digest: str | None = None,
    host: str = "github.com",
) -> dict[str, Any]:
    """Build one revision-bound factual observation.

    The function does not infer organization policy or an Assurance verdict.
    Callers supply factual execution status and counts; the SDK validates and
    canonicalizes them into the observation protocol.
    """
    if check_id not in SUPPORTED_OBSERVATION_CHECKS:
        raise ValueError(f"unsupported observation check: {check_id}")
    if status not in EXECUTION_STATUSES:
        raise ValueError(f"unsupported execution status: {status}")
    if not producer_version.strip():
        raise ValueError("producer_version must be non-empty")
    if not run_id.strip():
        raise ValueError("run_id must be non-empty")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise ValueError("attempt must be an integer >= 1")
    counts = (finding_count, error_count, warning_count, informational_count)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts):
        raise ValueError("observation summary counts must be non-negative integers")
    if finding_count != len(findings):
        raise ValueError("finding_count must equal the number of findings")

    owner, name = _parse_repository(repository)
    normalized_revision = _validate_revision(revision)

    producer: dict[str, Any] = {
        "id": "l9-ci-sdk",
        "version": producer_version,
        "repository": "Quantum-L9/l9-ci-sdk",
    }
    if producer_build_digest:
        producer["buildDigest"] = _sha256_digest(producer_build_digest)
    if execution_identity:
        producer["executionIdentity"] = execution_identity

    check: dict[str, Any] = {
        "id": check_id,
        "version": "1.0.0",
        "configurationDigest": _sha256_digest(configuration_digest),
    }
    if mode:
        check["mode"] = mode

    execution: dict[str, Any] = {
        "runId": run_id,
        "attempt": attempt,
        "status": status,
        "startedAt": started_at,
        "completedAt": completed_at,
    }
    if environment_digest:
        execution["environmentDigest"] = _sha256_digest(environment_digest)
    if invocation_digest:
        execution["invocationDigest"] = _sha256_digest(invocation_digest)

    payload: dict[str, Any] = {
        "schema": OBSERVATION_PROTOCOL,
        "schemaVersion": OBSERVATION_SCHEMA_VERSION,
        "producer": producer,
        "subject": {
            "kind": "git-revision",
            "repository": {"host": host, "owner": owner, "name": name},
            "revision": {"commit": normalized_revision},
        },
        "check": check,
        "execution": execution,
        "summary": {
            "findingCount": finding_count,
            "errorCount": error_count,
            "warningCount": warning_count,
            "informationalCount": informational_count,
        },
        "findings": [dict(item) for item in findings],
        "artifacts": [dict(item) for item in artifacts],
    }
    payload["observationId"] = _observation_id(payload)
    validate_observation(payload)
    return payload


def project_mandatory_findings_observation(
    bundle: FindingBundle,
    *,
    repository: str,
    configuration_digest: str,
    run_id: str,
    attempt: int,
    started_at: str,
    completed_at: str,
    mode: str | None = None,
    source_path: str | None = None,
) -> dict[str, Any]:
    """Project a canonical FindingBundle into `l9.mandatory-findings`.

    All canonical findings are retained. Assurance owns the policy that decides
    which severities are mandatory. Findings with unknown or absent severity
    are rejected rather than silently downgraded.
    """
    if not bundle.snapshot.revision:
        raise ValueError("FindingBundle must carry an exact revision for Assurance")

    classifications = {
        item.finding_id: item for item in bundle.classifications
    }
    projected: list[dict[str, Any]] = []
    error_count = len(bundle.provider_failures)
    warning_count = 0
    informational_count = 0

    for finding in sorted(bundle.findings, key=lambda item: item.finding_id):
        if finding.severity is None or finding.severity is Severity.UNKNOWN:
            raise ValueError(
                f"finding {finding.finding_id} has no Assurance-compatible severity"
            )
        severity = finding.severity.value
        if severity in {"critical", "high"}:
            error_count += 1
        elif severity in {"medium", "low"}:
            warning_count += 1
        elif severity == "informational":
            informational_count += 1

        item: dict[str, Any] = {
            "findingId": finding.finding_id,
            "ruleId": finding.canonical_rule_id or finding.provider_rule_id,
            "severity": severity,
            "disposition": "open",
            "message": finding.message,
            "fingerprint": finding.fingerprint,
            "metadata": {
                "providerId": finding.provider_id,
                "providerRuleId": finding.provider_rule_id,
                "category": finding.category,
                "limitations": list(finding.limitations),
                "sourceLocations": [location.to_dict() for location in finding.locations],
            },
        }
        classification = classifications.get(finding.finding_id)
        if classification is not None:
            item["metadata"]["classification"] = classification.to_dict()
        if finding.confidence is not None:
            item["metadata"]["confidence"] = finding.confidence.value
        if finding.locations:
            primary = finding.locations[0]
            location: dict[str, Any] = {"path": primary.normalized_path}
            if primary.start_line is not None:
                location["lineStart"] = primary.start_line
            if primary.start_column is not None:
                location["columnStart"] = primary.start_column
            if primary.end_line is not None:
                location["lineEnd"] = primary.end_line
            if primary.end_column is not None:
                location["columnEnd"] = primary.end_column
            item["location"] = location
        projected.append(item)

    bundle_artifact: dict[str, Any] = {
        "name": "finding-bundle",
        "digest": {
            "algorithm": "sha256",
            "value": bundle.canonical_digest(),
        },
        "mediaType": "application/vnd.l9.finding-bundle+json",
    }
    if source_path:
        source = Path(source_path)
        if source.is_absolute() or ".." in source.parts:
            raise ValueError("source_path must be repository-relative")
        bundle_artifact["path"] = source.as_posix()

    status = "error" if bundle.provider_failures else "passed"
    return build_observation(
        producer_version=bundle.SDK_version,
        repository=repository,
        revision=bundle.snapshot.revision,
        check_id="l9.mandatory-findings",
        configuration_digest=configuration_digest,
        run_id=run_id,
        attempt=attempt,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        finding_count=len(projected),
        error_count=error_count,
        warning_count=warning_count,
        informational_count=informational_count,
        findings=projected,
        artifacts=(bundle_artifact,),
        mode=mode,
    )
