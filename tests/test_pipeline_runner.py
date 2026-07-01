from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_ci.pipeline.context import (
    PipelineContext,
    derive_matrix_id,
    normalize_matrix_id,
    parse_matrix_pairs,
)
from l9_ci.pipeline.runner import run_pipeline
from l9_ci.pipeline.stages import stage_deprecated_api, stage_thresholds, stage_transport_contract


def test_matrix_id_normalization_is_deterministic() -> None:
    assert normalize_matrix_id("Python=3.12") == "python-3-12"
    assert derive_matrix_id({"python": "3.12"}) == "python-3-12"
    assert derive_matrix_id({"python": "3.13", "os": "ubuntu-latest"}) == "os-ubuntu-latest-python-3-13"


def test_parse_matrix_pairs() -> None:
    assert parse_matrix_pairs(["python=3.12", "os=ubuntu-latest"]) == {"python": "3.12", "os": "ubuntu-latest"}
    with pytest.raises(ValueError):
        parse_matrix_pairs(["python"])


def test_run_pipeline_matrix_emit_dir_creates_unique_stage_matrix_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "artifacts" / "ci"
    results = run_pipeline(
        root=tmp_path,
        stage="test",
        matrix_values=["python=3.12"],
        emit_dir=str(out_dir),
    )
    assert results[0].status == "success"
    output = out_dir / "test_python-3-12_ci_summary.json"
    assert output.exists()
    payload = json.loads(output.read_text())
    assert payload["stage"] == "test"
    assert payload["matrix_id"] == "python-3-12"


def test_run_pipeline_matrix_emit_json_without_matrix_id_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Matrix execution requires unique artifact output path"):
        run_pipeline(
            root=tmp_path,
            stage="test",
            matrix_values=["python=3.12"],
            emit_json=str(tmp_path / "artifacts" / "ci_summary.json"),
        )


def test_run_pipeline_matrix_emit_json_with_matrix_id_passes(tmp_path: Path) -> None:
    output = tmp_path / "artifacts" / "ci_summary_py313.json"
    results = run_pipeline(
        root=tmp_path,
        stage="test",
        matrix_values=["python=3.13"],
        matrix_id="py313",
        emit_json=str(output),
    )
    assert results[0].status == "success"
    assert json.loads(output.read_text())["matrix_id"] == "py313"


def test_non_matrix_emit_json_preserves_existing_behavior(tmp_path: Path) -> None:
    output = tmp_path / "ci_summary.json"
    run_pipeline(root=tmp_path, stage="classify", emit_json=str(output))
    assert json.loads(output.read_text())["matrix_id"] == "default"


def test_full_pipeline_requires_emit_dir_not_emit_json(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--emit-json can only be used"):
        run_pipeline(root=tmp_path, emit_json=str(tmp_path / "ci_summary.json"))


def _write_rule_modes(root: Path) -> None:
    path = root / ".github/governance/rule-modes.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
version: 1
default_mode: blocking
rules:
  PY-SYNTAX: blocking
  TRANSPORT-PACKET-CONTRACT: blocking
  DEPRECATED-API: blocking
  THRESHOLD-POLICY: blocking
""",
        encoding="utf-8",
    )


def test_stage_validate_reports_syntax_failure(tmp_path: Path) -> None:
    _write_rule_modes(tmp_path)
    bad = tmp_path / "bad.py"
    bad.write_text("def nope(:\n", encoding="utf-8")
    result = run_pipeline(root=tmp_path, stage="validate")[0]
    assert result.status == "failure"
    assert result.findings[0]["rule_id"] == "PY-SYNTAX"


def test_transport_contract_stage_reports_forbidden_reference(tmp_path: Path) -> None:
    _write_rule_modes(tmp_path)
    src = tmp_path / "src.py"
    src.write_text("from legacy import PacketEnvelope\n", encoding="utf-8")
    ctx = PipelineContext(root=tmp_path, stage="transport-contract")
    result = stage_transport_contract(ctx)
    assert result.status == "failure"
    assert result.findings[0]["rule_id"] == "TRANSPORT-PACKET-CONTRACT"


def test_deprecated_api_stage_reports_domain_spec_loader(tmp_path: Path) -> None:
    _write_rule_modes(tmp_path)
    src = tmp_path / "src.py"
    src.write_text("from engine.config.loader import DomainSpecLoader\n", encoding="utf-8")
    ctx = PipelineContext(root=tmp_path, stage="deprecated-api")
    result = stage_deprecated_api(ctx)
    assert result.status == "failure"
    assert result.findings[0]["rule_id"] == "DEPRECATED-API"


def test_thresholds_stage_fails_closed_when_policy_missing(tmp_path: Path) -> None:
    _write_rule_modes(tmp_path)
    ctx = PipelineContext(root=tmp_path, stage="thresholds")
    result = stage_thresholds(ctx)
    assert result.status == "failure"
    assert result.findings[0]["rule_id"] == "THRESHOLD-POLICY"


def test_unknown_pipeline_stage_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown pipeline stage"):
        run_pipeline(root=tmp_path, stage="bogus")


def test_stage_validate_fails_closed_on_unreadable_source(tmp_path: Path) -> None:
    # A non-UTF-8 .py file must become a PY-READ finding, not crash the stage.
    _write_rule_modes(tmp_path)
    (tmp_path / "bad.py").write_bytes(b"\xff\xfe\x00 not valid utf-8 \x9c")
    result = run_pipeline(root=tmp_path, stage="validate")[0]
    assert any(f["rule_id"] == "PY-READ" for f in result.findings)
