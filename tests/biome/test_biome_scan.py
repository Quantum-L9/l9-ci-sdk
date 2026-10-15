"""Structure tests for the SDK's own Biome toolchain (ADR 0017).

Biome is this repository's dev toolchain only. Consumers get Biome from Core's
``org-ci.yml``, so this repository must offer no reusable Biome workflow or
caller template. These tests pin that boundary, the shape of the SDK self-CI
job, and a drift guard: the four in-repo copies of the Biome version
(self-CI ``BIOME_VERSION``, the pre-commit hook's ``additional_dependencies``,
``biome.json`` ``$schema``, and the ``npx`` lines in the Biome doc) must agree.
They do not invoke the Biome CLI (CI runs ``biome ci`` directly).

Run: pytest tests/biome -q
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
BIOME_JSON = ROOT / "biome.json"
SELF_CI_WORKFLOW = WORKFLOWS / "l9-biome-scan-dogfood.yml"
REMOVED_REUSABLE = WORKFLOWS / "l9-biome-scan.yml"
CALLER_TEMPLATE = ROOT / "docs" / "templates" / "l9-biome-scan-caller.yml"
BIOME_DOC = ROOT / "docs" / "architecture" / "biome.md"
PRECOMMIT = ROOT / ".pre-commit-config.yaml"

SCHEMA_VERSION = re.compile(r"/schemas/([0-9]+\.[0-9]+\.[0-9]+)/schema\.json$")
NPX_VERSION = re.compile(r"@biomejs/biome@([0-9]+\.[0-9]+\.[0-9]+)")
EXACT_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict), f"{path} is not a YAML mapping"
    return loaded


def triggers(doc: dict[str, Any]) -> Any:
    # PyYAML parses the bare `on:` key as boolean True; GitHub Actions still
    # reads it as the literal `on` trigger key.
    return doc.get("on", doc.get(True))


def workflow_files() -> list[Path]:
    return sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])


def biome_hook() -> dict[str, Any]:
    precommit = load_yaml(PRECOMMIT)
    local_repo = next(repo for repo in precommit["repos"] if repo["repo"] == "local")
    hook: dict[str, Any] = next(
        h for h in local_repo["hooks"] if h["id"] == "biome-check"
    )
    return hook


# --- biome.json ---------------------------------------------------------------


def test_biome_json_exists_and_is_valid_json() -> None:
    assert BIOME_JSON.is_file(), "biome.json must live at the repository root"
    payload = json.loads(BIOME_JSON.read_text(encoding="utf-8"))
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


# --- no consumer-facing Biome surface (ADR 0017) --------------------------------


def test_no_workflow_offers_a_reusable_biome_job() -> None:
    offenders = []
    for path in workflow_files():
        doc = load_yaml(path)
        on = triggers(doc)
        callable_workflow = isinstance(on, dict) and "workflow_call" in on
        callable_workflow = callable_workflow or on == "workflow_call"
        if callable_workflow and "biome" in path.read_text(encoding="utf-8").lower():
            offenders.append(path.name)
    assert offenders == [], (
        "consumers get Biome from Core org-ci.yml; the SDK must not host a "
        f"workflow_call Biome workflow (ADR 0017): {offenders}"
    )


def test_removed_reusable_and_caller_template_stay_removed() -> None:
    assert not REMOVED_REUSABLE.exists()
    assert not CALLER_TEMPLATE.exists()


# --- SDK self-CI job -------------------------------------------------------------


def test_self_ci_runs_on_this_repository_only() -> None:
    doc = load_yaml(SELF_CI_WORKFLOW)
    on = triggers(doc)
    assert set(on) == {"pull_request", "push", "workflow_dispatch"}
    assert on["push"]["branches"] == ["main"]


def test_self_ci_is_read_only_everywhere() -> None:
    doc = load_yaml(SELF_CI_WORKFLOW)
    assert doc["permissions"] == {"contents": "read"}
    for name, job in doc["jobs"].items():
        assert job.get("permissions") == {"contents": "read"}, name


def test_self_ci_has_no_external_or_reusable_actions() -> None:
    doc = load_yaml(SELF_CI_WORKFLOW)
    for name, job in doc["jobs"].items():
        assert "uses" not in job, f"{name} delegates to a reusable workflow"
        for step in job.get("steps", []):
            assert "uses" not in step, f"unexpected action in {name}: {step}"


def test_self_ci_pins_an_exact_version_and_checksum() -> None:
    env = load_yaml(SELF_CI_WORKFLOW)["env"]
    assert EXACT_VERSION.match(env["BIOME_VERSION"])
    checksum = env["BIOME_LINUX_X64_SHA256"]
    assert re.fullmatch(r"[0-9a-f]{64}", checksum)
    text = SELF_CI_WORKFLOW.read_text(encoding="utf-8")
    assert "sha256sum --check" in text
    assert text.index("sha256sum --check") < text.index("chmod +x biome")


def test_self_ci_is_advisory() -> None:
    env = load_yaml(SELF_CI_WORKFLOW)["env"]
    assert env["ENFORCE_BIOME"] == "false"


def test_precommit_config_registers_biome_check_hook() -> None:
    hook = biome_hook()
    assert hook["language"] == "node"
    assert len(hook["additional_dependencies"]) == 1


# --- drift guard ---------------------------------------------------------------


def test_every_in_repo_biome_version_agrees() -> None:
    workflow = load_yaml(SELF_CI_WORKFLOW)["env"]["BIOME_VERSION"]

    (dependency,) = biome_hook()["additional_dependencies"]
    hook_match = NPX_VERSION.fullmatch(f"{dependency}".replace("'", ""))
    assert hook_match, f"unexpected hook dependency: {dependency}"

    schema = json.loads(BIOME_JSON.read_text(encoding="utf-8"))["$schema"]
    schema_match = SCHEMA_VERSION.search(schema)
    assert schema_match, f"biome.json $schema unreadable: {schema}"

    doc_versions = set(NPX_VERSION.findall(BIOME_DOC.read_text(encoding="utf-8")))
    assert doc_versions, "docs/architecture/biome.md shows no npx version"

    found = {
        "self-CI BIOME_VERSION": workflow,
        "pre-commit additional_dependencies": hook_match.group(1),
        "biome.json $schema": schema_match.group(1),
        **{f"biome.md npx ({v})": v for v in sorted(doc_versions)},
    }
    assert len(set(found.values())) == 1, f"Biome version drift: {found}"
