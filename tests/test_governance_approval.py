from __future__ import annotations

from pathlib import Path

from l9_ci.cli import main
from l9_ci.gate.ci_gate import evaluate
from l9_ci.governance.approval import evaluate_governance_approval, is_protected_path


def test_protected_governance_path_detection() -> None:
    assert is_protected_path(".github/governance/quality-thresholds.yaml")
    assert is_protected_path("l9-ci-core/.github/workflows/pr-pipeline.yml")
    assert not is_protected_path("src/example.py")


def test_governance_change_without_label_fails() -> None:
    result = evaluate_governance_approval([".github/governance/audit-baseline.json"], [])
    assert not result.passed
    assert "without required approval" in result.reason


def test_governance_change_with_label_passes() -> None:
    result = evaluate_governance_approval(
        [".github/governance/audit-baseline.json"], ["l9-validated:approve"]
    )
    assert result.passed


def test_governance_change_with_unknown_labels_fails_closed() -> None:
    result = evaluate_governance_approval(
        [".github/governance/audit-baseline.json"], [], labels_known=False
    )
    assert not result.passed
    assert "labels are unknown" in result.reason


def test_non_governance_change_does_not_require_label() -> None:
    result = evaluate_governance_approval(["src/example.py"], [])
    assert result.passed


def test_gate_enforces_governance_approval() -> None:
    result = evaluate(
        {"validate": "success"},
        ["validate"],
        changed_files=[".github/governance/quality-thresholds.yaml"],
        pr_labels=[],
    )
    assert not result.passed
    assert result.governance_failures


def test_cli_validate_governance_approval(tmp_path: Path, capsys) -> None:
    changed = tmp_path / "changed.txt"
    labels = tmp_path / "labels.json"
    changed.write_text(".github/governance/quality-thresholds.yaml\n", encoding="utf-8")
    labels.write_text('["l9-validated:approve"]', encoding="utf-8")
    code = main([
        "validate-governance-approval",
        "--changed-files-file",
        str(changed),
        "--pr-labels-file",
        str(labels),
    ])
    assert code == 0
    assert "Governance approval passed" in capsys.readouterr().out
