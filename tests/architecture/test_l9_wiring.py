"""Guardrails over this repo's l9-ci-core workflow wiring (ported from PR #16).

These tests keep the L9 analysis callers, the self-validation workflow, and
governance honest so a careless edit cannot silently drift the repo out of
correctness with respect to l9-ci-core:

* every Core / external action reference is pinned to an immutable commit SHA
  (covers ci.yml too, so the AUD-008 pinning cannot regress);
* non-actions references point only at l9-ci-core (no rogue third-party org);
* least-privilege permissions (``contents: read``; only a publishing job may
  hold ``checks: write``);
* each caller is a thin reusable-workflow stub that hands its profile /
  matrix id to the Core-owned analyze-semgrep kernel (v2 handoff shape);
* governance files parse as JSON and declare the profiles the callers use.

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


# Known non-Core action vendors used by this repo (still SHA-pinned).
_ALLOWED_EXTERNAL_ACTION_PREFIXES = (
    "actions/",
    f"{CORE_REPO}/",
    "pypa/gh-action-pypi-publish@",
)

# Workflows with intentional elevated write scopes beyond checks:write.
_ALLOWED_WRITE_SCOPES = {
    "l9-manifest-reconcile.yml": {"contents"},  # bot commits MANIFEST.md
    "l9-self-ci.yml": {"pull-requests"},  # marker comment
    "publish.yml": {"id-token", "actions"},  # OIDC publish + download-artifact
}

# Governance companions that are real YAML (not JSON-as-YAML).
_REAL_YAML_GOVERNANCE = frozenset({"rule-modes.selfci.yaml", "l9-ci-shared-spec.yaml"})


def test_non_action_references_target_core_only() -> None:
    offenders = [
        f"{workflow.name}:{number}:{ref}"
        for workflow in ALL_WORKFLOWS
        for number, ref in _uses_refs(workflow)
        if not ref.startswith("./")
        and not any(
            ref.startswith(prefix) for prefix in _ALLOWED_EXTERNAL_ACTION_PREFIXES
        )
    ]
    assert offenders == [], f"non-Core, non-actions refs: {offenders}"


@pytest.mark.parametrize(
    "workflow", ALL_WORKFLOWS, ids=[path.name for path in ALL_WORKFLOWS]
)
def test_least_privilege_permissions(workflow: Path) -> None:
    text = workflow.read_text(encoding="utf-8")
    assert re.search(r"(?m)^\s*contents:\s+(read|write)\s*$", text), (
        f"{workflow.name} must declare contents: read|write"
    )
    scopes = set(_WRITE_SCOPE.findall(text))
    allowed = {"checks"} | _ALLOWED_WRITE_SCOPES.get(workflow.name, set())
    forbidden = scopes - allowed
    assert forbidden == set(), (
        f"{workflow.name} requests forbidden write scopes: {sorted(forbidden)}"
    )


def _caller_analysis_with(caller: Path) -> dict[str, Any]:
    # v2 handoff shape: each caller is a thin stub whose single `analysis`
    # job calls the Core-owned reusable analyze-semgrep kernel with the
    # profile / matrix identity. All provider execution, gating, and
    # publication live in l9-ci-core.
    data = _load(caller)
    jobs = data.get("jobs", {})
    assert set(jobs) == {"analysis"}, (
        f"{caller.name} must contain exactly one 'analysis' job (thin caller)"
    )
    uses = jobs["analysis"].get("uses", "")
    assert uses.startswith(
        f"{CORE_REPO}/.github/workflows/analyze-semgrep.yml@"
    ) and _SHA_PIN.search(uses), (
        f"{caller.name}: analysis job must call the Core analyze-semgrep "
        f"kernel pinned to a 40-hex SHA, got {uses!r}"
    )
    with_block: dict[str, Any] = jobs["analysis"].get("with", {})
    return with_block


@pytest.mark.parametrize("caller", CALLERS, ids=[path.name for path in CALLERS])
def test_caller_is_thin_kernel_stub(caller: Path) -> None:
    with_block = _caller_analysis_with(caller)
    assert with_block.get("profile"), f"{caller.name} missing with.profile"
    assert with_block.get("matrix-id"), f"{caller.name} missing with.matrix-id"
    # Provider execution must not leak back into the stub: no semgrep
    # invocation, provisioning, or publish job may reappear here.
    text = caller.read_text(encoding="utf-8")
    for marker in ("semgrep run", "provision-sdk", "gate evaluate"):
        assert marker not in text.replace("'l9-ci semgrep run'", "").replace(
            "'l9-ci gate evaluate'", ""
        ), f"{caller.name} re-implements kernel logic ({marker!r})"


def test_governance_files_are_valid_json() -> None:
    files = sorted(GOVERNANCE.glob("*.yaml"))
    assert files, "no .github/governance/*.yaml files found"
    for path in files:
        if path.name in _REAL_YAML_GOVERNANCE:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            pytest.fail(f"{path.name} is not valid JSON: {error}")


@pytest.mark.parametrize("caller", CALLERS, ids=[path.name for path in CALLERS])
def test_caller_profiles_are_declared_in_governance(caller: Path) -> None:
    profiles = json.loads(
        (GOVERNANCE / "execution-profiles.yaml").read_text(encoding="utf-8")
    )["profiles"]
    profile = _caller_analysis_with(caller).get("profile")
    assert profile in profiles, (
        f"{caller.name} uses profile {profile!r} absent from execution-profiles.yaml"
    )
