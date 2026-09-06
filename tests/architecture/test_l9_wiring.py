"""Guardrails over this repo's GitHub Actions wiring (ported from PR #16).

Organization L9 analysis of this repository is executed by the GitHub
organization required-workflow ruleset from ``Quantum-L9/l9-ci-core`` ``main``
``.github/workflows/org-ci.yml`` (ADR-0016). Nothing in this tree selects a
Core or SDK revision, so these tests keep the remaining repository-owned
workflows honest and make sure the consumer-owned Core wiring the migration
removed cannot quietly regrow:

* no workflow references ``Quantum-L9/l9-ci-core``, ``L9_CORE_REF``, or
  ``L9_SDK_REF``, and no ``l9-analysis*.yml`` / ``l9-nightly.yml`` caller
  returns (any of these re-creates a consumer-owned Core revision);
* every external action reference is pinned to an immutable commit SHA
  (covers ci.yml too, so the AUD-008 pinning cannot regress);
* external references come only from an explicit vendor allow-list (no rogue
  third-party org); this repository's own reusable workflows are called by
  local ``./`` path, never by an SDK SHA;
* least-privilege permissions (``contents: read``; write scopes stay
  explicitly bounded per workflow);
* governance files parse as JSON.

Originally proposed as a standalone workflow + unittest module in PR #16;
folded into the canonical architecture suite so the invariants run under the
same self-validation gate (ci.yml) as every other architecture test, instead
of adding a second, separately-maintained checker.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GOVERNANCE = REPO_ROOT / ".github" / "governance"
ALL_WORKFLOWS = sorted(WORKFLOWS.glob("*.yml"))

_USES = re.compile(r"^\s*uses:\s*(?P<ref>\S+)")
_SHA_PIN = re.compile(r"@[0-9a-fA-F]{40}$")
_WRITE_SCOPE = re.compile(
    r"(?m)^\s+(actions|checks|contents|deployments|discussions|"
    r"id-token|issues|packages|pages|pull-requests|"
    r"repository-projects|security-events|statuses):\s+write"
)

# Consumer-owned organization CI ownership markers. Any of these in a workflow
# means this repository is again selecting a Core or SDK revision for
# organization CI, which the org ruleset owns (ADR-0016).
_ORG_CI_OWNERSHIP_MARKERS = (
    "Quantum-L9/l9-ci-core",
    "L9_CORE_REF",
    "L9_SDK_REF",
)
# Filenames of the removed Core callers. Behaviour, not the filename, decides
# ownership, but a returning caller under its old name is the likeliest shape.
_REMOVED_CALLER_GLOBS = ("l9-analysis*.yml", "l9-nightly.yml")


def _uses_refs(path: Path) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _USES.match(line)
        if not match:
            continue
        ref = match.group("ref").split("#", 1)[0].strip()
        yield number, ref


def test_workflows_exist() -> None:
    assert ALL_WORKFLOWS, "expected repository-owned workflows under .github/workflows"


def test_no_core_caller_workflow_returns() -> None:
    returned = sorted(
        path.name
        for pattern in _REMOVED_CALLER_GLOBS
        for path in WORKFLOWS.glob(pattern)
    )
    assert returned == [], (
        f"Core caller workflows must not return (org ruleset runs Core main "
        f"org-ci.yml directly; ADR-0016): {returned}"
    )


@pytest.mark.parametrize(
    "workflow", ALL_WORKFLOWS, ids=[path.name for path in ALL_WORKFLOWS]
)
def test_no_consumer_owned_core_or_sdk_revision(workflow: Path) -> None:
    # Prose in comments may name Core (provenance notes); only executable
    # lines can select a revision, so comment lines are excluded.
    text = "\n".join(
        line
        for line in workflow.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    offenders = [marker for marker in _ORG_CI_OWNERSHIP_MARKERS if marker in text]
    assert offenders == [], (
        f"{workflow.name} selects a Core/SDK revision for organization CI "
        f"({offenders}); the GitHub org ruleset owns that (ADR-0016)"
    )
    sdk_pins = [
        f"{number}:{ref}"
        for number, ref in _uses_refs(workflow)
        if ref.startswith("Quantum-L9/l9-ci-sdk/")
    ]
    assert sdk_pins == [], (
        f"{workflow.name} pins this repository's own reusable workflow by SDK "
        f"SHA; dogfood callers use a local ./ path: {sdk_pins}"
    )


def test_every_action_reference_is_sha_pinned() -> None:
    # Applies to ALL workflows (including ci.yml): a mutable tag anywhere is a
    # supply-chain hole (AUD-008).
    offenders = [
        f"{workflow.name}:{number}:{ref}"
        for workflow in ALL_WORKFLOWS
        for number, ref in _uses_refs(workflow)
        if not ref.startswith("./") and not _SHA_PIN.search(ref)
    ]
    assert offenders == [], f"unpinned refs (need @<40-hex sha>): {offenders}"


# Known action vendors used by this repo (still SHA-pinned).
_ALLOWED_EXTERNAL_ACTION_PREFIXES = (
    "actions/",
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


def test_external_references_are_allowlisted_vendors() -> None:
    offenders = [
        f"{workflow.name}:{number}:{ref}"
        for workflow in ALL_WORKFLOWS
        for number, ref in _uses_refs(workflow)
        if not ref.startswith("./")
        and not any(
            ref.startswith(prefix) for prefix in _ALLOWED_EXTERNAL_ACTION_PREFIXES
        )
    ]
    assert offenders == [], f"non-allowlisted external refs: {offenders}"


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
