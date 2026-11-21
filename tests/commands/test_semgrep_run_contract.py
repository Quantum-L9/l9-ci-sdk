from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import l9_ci.__main__ as main_module
import l9_ci.commands.semgrep as semgrep_commands
from l9_ci.rulesets.semgrep import (
    default_identity_map_path,
    default_profile_name,
    ruleset_dir,
)


def _capture_run(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> SimpleNamespace:
    captured: list[SimpleNamespace] = []

    def fake_run(request):
        captured.append(request)
        return SimpleNamespace(output_path=request.output_path)

    monkeypatch.setattr(semgrep_commands, "run_semgrep_pipeline", fake_run)
    monkeypatch.setattr(sys, "argv", argv)
    assert main_module.main() == 0
    assert len(captured) == 1
    return captured[0]


def test_run_cli_preserves_public_command_and_builds_execute_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    request = _capture_run(
        monkeypatch,
        [
            "l9-ci",
            "semgrep",
            "run",
            "--language",
            "python",
            "--raw-output",
            str(tmp_path / "report.json"),
            "--output",
            str(tmp_path / "bundle.json"),
            "--root",
            str(tmp_path),
            "--snapshot-id",
            "snapshot-1",
            "--timeout-seconds",
            "30",
        ],
    )
    assert request.execute is True
    # The SDK runtime is provisioned into the scanned repository, so every
    # execute request excludes it; see _RUNTIME_SCAFFOLDING_EXCLUSIONS.
    assert request.execution_arguments == (
        "--config",
        "p/python",
        "--config",
        str(ruleset_dir("python")),
        "--exclude",
        ".l9/runtime",
    )
    assert request.timeout_seconds == 30


def test_run_cli_default_profile_matches_omitted_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Passing the registry default profile explicitly is byte-identical to
    omitting --profile, so the default composition stays backward-compatible."""
    base_argv = [
        "l9-ci",
        "semgrep",
        "run",
        "--language",
        "python",
        "--output",
        str(tmp_path / "bundle.json"),
        "--root",
        str(tmp_path),
    ]
    omitted = _capture_run(monkeypatch, list(base_argv))
    explicit = _capture_run(
        monkeypatch, [*base_argv, "--profile", default_profile_name()]
    )
    assert omitted.execution_arguments == explicit.execution_arguments
    assert explicit.execution_arguments == (
        "--config",
        "p/python",
        "--config",
        str(ruleset_dir("python")),
        "--exclude",
        ".l9/runtime",
    )


def test_run_cli_l9_baseline_profile_omits_registry_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The l9-baseline profile drops the community registry ruleset and scans
    with the packaged L9 ruleset only -- deterministic, no p/python entry."""
    request = _capture_run(
        monkeypatch,
        [
            "l9-ci",
            "semgrep",
            "run",
            "--language",
            "python",
            "--output",
            str(tmp_path / "bundle.json"),
            "--root",
            str(tmp_path),
            "--profile",
            "l9-baseline",
        ],
    )
    # Opting out of the registry ruleset does not opt out of the scaffolding
    # exclusion: the provisioned runtime is never repository code.
    assert request.execution_arguments == (
        "--config",
        str(ruleset_dir("python")),
        "--exclude",
        ".l9/runtime",
    )
    assert "p/python" not in request.execution_arguments


def test_run_cli_rejects_unknown_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """An unknown --profile fails closed at argument parsing (exit 2) rather
    than silently scanning with an unintended config composition."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l9-ci",
            "semgrep",
            "run",
            "--language",
            "python",
            "--output",
            str(tmp_path / "bundle.json"),
            "--profile",
            "no-such-profile",
        ],
    )
    with pytest.raises(SystemExit) as excinfo:
        main_module.main()
    assert excinfo.value.code == 2


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


def test_normalize_cli_defaults_to_packaged_identity_map(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Omitting --identity-map must load the same packaged map as `semgrep run`.

    Organization callers never pass --identity-map. Before this default,
    normalize ran with zero identity coverage while run used the packaged map.
    """
    request = _capture_run(
        monkeypatch,
        [
            "l9-ci",
            "semgrep",
            "normalize",
            "--input",
            str(tmp_path / "report.json"),
            "--output",
            str(tmp_path / "bundle.json"),
            "--provider-version",
            "1.171.0",
            "--root",
            str(tmp_path),
            "--snapshot-id",
            "snapshot-1",
        ],
    )
    assert request.execute is False
    assert request.identity_map_path == default_identity_map_path()


def test_normalize_cli_explicit_identity_map_overrides_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    override = tmp_path / "custom-identity.yaml"
    override.write_text("provider_id: semgrep\nrules: {}\n", encoding="utf-8")
    request = _capture_run(
        monkeypatch,
        [
            "l9-ci",
            "semgrep",
            "normalize",
            "--input",
            str(tmp_path / "report.json"),
            "--output",
            str(tmp_path / "bundle.json"),
            "--provider-version",
            "1.171.0",
            "--root",
            str(tmp_path),
            "--snapshot-id",
            "snapshot-1",
            "--identity-map",
            str(override),
        ],
    )
    assert request.identity_map_path == override
