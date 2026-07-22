"""Guardrails over this repo's l9-ci-core workflow wiring (ported from PR #16).

These tests keep the L9 analysis callers, the self-validation workflow, and
governance honest so a careless edit cannot silently drift the repo out of
correctness with respect to l9-ci-core:

* every Core / external action reference is pinned to an immutable commit SHA
  (covers ci.yml too, so the AUD-008 pinning cannot regress);
* non-actions references point only at l9-ci-core (no rogue third-party org);
* least-privilege permissions (``contents: read``; only a publishing job may
  hold ``checks: write``);
* each caller's profile / matrix id are consistent with what it hands to
  publish-analysis.yml (a silent mismatch breaks publication);
* governance files parse as JSON and declare the profiles the callers use;
* semgrep is actually configured (``--config`` present).

Originally proposed as a standalone workflow + unittest module in PR #16;
folded into the canonical architecture suite so the invariants run under the
same self-validation gate (ci.yml) as every other architecture test, instead
of adding a second, separately-maintained checker.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GOVERNANCE = REPO_ROOT / ".github" / "governance"
CALLERS = sorted(WORKFLOWS.glob("l9-analysis*.yml"))
ALL_WORKFLOWS = sorted(WORKFLOWS.glob("*.yml"))

CORE_REPO = "Quantum-L9/l9-ci-core"
_USES = re.compile(r"^\s*uses:\s*(?P<ref>\S+)")
_SHA_PIN = re.compile(r"@[0-9a-fA-F]{40}$")
_WRITE_SCOPE = re.compile(
    r"(?m)^\s+(actions|checks|contents|deployments|discussions|"
    r"id-token|issues|packages|pages|pull-requests|"
    r"repository-projects|security-events|statuses):\s+write"
)


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def _uses_refs(path: Path) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _USES.match(line)
        if not match:
            continue
        ref = match.group("ref").split("#", 1)[0].strip()
        yield number, ref


def test_analysis_callers_exist() -> None:
    assert CALLERS, "expected .github/workflows/l9-analysis*.yml caller(s)"


def test_every_action_reference_is_sha_pinned() -> None:
    # Applies to ALL workflows (including ci.yml), not only the analysis
    # callers: a mutable tag anywhere is a supply-chain hole (AUD-008).
    offenders = [
        f"{workflow.name}:{number}:{ref}"
        for workflow in ALL_WORKFLOWS
        for number, ref in _uses_refs(workflow)
        if not ref.startswith("./") and not _SHA_PIN.search(ref)
    ]
    assert offenders == [], f"unpinned refs (need @<40-hex sha>): {offenders}"


def test_non_action_references_target_core_only() -> None:
    offenders = [
        f"{workflow.name}:{number}:{ref}"
        for workflow in ALL_WORKFLOWS
        for number, ref in _uses_refs(workflow)
        if not ref.startswith("./")
        and not ref.startswith("actions/")
        and not ref.startswith(f"{CORE_REPO}/")
    ]
    assert offenders == [], f"non-Core, non-actions refs: {offenders}"


@pytest.mark.parametrize(
    "workflow", ALL_WORKFLOWS, ids=[path.name for path in ALL_WORKFLOWS]
)
def test_least_privilege_permissions(workflow: Path) -> None:
    text = workflow.read_text(encoding="utf-8")
    assert re.search(r"(?m)^\s*contents:\s+read\s*$", text), (
        f"{workflow.name} must declare 'contents: read'"
    )
    scopes = set(_WRITE_SCOPE.findall(text))
    forbidden = scopes - {"checks"}
    assert forbidden == set(), (
        f"{workflow.name} requests forbidden write scopes: {sorted(forbidden)}"
    )


@pytest.mark.parametrize("caller", CALLERS, ids=[path.name for path in CALLERS])
def test_profile_and_matrix_are_consistent_with_publish(caller: Path) -> None:
    data = _load(caller)
    env = data.get("env", {})
    profile = env.get("L9_PROFILE")
    matrix = env.get("L9_MATRIX_ID")
    assert profile is not None, f"{caller.name} missing env.L9_PROFILE"
    assert matrix is not None, f"{caller.name} missing env.L9_MATRIX_ID"
    publish_with = data["jobs"]["publish"].get("with", {})
    assert profile == publish_with.get("profile"), (
        f"{caller.name}: L9_PROFILE != publish 'profile' input"
    )
    assert matrix == publish_with.get("matrix-id"), (
        f"{caller.name}: L9_MATRIX_ID != publish 'matrix-id' input"
    )


@pytest.mark.parametrize("caller", CALLERS, ids=[path.name for path in CALLERS])
def test_semgrep_config_is_present(caller: Path) -> None:
    assert "--config" in caller.read_text(encoding="utf-8"), (
        f"{caller.name} runs semgrep without --config"
    )


def test_governance_files_are_valid_json() -> None:
    files = sorted(GOVERNANCE.glob("*.yaml"))
    assert files, "no .github/governance/*.yaml files found"
    for path in files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            pytest.fail(f"{path.name} is not valid JSON: {error}")


@pytest.mark.parametrize("caller", CALLERS, ids=[path.name for path in CALLERS])
def test_caller_profiles_are_declared_in_governance(caller: Path) -> None:
    profiles = json.loads(
        (GOVERNANCE / "execution-profiles.yaml").read_text(encoding="utf-8")
    )["profiles"]
    profile = _load(caller).get("env", {}).get("L9_PROFILE")
    assert profile in profiles, (
        f"{caller.name} uses profile {profile!r} absent from execution-profiles.yaml"
    )
