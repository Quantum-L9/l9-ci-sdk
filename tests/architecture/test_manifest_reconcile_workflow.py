"""Witnesses: the manifest reconcile workflow detects drift and never pushes.

A commit pushed with the workflow ``GITHUB_TOKEN`` starts no new workflow run,
so the former bot reconcile commit left PR heads with their required checks
never run or held at ``action_required`` (l9-ci-sdk#117, head ``df39e1e6``).
These tests keep the push out and prove the replacement behaviour: on drift the
workflow uploads a patch for every PR and fails; on no drift it passes.
See ``docs/architecture/repository-manifest.md`` ("PR behavior").
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
RECONCILE = WORKFLOWS / "l9-manifest-reconcile.yml"

_GIT_PUSH = re.compile(r"(?m)^\s*[^#\n]*\bgit\s+push\b")


def _workflow() -> dict[Any, Any]:
    loaded = yaml.safe_load(RECONCILE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _steps() -> list[dict[str, Any]]:
    jobs = _workflow()["jobs"]
    assert list(jobs) == ["reconcile"]
    steps = jobs["reconcile"]["steps"]
    assert isinstance(steps, list)
    return steps


def _step(name: str) -> dict[str, Any]:
    matches = [step for step in _steps() if step.get("name") == name]
    assert len(matches) == 1, f"expected exactly one step named {name!r}"
    return matches[0]


def _all_workflows() -> list[Path]:
    return sorted(
        path
        for path in WORKFLOWS.iterdir()
        if path.is_file() and path.suffix in (".yml", ".yaml")
    )


@pytest.mark.parametrize("workflow", _all_workflows(), ids=lambda path: path.name)
def test_no_workflow_pushes_with_the_workflow_token(workflow: Path) -> None:
    text = workflow.read_text(encoding="utf-8")
    assert not _GIT_PUSH.search(text), (
        f"{workflow.name} runs `git push`; a GITHUB_TOKEN push starts no CI on "
        "the new head (l9-ci-sdk#117)"
    )


def test_reconcile_is_read_only() -> None:
    assert _workflow()["permissions"] == {"contents": "read"}
    checkout = _steps()[0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["persist-credentials"] is False


def test_reconcile_patch_and_failure_apply_to_every_pr() -> None:
    drift = "steps.reconcile.outputs.changed == 'true'"
    for name in (
        "Export reconciliation patch",
        "Upload reconciliation patch",
        "Fail on derived-state drift",
    ):
        # No head-repository (fork vs same-repository) split any more.
        assert _step(name)["if"] == drift, name
    assert _step("Upload reconciliation patch")["with"]["if-no-files-found"] == "error"
    assert [step["name"] for step in _steps()][-1] == "Fail on derived-state drift"


def _command_tokens(script: str) -> list[str]:
    tokens = [token for token in script.replace("\\\n", " ").split() if token != "\\"]
    start = tokens.index("l9_ci")
    end = next(
        (i for i, token in enumerate(tokens[start:], start) if token.endswith('"')),
        len(tokens) - 1,
    )
    return [token.strip('"') for token in tokens[start : end + 1]]


def test_failure_message_names_the_generate_command_ci_runs() -> None:
    generate = _command_tokens(_step("Generate manifest from repository truth")["run"])
    message = _command_tokens(_step("Fail on derived-state drift")["run"])
    assert generate[:2] == ["l9_ci", "manifest"]
    assert message == generate


def _run_step(name: str, cwd: Path, output: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GITHUB_OUTPUT": str(output)}
    return subprocess.run(
        ["bash", "-eo", "pipefail", "-c", _step(name)["run"]],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "witness@example.invalid")
    _git(repo, "config", "user.name", "witness")
    (repo / "MANIFEST.md").write_text("a\n", encoding="utf-8")
    (repo / "uv.lock").write_text("lock\n", encoding="utf-8")
    _git(repo, "add", "MANIFEST.md", "uv.lock")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def test_drift_exports_patch_and_fails(scratch_repo: Path, tmp_path: Path) -> None:
    output = tmp_path / "github_output"
    (scratch_repo / "MANIFEST.md").write_text("a\nb\n", encoding="utf-8")

    detect = _run_step("Detect reconciliation changes", scratch_repo, output)
    assert detect.returncode == 0
    assert "changed=true" in output.read_text(encoding="utf-8")

    export = _run_step("Export reconciliation patch", scratch_repo, output)
    assert export.returncode == 0
    patch = (scratch_repo / "repository-reconcile.patch").read_text(encoding="utf-8")
    assert "+b" in patch

    fail = _run_step("Fail on derived-state drift", scratch_repo, output)
    assert fail.returncode == 1
    assert "::error" in fail.stdout


def test_no_drift_reports_unchanged(scratch_repo: Path, tmp_path: Path) -> None:
    output = tmp_path / "github_output"
    detect = _run_step("Detect reconciliation changes", scratch_repo, output)
    assert detect.returncode == 0
    assert output.read_text(encoding="utf-8").strip() == "changed=false"
