"""Schema and redaction invariants for the SARIF subset projection."""

from __future__ import annotations

import copy
import json
from importlib.resources import files

from jsonschema import Draft202012Validator

from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    EvidenceRecord,
    Finding,
    FindingBundle,
    ProviderRun,
    Severity,
    SnapshotDescriptor,
    SourceLocation,
)
from l9_ci.integration import project_sarif_log, validate_redaction

SCHEMA = json.loads(
    files("l9_ci")
    .joinpath("schemas")
    .joinpath("v1")
    .joinpath("sarif-log.schema.json")
    .read_text(encoding="utf-8")
)


def _projected_log() -> dict:
    location = SourceLocation("src/example.py", start_line=3, start_column=2)
    finding = Finding(
        finding_id="finding-1",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="rule.one",
        canonical_rule_id="L9-RULE-ONE",
        category="security",
        message="Example finding message",
        evidence_ids=("evidence-1",),
        locations=(location,),
        fingerprint="fingerprint-1",
        severity=Severity.HIGH,
    )
    bundle = FindingBundle(
        SDK_version="1.2.3",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor(snapshot_id="snapshot-1", repository_root="."),
        providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", True),),
        evidence=(
            EvidenceRecord(
                evidence_id="evidence-1",
                snapshot_id="snapshot-1",
                provider_id="semgrep",
                provider_rule_id="rule.one",
                evidence_type="static-analysis-match",
                message="Example",
                locations=(location,),
            ),
        ),
        findings=(finding,),
        classifications=(),
        provider_failures=(),
        coverage=(Coverage("semgrep", CoverageStatus.COMPLETE, 1, 1, ()),),
    )
    return project_sarif_log(bundle, strict=True)


def test_schema_is_a_valid_draft_2020_12_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_projected_log_conforms_to_subset_schema() -> None:
    errors = sorted(
        Draft202012Validator(SCHEMA).iter_errors(_projected_log()),
        key=lambda error: list(error.absolute_path),
    )
    assert errors == [], [error.message for error in errors]


def test_schema_forbids_region_snippet_source_disclosure() -> None:
    log = _projected_log()
    region = log["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
    # Test data, not a credential: this is the secret-looking source line the
    # SARIF schema must refuse to carry. The assertion below is what proves
    # the disclosure guard works, so the literal has to look like a leak.
    # nosemgrep: l9.baseline.python.hardcoded-credential
    region["snippet"] = {"text": "secret = 'super-secret-value'"}
    errors = list(Draft202012Validator(SCHEMA).iter_errors(log))
    assert errors, "schema must reject a region.snippet (source-line disclosure)"


def test_schema_forbids_absolute_artifact_uri() -> None:
    log = _projected_log()
    log["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
        "artifactLocation"
    ]["uri"] = "/etc/passwd"
    errors = list(Draft202012Validator(SCHEMA).iter_errors(log))
    assert errors, "schema must reject an absolute artifactLocation.uri"


def test_schema_pins_version_const() -> None:
    log = _projected_log()
    log["version"] = "2.0.0"
    errors = list(Draft202012Validator(SCHEMA).iter_errors(log))
    assert errors, "schema must pin version to 2.1.0"


def test_projected_log_passes_redaction_validation() -> None:
    validate_redaction(_projected_log()).require_valid()


def test_projection_carries_no_raw_source_keys() -> None:
    # Belt-and-braces: the serialized projection must contain none of the
    # raw-source key names the redaction guard forbids.
    blob = json.dumps(_projected_log())
    for forbidden in ('"lines"', '"matched_source"', '"metavars"', '"snippet"'):
        assert forbidden not in blob, f"projected SARIF leaked {forbidden}"


def test_projected_log_is_not_mutated_by_validation() -> None:
    log = _projected_log()
    before = copy.deepcopy(log)
    validate_redaction(log).require_valid()
    assert log == before
