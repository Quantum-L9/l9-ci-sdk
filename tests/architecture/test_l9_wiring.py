"""Guardrails over this repo's l9-ci-core workflow wiring (ported from PR #16).

These tests keep the L9 analysis callers, the self-validation workflow, and
governance honest so a careless edit cannot silently drift the repo out of
correctness with respect to l9-ci-core:

* every Core / external action reference is pinned to an immutable commit SHA
  (covers ci.yml too, so the AUD-008 pinning cannot regress);
* non-actions references point only at l9-ci-core (no rogue third-party org);
* least-privilege permissions (``contents: read``; only publishing surfaces
  may hold ``checks: write``);
* every ``l9-analysis*.yml`` caller is a thin ``workflow_call`` consumer of
  Core's reusable ``analyze-semgrep.yml`` (AUD-006): a single job whose only
  step surface is the pinned ``uses:`` reference, with no inline Semgrep
  installation, SDK provisioning, SDK command execution, artifact routing,
  or publication;
* all five callers pin the *same* immutable Core commit;
* each caller's ``profile`` / ``matrix-id`` inputs are unique, consistent
  with the contract, and declared in governance;
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
CORE_ANALYSIS_WORKFLOW = f"{CORE_REPO}/.github/workflows/analyze-semgrep.yml"
_USES = re.compile(r"^\s*uses:\s*(?P<ref>\S+)")
_SHA_PIN = re.compile(r"@[0-9a-fA-F]{40}$")
_WRITE_SCOPE = re.compile(
    r"(?m)^\s+(actions|checks|contents|deployments|discussions|"
    r"id-token|issues|packages|pages|pull-requests|"
    r"repository-projects|security-events|statuses):\s+write"
)

# Contract expectations for each thin caller (see .l9/integration-contract.yaml).
_EXPECTED_CALLERS: dict[str, dict[str, str]] = {
    "l9-analysis.yml": {"profile": "pr_fast", "matrix-id": "pr-semgrep"},
    "l9-analysis-merge.yml": {"profile": "merge", "matrix-id": "merge-semgrep"},
    "l9-analysis-nightly.yml": {
        "profile": "nightly",
        "matrix-id": "nightly-semgrep",
    },
    "l9-analysis-release.yml": {
        "profile": "release",
        "matrix-id": "release-semgrep",
    },
    "l9-analysis-supply-chain.yml": {
        "profile": "supply_chain",
        "matrix-id": "supply-chain-semgrep",
    },
}

# Operations the thin callers must never perform inline (Core owns them).
_FORBIDDEN_CALLER_PATTERNS: dict[str, str] = {
    "inline semgrep execution": r"\bsemgrep\s+(scan|ci)\b",
    "inline semgrep install": r"pip3?\s+install[^\n]*semgrep",
    "inline SDK execution": r"\bl9-ci\s+(semgrep|bundle|gate|manifest|compatibility)\b"
    r"|python3?\s+-m\s+l9_ci",
    "inline artifact upload": r"actions/upload-artifact",
    "inline checkout": r"actions/checkout",
    "run steps": r"(?m)^\s*run:",
}


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


def _caller_analysis_job(caller: Path) -> dict[str, Any]:
    jobs = _load(caller)["jobs"]
    assert list(jobs) == ["analysis"], (
        f"{caller.name} must define exactly one job named 'analysis'; "
        f"found {sorted(jobs)}"
    )
    job: dict[str, Any] = jobs["analysis"]
    return job


def test_analysis_callers_exist() -> None:
    assert CALLERS, "expected .github/workflows/l9-analysis*.yml caller(s)"
    assert sorted(path.name for path in CALLERS) == sorted(_EXPECTED_CALLERS), (
        "analysis caller set drifted from the integration contract"
    )


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
    # PR caller: Core publishes the gate summary as a PR comment/check.
    "l9-analysis.yml": {"pull-requests"},
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


@pytest.mark.parametrize("caller", CALLERS, ids=[path.name for path in CALLERS])
def test_caller_is_thin_core_workflow_call(caller: Path) -> None:
    """AUD-006: callers delegate everything to Core's reusable workflow."""
    job = _caller_analysis_job(caller)
    uses = job.get("uses", "")
    assert uses.startswith(f"{CORE_ANALYSIS_WORKFLOW}@"), (
        f"{caller.name} must call {CORE_ANALYSIS_WORKFLOW} via 'uses'; got {uses!r}"
    )
    assert _SHA_PIN.search(uses), (
        f"{caller.name} must pin the Core reusable workflow to a 40-hex SHA"
    )
    assert "steps" not in job, (
        f"{caller.name} must not define inline steps; Core owns orchestration"
    )
    text = caller.read_text(encoding="utf-8")
    for label, pattern in _FORBIDDEN_CALLER_PATTERNS.items():
        assert not re.search(pattern, text), (
            f"{caller.name} contains forbidden {label} (Core owns this operation)"
        )


def test_callers_pin_identical_core_commit() -> None:
    pins = {
        caller.name: _caller_analysis_job(caller)["uses"].rsplit("@", 1)[-1]
        for caller in CALLERS
    }
    assert len(set(pins.values())) == 1, (
        f"all callers must pin the same immutable Core commit: {pins}"
    )


@pytest.mark.parametrize("caller", CALLERS, ids=[path.name for path in CALLERS])
def test_caller_inputs_match_contract(caller: Path) -> None:
    job = _caller_analysis_job(caller)
    with_inputs = job.get("with", {})
    expected = _EXPECTED_CALLERS[caller.name]
    assert with_inputs.get("profile") == expected["profile"], (
        f"{caller.name}: profile input must be {expected['profile']!r}"
    )
    assert with_inputs.get("matrix-id") == expected["matrix-id"], (
        f"{caller.name}: matrix-id input must be {expected['matrix-id']!r}"
    )
    for required in ("language", "semgrep-version", "repository-revision"):
        assert required in with_inputs, (
            f"{caller.name}: missing required reusable-workflow input {required!r}"
        )


def test_caller_matrix_ids_are_unique() -> None:
    matrix_ids = [
        _caller_analysis_job(caller).get("with", {}).get("matrix-id")
        for caller in CALLERS
    ]
    assert len(matrix_ids) == len(set(matrix_ids)), (
        f"matrix-id values must be unique across callers: {matrix_ids}"
    )


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
    profile = _caller_analysis_job(caller).get("with", {}).get("profile")
    assert profile in profiles, (
        f"{caller.name} uses profile {profile!r} absent from execution-profiles.yaml"
    )
