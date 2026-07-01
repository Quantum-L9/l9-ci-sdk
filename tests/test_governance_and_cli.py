from __future__ import annotations

from pathlib import Path

import json

from l9_ci.cli import main
from l9_ci.governance import banned_imports, terminology_guard
from l9_ci.scanners import secrets_policy


def test_terminology_guard_detects_legacy_typing(tmp_path: Path) -> None:
    target = tmp_path / "engine" / "x.py"
    target.parent.mkdir()
    target.write_text("from typing import Optional\nvalue: Optional[str] = None\n", encoding="utf-8")
    violations = terminology_guard.scan([tmp_path], include_prefixes=[str(tmp_path / "engine")])
    assert any("T | None" in item.message for item in violations)


def test_terminology_guard_include_prefix_limits_scope(tmp_path: Path) -> None:
    ignored = tmp_path / "docs" / "x.py"
    ignored.parent.mkdir()
    ignored.write_text("print('ignored')\n", encoding="utf-8")
    assert terminology_guard.scan([tmp_path], include_prefixes=[str(tmp_path / "engine")]) == []


def test_banned_imports_detects_module(tmp_path: Path) -> None:
    target = tmp_path / "engine" / "service.py"
    target.parent.mkdir()
    target.write_text("from fastapi import FastAPI\n", encoding="utf-8")
    violations = banned_imports.scan([tmp_path], "fastapi")
    assert len(violations) == 1
    assert violations[0].module == "fastapi"


def test_banned_imports_allows_explicit_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "engine" / "handlers.py"
    target.parent.mkdir()
    target.write_text("import fastapi\n", encoding="utf-8")
    assert banned_imports.scan([tmp_path], "fastapi", allow=["engine/handlers.py"]) == []


def test_expected_gitleaks_rules_include_neo4j_and_openai() -> None:
    rules = secrets_policy.expected_rules()
    assert "openai-api-key" in rules
    assert "neo4j-connection" in rules
    assert rules is not secrets_policy.UNIVERSAL_GITLEAKS_RULES


def test_cli_gate_success(capsys) -> None:
    code = main(["gate", "--required", "validate,lint", "--result", "validate=success", "--result", "lint=skipped"])
    assert code == 0
    assert "CI gate passed" in capsys.readouterr().out


def test_cli_gate_failure(capsys) -> None:
    code = main(["gate", "--required", "validate,lint", "--result", "validate=success", "--result", "lint=failure"])
    assert code == 1
    assert "lint=failure" in capsys.readouterr().out


def test_cli_scanner_commands(tmp_path: Path, capsys) -> None:
    target = tmp_path / "bad.py"
    target.write_text("PacketEnvelope()\n", encoding="utf-8")
    code = main(["check-transport-packet", str(tmp_path)])
    assert code == 1
    assert "PacketEnvelope" in capsys.readouterr().err


def test_cli_review_defaults_audit_to_advisory(tmp_path: Path, capsys) -> None:
    # Out-of-the-box the deterministic audit agent should surface advisory
    # findings, not silently default to shadow (which prints 0 advisory).
    (tmp_path / "bad.py").write_text("from x import PacketEnvelope\n", encoding="utf-8")
    out_json = tmp_path / "report.json"
    code = main(
        [
            "review",
            "--root",
            str(tmp_path),
            "--changed-file",
            "bad.py",
            "--file-mode",
            "filesystem",
            "--emit-json",
            str(out_json),
        ]
    )
    assert code == 0
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert report["advisory_count"] >= 1
    assert report["blocking_count"] == 0
    assert "advisory" in capsys.readouterr().out


def test_cli_review_explicit_shadow_overrides_default(tmp_path: Path) -> None:
    # An explicit --agent-mode audit=shadow must win over the advisory default.
    (tmp_path / "bad.py").write_text("from x import PacketEnvelope\n", encoding="utf-8")
    out_json = tmp_path / "report.json"
    code = main(
        [
            "review",
            "--root",
            str(tmp_path),
            "--changed-file",
            "bad.py",
            "--file-mode",
            "filesystem",
            "--agent-mode",
            "audit=shadow",
            "--emit-json",
            str(out_json),
        ]
    )
    assert code == 0
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert report["advisory_count"] == 0
    assert report["shadow_count"] >= 1


def test_cli_deprecated_fix_zero_on_change(tmp_path: Path) -> None:
    target = tmp_path / "bad.py"
    target.write_text("from engine.config.loader import DomainSpecLoader\nloader = DomainSpecLoader(SPEC_PATH)\n", encoding="utf-8")
    code = main(["fix-deprecated-api", str(tmp_path), "--zero-on-change"])
    assert code == 0
    assert "DomainPackLoader(config_path=str(SPEC_PATH))" in target.read_text(encoding="utf-8")
