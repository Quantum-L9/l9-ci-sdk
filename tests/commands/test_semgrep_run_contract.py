from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import l9_ci.__main__ as main_module
import l9_ci.commands.semgrep as semgrep_commands


def test_run_cli_preserves_public_command_and_builds_execute_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured = []

    def fake_run(request):
        captured.append(request)
        return SimpleNamespace(output_path=request.output_path)

    monkeypatch.setattr(semgrep_commands, "run_semgrep_pipeline", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l9-ci",
            "semgrep",
            "run",
            "--report",
            str(tmp_path / "report.json"),
            "--output",
            str(tmp_path / "bundle.json"),
            "--root",
            str(tmp_path),
            "--snapshot-id",
            "snapshot-1",
            "--execution-arg=--config",
            "--execution-arg=p/python",
            "--timeout-seconds",
            "30",
        ],
    )
    assert main_module.main() == 0
    request = captured[0]
    assert request.execute is True
    assert request.execution_arguments == ("--config", "p/python")
    assert request.timeout_seconds == 30


def test_normalize_cli_requires_provider_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l9-ci",
            "semgrep",
            "normalize",
            "--input",
            str(tmp_path / "report.json"),
            "--output",
            str(tmp_path / "bundle.json"),
            "--snapshot-id",
            "snapshot-1",
        ],
    )
    with pytest.raises(SystemExit) as excinfo:
        main_module.main()
    assert excinfo.value.code == 2
