"""Structure-validation tests for the L9 Biome static-check capability.

Biome itself is an external binary/npm package (no bundled Python checker),
so these tests validate the *shape* of the checked-in artifacts: biome.json,
the reusable workflow, and the dogfood caller. They do not invoke the Biome
CLI (that is covered by CI running `biome ci` directly).

Run: pytest tests/biome -q
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BIOME_JSON = ROOT / "biome.json"
REUSABLE_WORKFLOW = ROOT / ".github" / "workflows" / "l9-biome-scan.yml"
DOGFOOD_WORKFLOW = ROOT / ".github" / "workflows" / "l9-biome-scan-dogfood.yml"
CALLER_TEMPLATE = ROOT / "docs" / "templates" / "l9-biome-scan-caller.yml"


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_biome_json_exists_and_is_valid_json() -> None:
    assert BIOME_JSON.is_file(), "biome.json must live at the repository root"
    with BIOME_JSON.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)


def test_biome_json_enables_formatter_linter_and_import_organization() -> None:
    payload = json.loads(BIOME_JSON.read_text(encoding="utf-8"))
    assert payload["formatter"]["enabled"] is True
    assert payload["linter"]["enabled"] is True
    assert payload["linter"]["rules"]["preset"] == "recommended"
    assert payload["assist"]["actions"]["source"]["organizeImports"] == "on"
    assert payload["vcs"]["useIgnoreFile"] is True


def test_biome_json_excludes_test_fixture_directories() -> None:
    payload = json.loads(BIOME_JSON.read_text(encoding="utf-8"))
    includes = payload["files"]["includes"]
    assert "!tests/fixtures" in includes
    assert "!tests/compatibility/fixtures" in includes


def test_reusable_workflow_is_workflow_call_with_read_only_permissions() -> None:
    doc = load_yaml(REUSABLE_WORKFLOW)
    # PyYAML parses the bare `on:` key as boolean True; GitHub Actions still
    # reads it as the literal `on` trigger key.
    triggers = doc.get("on", doc.get(True))
    assert "workflow_call" in triggers
    assert doc["permissions"] == {"contents": "read"}


def test_reusable_workflow_enforce_biome_input_defaults_to_false() -> None:
    doc = load_yaml(REUSABLE_WORKFLOW)
    triggers = doc.get("on", doc.get(True))
    inputs = triggers["workflow_call"]["inputs"]
    assert inputs["enforce-biome"]["type"] == "boolean"
    assert inputs["enforce-biome"]["default"] is False
    assert inputs["scan-path"]["default"] == "."


def test_reusable_workflow_has_no_external_actions() -> None:
    doc = load_yaml(REUSABLE_WORKFLOW)
    for job in doc["jobs"].values():
        for step in job.get("steps", []):
            assert "uses" not in step, f"unexpected external action: {step}"


def test_reusable_workflow_pins_biome_version_and_checksum() -> None:
    doc = load_yaml(REUSABLE_WORKFLOW)
    env = doc["env"]
    assert env["BIOME_VERSION"] == "2.5.5"
    checksum = env["BIOME_LINUX_X64_SHA256"]
    assert len(checksum) == 64
    assert all(c in "0123456789abcdef" for c in checksum)


def test_dogfood_workflow_calls_local_reusable_workflow() -> None:
    doc = load_yaml(DOGFOOD_WORKFLOW)
    job = doc["jobs"]["biome-scan"]
    assert job["uses"] == "./.github/workflows/l9-biome-scan.yml"
    assert job["with"]["enforce-biome"] is False
    assert doc["permissions"] == {"contents": "read"}


def test_caller_template_pins_placeholder_sdk_sha_and_is_advisory() -> None:
    doc = load_yaml(CALLER_TEMPLATE)
    job = doc["jobs"]["biome-scan"]
    uses = job["uses"]
    assert uses.startswith("Quantum-L9/l9-ci-sdk/.github/workflows/l9-biome-scan.yml@")
    sha = uses.rsplit("@", 1)[1]
    assert len(sha) == 40
    assert job["with"]["enforce-biome"] is False


def test_precommit_config_registers_biome_check_hook() -> None:
    precommit = load_yaml(ROOT / ".pre-commit-config.yaml")
    local_repo = next(repo for repo in precommit["repos"] if repo["repo"] == "local")
    hook = next(h for h in local_repo["hooks"] if h["id"] == "biome-check")
    assert hook["language"] == "node"
    assert hook["additional_dependencies"] == ["@biomejs/biome@2.5.5"]
