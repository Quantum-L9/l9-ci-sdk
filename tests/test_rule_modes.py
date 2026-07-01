from __future__ import annotations

from pathlib import Path

import pytest

from l9_ci.governance.rule_modes import (
    RuleModePolicyError,
    apply_rule_modes_to_findings,
    finding_blocks,
    load_rule_mode_policy,
)
from l9_ci.pipeline.runner import run_pipeline


def write_policy(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def valid_policy() -> str:
    return """
version: 1
default_mode: blocking
rules:
  TRANSPORT-PACKET-CONTRACT: blocking
  DEPRECATED-API: advisory
  SEMGREP-EXPERIMENTAL: shadow
  DISABLED-RULE: disabled
promotion:
  blocking_requires:
    - l9-validated:approve
"""


def test_load_rule_mode_policy(tmp_path: Path) -> None:
    path = write_policy(tmp_path / ".github/governance/rule-modes.yaml", valid_policy())
    policy = load_rule_mode_policy(path)
    assert policy.mode_for("TRANSPORT-PACKET-CONTRACT") == "blocking"
    assert policy.mode_for("DEPRECATED-API") == "advisory"
    assert policy.mode_for("SEMGREP-EXPERIMENTAL") == "shadow"
    assert policy.mode_for("UNKNOWN-RULE") == "blocking"


def test_malformed_rule_mode_policy_fails_closed(tmp_path: Path) -> None:
    path = write_policy(
        tmp_path / ".github/governance/rule-modes.yaml",
        """
version: 1
default_mode: potato
rules:
  X: blocking
""",
    )
    with pytest.raises(RuleModePolicyError):
        load_rule_mode_policy(path)


def test_apply_rule_modes_and_blocking_semantics(tmp_path: Path) -> None:
    policy = load_rule_mode_policy(write_policy(tmp_path / "rule-modes.yaml", valid_policy()))
    findings = apply_rule_modes_to_findings(
        [
            {"rule_id": "TRANSPORT-PACKET-CONTRACT", "message": "legacy packet"},
            {"rule_id": "DEPRECATED-API", "message": "old loader"},
            {"rule_id": "SEMGREP-EXPERIMENTAL", "message": "calibration"},
            {"rule_id": "DISABLED-RULE", "message": "ignored"},
        ],
        policy,
    )
    assert [f["mode"] for f in findings] == ["blocking", "advisory", "shadow", "disabled"]
    assert finding_blocks(findings[0]) is True
    assert finding_blocks(findings[1]) is False
    assert finding_blocks(findings[2]) is False
    assert finding_blocks(findings[3]) is False


def test_pipeline_advisory_deprecated_api_does_not_block(tmp_path: Path) -> None:
    write_policy(tmp_path / ".github/governance/rule-modes.yaml", valid_policy())
    (tmp_path / "bad.py").write_text("from engine.config.loader import DomainSpecLoader\n", encoding="utf-8")
    result = run_pipeline(root=tmp_path, stage="deprecated-api")[0]
    assert result.status == "success"
    assert result.exit_code == 0
    assert result.findings
    assert result.findings[0]["mode"] == "advisory"


def test_pipeline_missing_rule_mode_policy_blocks_when_findings_exist(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("from engine.config.loader import DomainSpecLoader\n", encoding="utf-8")
    result = run_pipeline(root=tmp_path, stage="deprecated-api")[0]
    assert result.status == "failure"
    assert result.exit_code == 1
    assert result.findings[0]["rule_id"] == "RULE-MODE-POLICY"
    assert result.findings[0]["mode"] == "blocking"
