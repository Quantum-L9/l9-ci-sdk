"""Coverage for the `l9-ci semgrep run` command: the CLI step that collapses
`semgrep scan` + `l9-ci semgrep normalize` into one invocation (see
``l9_ci/commands/semgrep.py``). Before this suite, the command had zero
automated coverage -- it was only exercised by hand against a locally
faked `semgrep` executable during authoring (see the Semgrep identity/
global-ruleset GMP). This file codifies that manual check as a repeatable
regression test.
"""

from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path

import pytest

from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.cli import ExitCode
from l9_ci.commands.semgrep import (
    _build_run_config_arguments,
    handle_run,
    register_semgrep_commands,
)
from l9_ci.rulesets.semgrep import ruleset_dir

_FAKE_SEMGREP_SCRIPT = """\
#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args[:1] == ["--version"]:
    print("1.171.0")
    raise SystemExit(0)
if args[:1] == ["scan"]:
    output_path = None
    for index, value in enumerate(args):
        if value == "--json-output":
            output_path = args[index + 1]
            break
    assert output_path is not None, "fake semgrep expected --json-output"
    payload = {
        "results": [
            {
                "check_id": "fake.rule.unresolved",
                "path": "example.py",
                "start": {"line": 1, "col": 1},
                "end": {"line": 1, "col": 5},
                "extra": {
                    "message": "fake finding from test fixture",
                    "severity": "WARNING",
                    "metadata": {},
                },
            }
        ],
        "errors": [],
        "paths": {"scanned": ["example.py"], "skipped": []},
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    raise SystemExit(0)
raise SystemExit(f"fake semgrep received unexpected arguments: {args!r}")
"""


def _install_fake_semgrep(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "semgrep"
    script.write_text(_FAKE_SEMGREP_SCRIPT, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _build_run_namespace(**overrides: object) -> argparse.Namespace:
    """Parse a real `semgrep run` argv through the registered parser.

    Exercises `register_semgrep_commands` wiring and the command's real
    argparse defaults in one step, rather than hand-constructing a
    `Namespace` that could silently drift from the actual CLI contract.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_semgrep_commands(subparsers)
    argv = ["semgrep", "run", "--language", "python"]
    for key, value in overrides.items():
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                argv.append(flag)
        else:
            argv.extend((flag, str(value)))
    return parser.parse_args(argv)


def test_run_subcommand_rejects_unsupported_language() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_semgrep_commands(subparsers)
    with pytest.raises(SystemExit):
        parser.parse_args(["semgrep", "run", "--language", "rust", "--output", "x"])


def test_run_subcommand_wires_to_handle_run() -> None:
    args = _build_run_namespace(output="bundle.json")
    assert args.handler is handle_run
    assert args.language == "python"
    assert args.no_registry_config is False
    assert args.extra_config == []


def test_build_run_config_arguments_defaults_to_registry_plus_packaged_ruleset() -> (
    None
):
    args = _build_run_namespace(output="bundle.json")
    arguments = _build_run_config_arguments(args)
    assert arguments == (
        "--config",
        "p/python",
        "--config",
        str(ruleset_dir("python")),
    )


def test_build_run_config_arguments_no_registry_config_omits_registry_ruleset() -> None:
    args = _build_run_namespace(output="bundle.json", no_registry_config=True)
    arguments = _build_run_config_arguments(args)
    assert arguments == ("--config", str(ruleset_dir("python")))


def test_build_run_config_arguments_appends_extra_config_after_defaults() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_semgrep_commands(subparsers)
    args = parser.parse_args(
        [
            "semgrep",
            "run",
            "--language",
            "python",
            "--output",
            "bundle.json",
            "--extra-config",
            "custom-rules.yaml",
            "--extra-config",
            "p/security-audit",
        ]
    )
    arguments = _build_run_config_arguments(args)
    assert arguments == (
        "--config",
        "p/python",
        "--config",
        str(ruleset_dir("python")),
        "--config",
        "custom-rules.yaml",
        "--config",
        "p/security-audit",
    )


def test_handle_run_executes_and_normalizes_into_a_valid_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _install_fake_semgrep(bin_dir)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    output = tmp_path / "bundle.json"
    args = _build_run_namespace(
        output=str(output),
        root=str(tmp_path),
        **{"snapshot-id": "snap-1", "generated-at": "2026-07-17T00:00:00Z"},
    )
    exit_code = handle_run(args)

    assert exit_code == int(ExitCode.SUCCESS)
    bundle = load_and_validate_bundle(output)
    assert len(bundle.findings) == 1
    assert bundle.findings[0].provider_rule_id == "fake.rule.unresolved"
    # The fake report's check_id is not in the packaged identity map, so
    # (non-strict) it stays unresolved rather than inventing an identity.
    assert bundle.findings[0].canonical_rule_id is None


def test_handle_run_reports_a_clean_error_when_semgrep_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

    output = tmp_path / "bundle.json"
    args = _build_run_namespace(output=str(output), root=str(tmp_path))
    exit_code = handle_run(args)

    assert exit_code == int(ExitCode.PROVIDER_EXECUTION_FAILURE)
    assert not output.exists()


def test_handle_run_surfaces_provider_execution_failure_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unsupported (too-old) semgrep version must fail the CLI command
    cleanly via `validate_configuration`, not crash with a traceback."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "semgrep"
    script.write_text(
        "#!/usr/bin/env python3\nprint('0.999.0')\nraise SystemExit(0)\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    output = tmp_path / "bundle.json"
    args = _build_run_namespace(output=str(output), root=str(tmp_path))
    exit_code = handle_run(args)

    assert exit_code == int(ExitCode.PROVIDER_EXECUTION_FAILURE)
    assert not output.exists()
