"""Canonical artifact schema and semantic validation."""

from __future__ import annotations
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from l9_ci.contracts import FindingBundle
from .compatibility import check_bundle_compatibility


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]

    def require_valid(self) -> None:
        if not self.valid:
            joined = "\n".join(f"- {error}" for error in self.errors)
            raise ValueError(f"artifact validation failed:\n{joined}")


def load_bundle_schema() -> dict[str, Any]:
    schema_path = (
        files("l9_ci")
        .joinpath("schemas")
        .joinpath("v1")
        .joinpath("finding-bundle.schema.json")
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _schema_registry() -> Registry:
    schema_root = files("l9_ci").joinpath("schemas").joinpath("v1")
    resources = []
    for entry in schema_root.iterdir():
        if entry.name.endswith(".schema.json"):
            schema = json.loads(entry.read_text(encoding="utf-8"))
            resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def validate_bundle_schema(
    payload: Mapping[str, Any],
) -> ValidationResult:
    validator = Draft202012Validator(
        load_bundle_schema(),
        registry=_schema_registry(),
    )
    errors = tuple(
        sorted(
            (
                f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
                f"{error.message}"
            )
            for error in validator.iter_errors(payload)
        )
    )
    return ValidationResult(valid=not errors, errors=errors)


def validate_bundle_semantics(bundle: FindingBundle) -> ValidationResult:
    errors: list[str] = []
    evidence_ids = [item.evidence_id for item in bundle.evidence]
    finding_ids = [item.finding_id for item in bundle.findings]
    classification_ids = [item.finding_id for item in bundle.classifications]
    provider_ids = [item.provider_id for item in bundle.providers]
    coverage_provider_ids = [item.provider_id for item in bundle.coverage]
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("evidence IDs must be unique")
    if len(finding_ids) != len(set(finding_ids)):
        errors.append("finding IDs must be unique")
    if len(classification_ids) != len(set(classification_ids)):
        errors.append("classifications must be unique by finding_id")
    if len(provider_ids) != len(set(provider_ids)):
        errors.append("provider runs must be unique by provider_id")
    if len(coverage_provider_ids) != len(set(coverage_provider_ids)):
        errors.append("coverage records must be unique by provider_id")
    evidence_id_set = set(evidence_ids)
    finding_id_set = set(finding_ids)
    provider_id_set = set(provider_ids)
    for evidence in bundle.evidence:
        if evidence.snapshot_id != bundle.snapshot.snapshot_id:
            errors.append(
                f"evidence {evidence.evidence_id!r} has a different snapshot_id"
            )
        if evidence.provider_id not in provider_id_set:
            errors.append(
                f"evidence {evidence.evidence_id!r} references unregistered "
                f"provider {evidence.provider_id!r}"
            )
    for finding in bundle.findings:
        if finding.snapshot_id != bundle.snapshot.snapshot_id:
            errors.append(f"finding {finding.finding_id!r} has a different snapshot_id")
        if finding.provider_id not in provider_id_set:
            errors.append(
                f"finding {finding.finding_id!r} references unregistered "
                f"provider {finding.provider_id!r}"
            )
        missing_evidence = set(finding.evidence_ids) - evidence_id_set
        if missing_evidence:
            errors.append(
                f"finding {finding.finding_id!r} references missing evidence: "
                f"{sorted(missing_evidence)!r}"
            )
    for classification in bundle.classifications:
        if classification.finding_id not in finding_id_set:
            errors.append(
                "classification references missing finding: "
                f"{classification.finding_id!r}"
            )
    for coverage in bundle.coverage:
        if coverage.provider_id not in provider_id_set:
            errors.append(
                f"coverage references unregistered provider {coverage.provider_id!r}"
            )
    requested = provider_id_set
    covered = set(coverage_provider_ids)
    if requested != covered:
        missing = requested - covered
        unexpected = covered - requested
        if missing:
            errors.append(
                f"missing coverage records for providers: {sorted(missing)!r}"
            )
        if unexpected:
            errors.append(
                f"unexpected coverage records for providers: {sorted(unexpected)!r}"
            )
    return ValidationResult(
        valid=not errors,
        errors=tuple(sorted(errors)),
    )


def validate_bundle(bundle: FindingBundle) -> ValidationResult:
    payload = bundle.to_dict()
    errors: list[str] = []
    summary_result = validate_raw_summary(payload)
    summary_result.require_valid()
    compatibility = check_bundle_compatibility(payload)
    errors.extend(compatibility.errors)
    schema_result = validate_bundle_schema(payload)
    errors.extend(schema_result.errors)
    semantic_result = validate_bundle_semantics(bundle)
    errors.extend(semantic_result.errors)
    return ValidationResult(
        valid=not errors,
        errors=tuple(sorted(set(errors))),
    )


def validate_raw_summary(
    payload: Mapping[str, Any],
) -> ValidationResult:
    expected = {
        "provider_count": len(payload.get("providers", [])),
        "evidence_count": len(payload.get("evidence", [])),
        "finding_count": len(payload.get("findings", [])),
        "classification_count": len(payload.get("classifications", [])),
        "provider_failure_count": len(payload.get("provider_failures", [])),
        "coverage_count": len(payload.get("coverage", [])),
    }
    actual = payload.get("summary")
    if actual != expected:
        return ValidationResult(
            valid=False,
            errors=("bundle summary does not match raw record counts",),
        )
    return ValidationResult(valid=True, errors=())


def load_and_validate_bundle(path: Path) -> FindingBundle:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_raw_summary(payload).require_valid()
    compatibility = check_bundle_compatibility(payload)
    if not compatibility.compatible:
        ValidationResult(False, compatibility.errors).require_valid()
    schema_result = validate_bundle_schema(payload)
    schema_result.require_valid()
    bundle = FindingBundle.from_dict(payload)
    semantic_result = validate_bundle_semantics(bundle)
    semantic_result.require_valid()
    return bundle
