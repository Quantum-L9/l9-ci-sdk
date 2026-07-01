from __future__ import annotations

from pathlib import Path

import pytest

from l9_ci.cli import main
from l9_ci.governance.thresholds import ThresholdPolicyError, load_threshold_policy


def test_load_valid_threshold_policy(tmp_path: Path) -> None:
    path = tmp_path / "quality-thresholds.yaml"
    path.write_text(
        """
coverage:
  default: 80
  l9_ci_sdk: 85
  minimum_floor: 80
security:
  max_critical_findings: 0
  max_high_findings: 0
rule_modes:
  transport_packet_contract: blocking
""",
        encoding="utf-8",
    )
    policy = load_threshold_policy(path)
    assert policy.default_coverage == 80
    assert policy.coverage_for("l9_ci_sdk") == 85


def test_missing_threshold_policy_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ThresholdPolicyError):
        load_threshold_policy(tmp_path / "missing.yaml")


def test_bootstrap_mode_uses_internal_floor_only_for_bootstrap(tmp_path: Path) -> None:
    policy = load_threshold_policy(tmp_path / "missing.yaml", bootstrap_mode=True)
    assert policy.default_coverage == 80
    assert policy.coverage_for("l9_ci_sdk") == 85


def test_malformed_threshold_policy_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "quality-thresholds.yaml"
    path.write_text("coverage: [bad]\n", encoding="utf-8")
    with pytest.raises(ThresholdPolicyError):
        load_threshold_policy(path)


def test_threshold_below_floor_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "quality-thresholds.yaml"
    path.write_text(
        """
coverage:
  default: 60
  minimum_floor: 80
security:
  max_critical_findings: 0
  max_high_findings: 0
rule_modes:
  transport_packet_contract: blocking
""",
        encoding="utf-8",
    )
    with pytest.raises(ThresholdPolicyError):
        load_threshold_policy(path)


def test_cli_validate_thresholds(tmp_path: Path, capsys) -> None:
    path = tmp_path / "quality-thresholds.yaml"
    path.write_text(
        """
coverage:
  default: 80
  minimum_floor: 80
security:
  max_critical_findings: 0
  max_high_findings: 0
rule_modes:
  transport_packet_contract: blocking
""",
        encoding="utf-8",
    )
    assert main(["validate-thresholds", "--policy", str(path)]) == 0
    assert "L9 threshold policy valid" in capsys.readouterr().out
