from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_ci.agent_payload import AgentPayloadError, render_agent_payload
from l9_ci.cli import main


def _write_summary(directory: Path, stage: str, matrix_id: str = "default", *, status: str = "success", findings: list[dict] | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stage}_{matrix_id}_ci_summary.json"
    path.write_text(
        json.dumps(
            {
                "stage": stage,
                "status": status,
                "matrix_id": matrix_id,
                "matrix": {"python": "3.12"} if matrix_id != "default" else {},
                "findings": findings or [],
                "artifacts": [],
                "duration_seconds": 0.01,
                "exit_code": 0 if status == "success" else 1,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_agent_payload_aggregates_multiple_matrix_summaries(tmp_path: Path) -> None:
    input_dir = tmp_path / "ci"
    _write_summary(input_dir, "test", "python-3-12")
    _write_summary(input_dir, "test", "python-3-13")
    _write_summary(input_dir, "validate", "default")
    payload = render_agent_payload(input_dir=input_dir, required_stages=["validate", "test"])
    assert payload["gate_status"] == "pass"
    assert len(payload["matrix_runs"]) == 3
    assert {item["matrix_id"] for item in payload["matrix_runs"]} >= {"python-3-12", "python-3-13"}


def test_duplicate_stage_matrix_ids_fail_closed(tmp_path: Path) -> None:
    input_dir = tmp_path / "ci"
    _write_summary(input_dir, "test", "python-3-12")
    duplicate = input_dir / "nested"
    _write_summary(duplicate, "test", "python-3-12")
    with pytest.raises(AgentPayloadError, match="Duplicate stage/matrix"):
        render_agent_payload(input_dir=input_dir)


def test_missing_required_matrix_summary_fails_closed(tmp_path: Path) -> None:
    input_dir = tmp_path / "ci"
    _write_summary(input_dir, "validate")
    with pytest.raises(AgentPayloadError, match="Missing required CI summary stages"):
        render_agent_payload(input_dir=input_dir, required_stages=["validate", "test"])


def test_optional_missing_summary_is_advisory(tmp_path: Path) -> None:
    input_dir = tmp_path / "ci"
    _write_summary(input_dir, "validate")
    payload = render_agent_payload(input_dir=input_dir, optional_stages=["scorecard"])
    assert payload["gate_status"] == "pass"
    assert payload["advisory_findings"][0]["rule_id"] == "OPTIONAL-STAGE-MISSING"


def test_agent_payload_preserves_autofix_vs_manual_review_separation(tmp_path: Path) -> None:
    input_dir = tmp_path / "ci"
    _write_summary(
        input_dir,
        "transport-contract",
        status="failure",
        findings=[{"rule_id": "TRANSPORT-PACKET-CONTRACT", "message": "legacy packet", "mode": "blocking"}],
    )
    _write_summary(
        input_dir,
        "deprecated-api",
        status="failure",
        findings=[{"rule_id": "DEPRECATED-API", "message": "old loader", "mode": "blocking", "autofix_safe": True}],
    )
    payload = render_agent_payload(input_dir=input_dir)
    assert payload["gate_status"] == "fail"
    assert any(item["rule_id"] == "DEPRECATED-API" for item in payload["autofix_candidates"])
    assert any(item["rule_id"] == "TRANSPORT-PACKET-CONTRACT" for item in payload["manual_review_required"])


def test_render_agent_payload_cli_writes_output(tmp_path: Path) -> None:
    input_dir = tmp_path / "ci"
    output = tmp_path / "agent_review_payload.json"
    _write_summary(input_dir, "validate")
    rc = main(["render-agent-payload", "--input-dir", str(input_dir), "--output", str(output), "--required-stage", "validate"])
    assert rc == 0
    assert json.loads(output.read_text())["gate_status"] == "pass"


def test_gate_can_emit_agent_payload_from_input_dir(tmp_path: Path) -> None:
    input_dir = tmp_path / "ci"
    output = tmp_path / "agent_review_payload.json"
    for stage in ["validate", "lint", "test", "security"]:
        _write_summary(input_dir, stage)
    rc = main(["gate", "--input-dir", str(input_dir), "--emit-agent-payload", str(output), "--required", "validate,lint,test,security"])
    assert rc == 0
    assert output.exists()


def test_gate_fails_from_input_dir_when_summary_failed(tmp_path: Path) -> None:
    input_dir = tmp_path / "ci"
    output = tmp_path / "agent_review_payload.json"
    _write_summary(input_dir, "validate")
    _write_summary(input_dir, "lint")
    _write_summary(input_dir, "test", status="failure", findings=[{"rule_id": "TEST", "message": "failed", "mode": "blocking"}])
    _write_summary(input_dir, "security")
    rc = main(["gate", "--input-dir", str(input_dir), "--emit-agent-payload", str(output), "--required", "validate,lint,test,security"])
    assert rc == 1
    assert json.loads(output.read_text())["gate_status"] == "fail"


def test_policy_hash_is_stable_across_working_directories(tmp_path: Path) -> None:
    # Identical CI summaries must yield an identical policy_hash regardless of the
    # absolute location they are read from (the digest is anchored to input_dir).
    dir_a = tmp_path / "runner_a" / "artifacts" / "ci"
    dir_b = tmp_path / "runner_b" / "artifacts" / "ci"
    for d in (dir_a, dir_b):
        _write_summary(d, "validate")
        _write_summary(d, "test")
    hash_a = render_agent_payload(input_dir=dir_a)["policy_hash"]
    hash_b = render_agent_payload(input_dir=dir_b)["policy_hash"]
    assert hash_a == hash_b


def test_payload_pr_class_uses_canonical_unknown(tmp_path: Path) -> None:
    input_dir = tmp_path / "artifacts" / "ci"
    _write_summary(input_dir, "validate")
    _write_summary(input_dir, "test")
    payload = render_agent_payload(input_dir=input_dir)
    assert payload["pr_class"] == "unknown_diff"
