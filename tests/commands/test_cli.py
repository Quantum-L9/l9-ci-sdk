"""CLI command-handler / argparse integration tests (QA-006).

Exercises the real entrypoint (l9_ci.__main__.main) for every command: success
and failure JSON envelopes, stderr behavior, required-flag validation, and the
exact exit-code mapping per typed failure. Before this, tests/cli had only two
trivial tests and the Core-facing CLI boundary was effectively untested.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any
import pytest
import l9_ci.__main__ as main_module
from l9_ci.artifacts import bundle_bytes
from l9_ci.cli import ExitCode
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    FindingBundle,
    ProviderFailure,
    ProviderFailureType,
    ProviderRun,
    SnapshotDescriptor,
)

FIXTURE = Path("tests/fixtures/semgrep/results.json")


def run_cli(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sys, "argv", ["l9-ci", *argv])
    return main_module.main()


def _bundle(
    *,
    coverage_status: CoverageStatus = CoverageStatus.COMPLETE,
    failures: tuple[ProviderFailure, ...] = (),
) -> FindingBundle:
    analyzed = 1 if coverage_status is CoverageStatus.COMPLETE else 0
    return FindingBundle(
        SDK_version="1.0.0",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor("snapshot-1", "."),
        providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", True),),
        evidence=(),
        findings=(),
        classifications=(),
        provider_failures=failures,
        coverage=(Coverage("semgrep", coverage_status, 1, analyzed, ()),),
    )


def _write_bundle(path: Path, bundle: FindingBundle) -> Path:
    path.write_bytes(bundle_bytes(bundle))
    return path


def _json_stderr(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(capsys.readouterr().err)
    return payload


def _json_stdout(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(capsys.readouterr().out)
    return payload


# --- success envelopes ------------------------------------------------------


def test_providers_list_json_success(monkeypatch, capsys) -> None:
    assert run_cli(["providers", "list", "--format", "json"], monkeypatch) == 0
    assert _json_stdout(capsys)["ok"] is True


def test_providers_detect_json_success(monkeypatch, capsys, tmp_path) -> None:
    code = run_cli(
        ["providers", "detect", "--root", str(tmp_path), "--format", "json"],
        monkeypatch,
    )
    assert code == 0
    assert _json_stdout(capsys)["ok"] is True


def test_bundle_validate_success(monkeypatch, capsys, tmp_path) -> None:
    bundle_path = _write_bundle(tmp_path / "bundle.json", _bundle())
    assert run_cli(["bundle", "validate", str(bundle_path)], monkeypatch) == 0


# --- gate exit-code mapping (fail-closed) -----------------------------------


def test_gate_evaluate_pass(monkeypatch, capsys, tmp_path) -> None:
    bundle_path = _write_bundle(tmp_path / "bundle.json", _bundle())
    out = tmp_path / "gate.json"
    code = run_cli(
        ["gate", "evaluate", "--bundle", str(bundle_path), "--output", str(out)],
        monkeypatch,
    )
    assert code == int(ExitCode.SUCCESS)
    assert json.loads(out.read_text())["status"] == "pass"


def test_gate_evaluate_incomplete_on_required_nonfatal_failure(
    monkeypatch, tmp_path
) -> None:
    # AUD-003 regression, at the CLI boundary: required non-fatal failure ->
    # INCOMPLETE -> exit 6.
    failure = ProviderFailure(
        provider_id="semgrep",
        failure_type=ProviderFailureType.EXECUTION_ERROR,
        message="advisory",
        required=True,
        fatal=False,
    )
    bundle_path = _write_bundle(tmp_path / "bundle.json", _bundle(failures=(failure,)))
    out = tmp_path / "gate.json"
    code = run_cli(
        ["gate", "evaluate", "--bundle", str(bundle_path), "--output", str(out)],
        monkeypatch,
    )
    assert code == int(ExitCode.UNRESOLVED_STRICT_CONTRACT)
    assert json.loads(out.read_text())["status"] == "incomplete"


# --- structured failure envelopes -------------------------------------------


def test_bundle_validate_missing_file_json_error(monkeypatch, capsys, tmp_path) -> None:
    code = run_cli(
        ["bundle", "validate", str(tmp_path / "nope.json"), "--format", "json"],
        monkeypatch,
    )
    assert code == int(ExitCode.ARTIFACT_VALIDATION_FAILURE)
    payload = _json_stderr(capsys)
    assert payload["ok"] is False
    assert "code" in payload["error"]


def test_semgrep_normalize_missing_report_json_error(
    monkeypatch, capsys, tmp_path
) -> None:
    code = run_cli(
        [
            "semgrep",
            "normalize",
            "--input",
            str(tmp_path / "missing.json"),
            "--output",
            str(tmp_path / "out.json"),
            "--snapshot-id",
            "s1",
            "--format",
            "json",
        ],
        monkeypatch,
    )
    assert code == int(ExitCode.PROVIDER_REPORT_FAILURE)
    assert _json_stderr(capsys)["ok"] is False


def test_semgrep_normalize_unsupported_version_exit_8(
    monkeypatch, capsys, tmp_path
) -> None:
    code = run_cli(
        [
            "semgrep",
            "normalize",
            "--input",
            str(FIXTURE),
            "--output",
            str(tmp_path / "out.json"),
            "--snapshot-id",
            "s1",
            "--provider-version",
            "1.99.0",
            "--format",
            "json",
        ],
        monkeypatch,
    )
    assert code == int(ExitCode.INCOMPATIBLE_VERSION)
    payload = _json_stderr(capsys)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "incompatible_version"


def test_compatibility_check_success_and_json(monkeypatch, capsys, tmp_path) -> None:
    bundle_path = _write_bundle(tmp_path / "bundle.json", _bundle())
    code = run_cli(
        ["compatibility", "check", "--bundle", str(bundle_path), "--format", "json"],
        monkeypatch,
    )
    assert code == int(ExitCode.SUCCESS)
    assert _json_stdout(capsys)["ok"] is True


def test_compatibility_check_incompatible_exit_8(monkeypatch, capsys, tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"schema": "x", "schema_version": "9.0.0", "SDK_version": "1.0.0"}),
        encoding="utf-8",
    )
    code = run_cli(
        ["compatibility", "check", "--bundle", str(bad), "--format", "json"],
        monkeypatch,
    )
    assert code == int(ExitCode.INCOMPATIBLE_VERSION)
    assert _json_stderr(capsys)["ok"] is False


# --- argparse validation ----------------------------------------------------


def test_missing_required_flag_exits_2(monkeypatch) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run_cli(["semgrep", "normalize"], monkeypatch)
    assert excinfo.value.code == int(ExitCode.INVALID_ARGUMENTS)


def test_unknown_command_exits_2(monkeypatch) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run_cli(["nonexistent"], monkeypatch)
    assert excinfo.value.code == int(ExitCode.INVALID_ARGUMENTS)
