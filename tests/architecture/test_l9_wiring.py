"""Guardrails over this repo's GitHub Actions wiring (ported from PR #16).

Organization L9 analysis of this repository is executed by the GitHub
organization required-workflow ruleset from ``Quantum-L9/l9-ci-core`` ``main``
``.github/workflows/org-ci.yml`` (ADR-0016). Nothing in this tree selects a
Core or SDK revision, so these tests keep the remaining repository-owned
workflows honest and make sure the consumer-owned Core wiring the migration
removed cannot quietly regrow:

* no workflow references ``Quantum-L9/l9-ci-core``, ``L9_CORE_REF``, or
  ``L9_SDK_REF``, and no ``l9-analysis*`` / ``l9-nightly`` caller returns
  (any of these re-creates a consumer-owned Core revision);
* every external action reference is pinned to an immutable commit SHA
  (covers ci.yml too, so the AUD-008 pinning cannot regress);
* external references come only from an explicit vendor allow-list (no rogue
  third-party org); this repository's own reusable workflows are called by
  local ``./`` path, never by an SDK SHA;
* least-privilege permissions (``contents: read``; write scopes stay
  explicitly bounded per workflow);
* governance files parse as JSON.

Workflow discovery is extension-complete: GitHub runs both ``*.yml`` and
``*.yaml`` under ``.github/workflows``, so a guard that globbed only ``*.yml``
could be evaded by a ``.yaml`` caller. Discovery and ``uses:`` parsing reuse
``lint/check_action_pins.py`` (the yaml-governance action-pin checker) so the
two do not drift into subtly different grammars.

Originally proposed as a standalone workflow + unittest module in PR #16;
folded into the canonical architecture suite so the invariants run under the
same self-validation gate (ci.yml) as every other architecture test, instead
of adding a second, separately-maintained checker.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GOVERNANCE = REPO_ROOT / ".github" / "governance"

WORKFLOW_EXTENSIONS = (".yml", ".yaml")


def _load_action_pins_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "l9_lint_check_action_pins", REPO_ROOT / "lint" / "check_action_pins.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ACTION_PINS = _load_action_pins_module()
# Canonical `uses:` grammar shared with the action-pin checker: optional list
# dash, optional quotes, ref up to whitespace/quote/comment.
_USES = _ACTION_PINS.USES
_LOCAL_PREFIXES: tuple[str, ...] = tuple(_ACTION_PINS.LOCAL_PREFIXES)
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
# Stems of the removed Core callers. Behaviour, not the filename, decides
# ownership, but a returning caller under its old name is the likeliest shape.
_REMOVED_CALLER_STEMS = re.compile(r"^(l9-analysis.*|l9-nightly)$")


def workflow_files(root: Path) -> list[Path]:
    """Every workflow GitHub would run under ``root``: ``*.yml`` and ``*.yaml``."""
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix in WORKFLOW_EXTENSIONS
    )


ALL_WORKFLOWS = workflow_files(WORKFLOWS)


def _uses_refs(path: Path) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _USES.match(line)
        if not match:
            continue
        yield number, match.group(1)


def _is_local(ref: str) -> bool:
    return ref.startswith(_LOCAL_PREFIXES)


def test_workflow_discovery_is_extension_complete(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text("name: a\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("name: b\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.yml").write_text("name: c\n", encoding="utf-8")
    assert [path.name for path in workflow_files(tmp_path)] == ["a.yml", "b.yaml"]


def test_uses_grammar_matches_step_and_job_forms() -> None:
    # Step form (list item), job form (mapping value), quoted, and commented.
    cases = {
        "      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567  # v4": (
            "actions/checkout@0123456789abcdef0123456789abcdef01234567"
        ),
        "    uses: ./.github/workflows/l9-biome-scan.yml": (
            "./.github/workflows/l9-biome-scan.yml"
        ),
        "  - uses: 'pypa/gh-action-pypi-publish@0123456789abcdef0123456789abcdef01234567'": (
            "pypa/gh-action-pypi-publish@0123456789abcdef0123456789abcdef01234567"
        ),
    }
    for line, expected in cases.items():
        match = _USES.match(line)
        assert match is not None, line
        assert match.group(1) == expected
    assert _USES.match("      # uses: not/a-ref@v1") is None


def test_workflows_exist() -> None:
    assert ALL_WORKFLOWS, "expected repository-owned workflows under .github/workflows"


def test_no_core_caller_workflow_returns() -> None:
    returned = sorted(
        path.name for path in ALL_WORKFLOWS if _REMOVED_CALLER_STEMS.match(path.stem)
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
        if not _is_local(ref) and not _SHA_PIN.search(ref)
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
        if not _is_local(ref)
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
