from __future__ import annotations

import json
import sys

import pytest

import l9_ci.__main__ as main_module

REVISION = "a" * 40
DIGEST = "b" * 64


def run_cli(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sys, "argv", ["l9-ci", *argv])
    return main_module.main()


def test_observation_build_cli(monkeypatch, tmp_path) -> None:
    output = tmp_path / "tests-observation.json"
    code = run_cli(
        [
            "observation",
            "build",
            "--repository",
            "Quantum-L9/example",
            "--revision",
            REVISION,
            "--check-id",
            "l9.tests",
            "--configuration-digest",
            DIGEST,
            "--run-id",
            "12345",
            "--attempt",
            "1",
            "--status",
            "passed",
            "--started-at",
            "2026-08-21T20:00:00Z",
            "--completed-at",
            "2026-08-21T20:00:01Z",
            "--output",
            str(output),
        ],
        monkeypatch,
    )
    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["producer"]["id"] == "l9-ci-sdk"
    assert payload["producer"]["version"] == "2.0.0"
    assert payload["check"]["id"] == "l9.tests"
    assert payload["subject"]["revision"]["commit"] == REVISION


def test_observation_build_rejects_unknown_check(monkeypatch, tmp_path) -> None:
    output = tmp_path / "bad.json"
    code = run_cli(
        [
            "observation",
            "build",
            "--repository",
            "Quantum-L9/example",
            "--revision",
            REVISION,
            "--check-id",
            "repo.custom",
            "--configuration-digest",
            DIGEST,
            "--run-id",
            "12345",
            "--attempt",
            "1",
            "--status",
            "passed",
            "--started-at",
            "2026-08-21T20:00:00Z",
            "--completed-at",
            "2026-08-21T20:00:01Z",
            "--output",
            str(output),
        ],
        monkeypatch,
    )
    assert code != 0
    assert not output.exists()
