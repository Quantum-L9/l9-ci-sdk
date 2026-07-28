"""Full-path integration test against a runtime-captured Semgrep fixture (QA-010).

The fixture at tests/fixtures/semgrep/runtime/results.json is a real Semgrep
report captured from this repository's own live L9 Analysis workflow (PR #17,
GitHub Actions, Semgrep 1.170.0), redacted per the rules recorded in
provenance.yaml. This harness runs the COMPLETE
normalize -> validate -> project -> gate path against it — strict mode, with
the companion identity map and policy — and asserts the deterministic verdict.

If the fixture is ever removed, the full-path test SKIPS with an explicit
message rather than passing silently or substituting a synthetic fixture, and
the provenance test enforces that the recorded status is downgraded.
"""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.contracts import CoverageStatus
from l9_ci.gates import GateStatus, evaluate_gate
from l9_ci.integration import project_agent_review_payload
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline

RUNTIME_DIR = Path("tests/fixtures/semgrep/runtime")
RUNTIME_REPORT = RUNTIME_DIR / "results.json"
RUNTIME_PROVENANCE = RUNTIME_DIR / "provenance.yaml"
RUNTIME_IDENTITY_MAP = RUNTIME_DIR / "identity-map.yaml"
RUNTIME_POLICY = RUNTIME_DIR / "policy.yaml"

REQUIRED_PROVENANCE_FIELDS = {
    "semgrep_version",
    "capture_timestamp",
    "command",
    "input_checksum",
    "output_checksum",
    "redaction_reviewed_by",
}

_runtime_available = RUNTIME_REPORT.exists()


def test_runtime_provenance_status_matches_fixture_presence() -> None:
    # The provenance record must always exist and state a status, so the gap
    # (or the capture) is visible in the tree. runtime_captured may only be
    # claimed when the fixture is actually present.
    provenance = yaml.safe_load(RUNTIME_PROVENANCE.read_text(encoding="utf-8"))
    assert "verification_status" in provenance
    if _runtime_available:
        assert provenance["verification_status"] == "runtime_captured"
    else:
        assert provenance["verification_status"] != "runtime_captured"


@pytest.mark.skipif(
    not _runtime_available,
    reason=(
        "runtime-captured Semgrep fixture not present "
        "(tests/fixtures/semgrep/runtime/results.json); capture pending, "
        "gates Semgrep promotion — see runtime/provenance.yaml"
    ),
)
def test_runtime_fixture_checksum_matches_provenance() -> None:
    # The committed fixture must be byte-identical to the reviewed redaction
    # output recorded in provenance (tamper evidence).
    provenance = yaml.safe_load(RUNTIME_PROVENANCE.read_text(encoding="utf-8"))
    digest = hashlib.sha256(RUNTIME_REPORT.read_bytes()).hexdigest()
    assert digest == provenance["output_checksum"]


@pytest.mark.skipif(
    not _runtime_available,
    reason=(
        "runtime-captured Semgrep fixture not present "
        "(tests/fixtures/semgrep/runtime/results.json); capture pending, "
        "gates Semgrep promotion — see runtime/provenance.yaml"
    ),
)
def test_runtime_fixture_is_redacted() -> None:
    # The redaction rules recorded in provenance must hold on the committed
    # bytes: no source snippets, no volatile measurement data.
    report = json.loads(RUNTIME_REPORT.read_text(encoding="utf-8"))
    assert "time" not in report
    assert "profiling_results" not in report
    for result in report["results"]:
        assert "lines" not in result["extra"]


@pytest.mark.skipif(
    not _runtime_available,
    reason=(
        "runtime-captured Semgrep fixture not present "
        "(tests/fixtures/semgrep/runtime/results.json); capture pending, "
        "gates Semgrep promotion — see runtime/provenance.yaml"
    ),
)
def test_runtime_fixture_full_path(tmp_path: Path) -> None:
    provenance = yaml.safe_load(RUNTIME_PROVENANCE.read_text(encoding="utf-8"))
    assert provenance.get("verification_status") == "runtime_captured"
    assert REQUIRED_PROVENANCE_FIELDS <= set(provenance)

    output = tmp_path / "bundle.json"
    result = run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=RUNTIME_REPORT,
            repository_root=Path(".").resolve(),
            snapshot_id="runtime-snapshot",
            SDK_version="1.0.0",
            output_path=output,
            provider_version=str(provenance["semgrep_version"]),
            identity_map_path=RUNTIME_IDENTITY_MAP,
            policy_path=RUNTIME_POLICY,
            strict=True,
            required=True,
            generated_at="2026-07-17T00:00:00Z",
        )
    )
    # Deterministic content assertions against the captured report.
    characteristics = provenance["report_characteristics"]
    assert len(result.bundle.findings) == characteristics["result_count"]
    finding = result.bundle.findings[0]
    assert finding.canonical_rule_id == "L9-PY-SUBPROCESS-INJECTION"
    coverage = result.bundle.coverage[0]
    assert coverage.status is CoverageStatus.COMPLETE
    assert coverage.files_considered == characteristics["scanned_file_count"]
    assert coverage.files_analyzed == characteristics["scanned_file_count"]
    assert result.bundle.provider_failures == ()
    assert len(result.bundle.classifications) == 1

    # Validate (schema + semantic), project the agent payload (strict), gate.
    bundle = load_and_validate_bundle(output)
    project_agent_review_payload(bundle, strict=True)
    gate_result = evaluate_gate(bundle)
    assert gate_result.status is GateStatus[provenance["expected_gate_status"].upper()]
    schema = json.loads(
        files("l9_ci").joinpath("schemas/v1/gate-result.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(gate_result.to_dict())
