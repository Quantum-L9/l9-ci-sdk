"""Full-path integration test against a runtime-captured Semgrep fixture (QA-010).

Provider behavior has only ever been tested against a hand-authored
"representative" fixture. This harness runs the COMPLETE
normalize -> validate -> project -> gate path against a real, provenance-bound
Semgrep report captured from the pinned supported version.

The runtime fixture (tests/fixtures/semgrep/runtime/results.json) requires a real
Semgrep run to capture and could not be produced in the report-only audit
environment (Semgrep binary unavailable). Until it is captured and its
provenance recorded, the full-path test SKIPS with an explicit message rather
than passing silently or substituting a synthetic fixture. This is the tracked
gate on promoting Semgrep out of EXPERIMENTAL (roadmap P4).
"""

from __future__ import annotations
import json
from importlib.resources import files
from pathlib import Path
import pytest
import yaml
from jsonschema import Draft202012Validator
from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.gates import evaluate_gate
from l9_ci.integration import project_agent_review_payload
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline

RUNTIME_DIR = Path("tests/fixtures/semgrep/runtime")
RUNTIME_REPORT = RUNTIME_DIR / "results.json"
RUNTIME_PROVENANCE = RUNTIME_DIR / "provenance.yaml"

REQUIRED_PROVENANCE_FIELDS = {
    "semgrep_version",
    "capture_timestamp",
    "command",
    "input_checksum",
    "output_checksum",
    "redaction_reviewed_by",
}

_runtime_available = RUNTIME_REPORT.exists()


def test_runtime_provenance_placeholder_is_explicit() -> None:
    # The provenance record must always exist and state a status, so the gap is
    # visible in the tree rather than silently absent. Before capture it must
    # NOT claim runtime_captured.
    provenance = yaml.safe_load(RUNTIME_PROVENANCE.read_text(encoding="utf-8"))
    assert "verification_status" in provenance
    if not _runtime_available:
        assert provenance["verification_status"] != "runtime_captured"


@pytest.mark.skipif(
    not _runtime_available,
    reason=(
        "runtime-captured Semgrep fixture not yet present "
        "(tests/fixtures/semgrep/runtime/results.json); capture pending, "
        "gates Semgrep promotion — see runtime/provenance.yaml"
    ),
)
def test_runtime_fixture_full_path(tmp_path: Path) -> None:
    provenance = yaml.safe_load(RUNTIME_PROVENANCE.read_text(encoding="utf-8"))
    assert provenance.get("verification_status") == "runtime_captured"
    assert REQUIRED_PROVENANCE_FIELDS <= set(provenance)

    output = tmp_path / "bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=RUNTIME_REPORT,
            repository_root=Path(".").resolve(),
            snapshot_id="runtime-snapshot",
            SDK_version="1.0.0",
            output_path=output,
            provider_version=str(provenance["semgrep_version"]),
            required=True,
            generated_at="2026-07-17T00:00:00Z",
        )
    )
    # Validate (schema + semantic), project the agent payload, and gate.
    bundle = load_and_validate_bundle(output)
    project_agent_review_payload(bundle, strict=False)
    gate_result = evaluate_gate(bundle)
    schema = json.loads(
        files("l9_ci").joinpath("schemas/v1/gate-result.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(gate_result.to_dict())
