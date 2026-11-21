"""Every local pin of a Core lock-owned tool equals Core's lock (lane L1g).

Core owns exact CI tool versions: ``install-consumer-ci/toolchain-lock.json`` in
Quantum-L9/l9-ci-core (ADR 0017). This repository still declares local copies,
because its own self-CI installs its own toolchain and ADR 0016 forbids it from
selecting a Core revision to fetch Core's installer. Those copies drifted
(ruff 0.16.5 and mypy 2.3.1 against a 0.16.1/2.3.0 lock, gitleaks 8.18.4 against
8.24.3, Python 3.11 against 3.12.14), and Dependabot proposed moving them further.

``.l9/core-toolchain-lock.json`` is a verbatim, non-authoritative mirror of
Core's lock. ``MIRROR_SOURCE`` records the Core revision it was copied from and
the file's SHA-256, which equals the digest Core itself records for the lock in
``install-consumer-ci/tool-ownership.json``; editing the mirror without updating
both fails here. Drift between the mirror and Core is reported by Core's
advisory ``check-toolchain-alignment`` step, which runs on this repository.

To move a tool: Core moves its lock first; then copy Core's file over the
mirror, update ``MIRROR_SOURCE`` and bump every pin this test names.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MIRROR = ROOT / ".l9" / "core-toolchain-lock.json"

MIRROR_SOURCE = {
    "repository": "Quantum-L9/l9-ci-core",
    "path": ".github/actions/install-consumer-ci/toolchain-lock.json",
    "revision": "acb734630f4da1e56ac7d7f4e54a437b6de4ae75",
    "sha256": "4f1b5398098780f4a3c9cd416d6a724615c280e15a0719e719fa0a9210b013e2",
}

# Workflow environment variables that pin a lock-owned tool.
_WORKFLOW_ENV_TOOLS = {
    "BIOME_VERSION": "biome",
    "GITLEAKS_VERSION": "gitleaks",
    "L9_SEMGREP_VERSION": "semgrep",
}
_EXACT_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s;#]+)")


@dataclass(frozen=True)
class Declaration:
    tool: str
    value: str
    where: str
    exact: bool = True  # False: a Python minor-version line such as "3.12"


def _lock() -> dict[str, str]:
    data = json.loads(MIRROR.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and all(
        isinstance(value, str) for value in data.values()
    ), "mirror must be Core's flat {tool: version} lock"
    return data


def _requirement_pins(
    lines: list[str], where: str, tools: set[str]
) -> list[Declaration]:
    found = []
    for number, line in enumerate(lines, start=1):
        match = _EXACT_PIN.match(line.strip())
        if match and match.group(1).lower() in tools:
            found.append(
                Declaration(match.group(1).lower(), match.group(2), f"{where}:{number}")
            )
    return found


_ENV_REFERENCE = re.compile(r"^\$\{\{\s*env\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}$")


def _resolve_env(value: str, env: dict[str, object]) -> str:
    """Follow one ``${{ env.NAME }}`` reference; anything else is returned as is.

    A value that still holds an expression after this (for example a repository
    variable fallback) cannot be proved equal to the lock, so it counts as drift.
    """
    match = _ENV_REFERENCE.match(value.strip())
    if match and match.group(1) in env:
        return str(env[match.group(1)])
    return value


def declarations(root: Path, tools: set[str]) -> list[Declaration]:
    """Every local declaration of a lock-owned tool under ``root``."""
    found: list[Declaration] = []

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    groups = pyproject.get("project", {}).get("optional-dependencies", {})
    for group, requirements in sorted(groups.items()):
        found += _requirement_pins(
            list(requirements), f"pyproject.toml [{group}]", tools
        )
    for group, requirements in sorted(pyproject.get("dependency-groups", {}).items()):
        found += _requirement_pins(
            [r for r in requirements if isinstance(r, str)],
            f"pyproject.toml dependency-groups.{group}",
            tools,
        )

    for path in sorted(root.glob("requirements*.txt")) + sorted(
        root.glob("constraints*.txt")
    ):
        found += _requirement_pins(
            path.read_text(encoding="utf-8").splitlines(), path.name, tools
        )

    uv_lock = root / "uv.lock"
    if uv_lock.exists():
        for package in tomllib.loads(uv_lock.read_text(encoding="utf-8")).get(
            "package", []
        ):
            if package.get("name") in tools:
                found.append(
                    Declaration(package["name"], package["version"], "uv.lock")
                )

    precommit_path = root / ".pre-commit-config.yaml"
    if precommit_path.exists():
        precommit = yaml.safe_load(precommit_path.read_text(encoding="utf-8"))
        for repo in precommit.get("repos", []):
            url = str(repo.get("repo", ""))
            if url == "https://github.com/astral-sh/ruff-pre-commit":
                found.append(
                    Declaration(
                        "ruff",
                        str(repo["rev"]).removeprefix("v"),
                        ".pre-commit-config.yaml ruff-pre-commit",
                    )
                )
            for hook in repo.get("hooks", []):
                for dependency in hook.get("additional_dependencies", []):
                    if str(dependency).startswith("@biomejs/biome@"):
                        found.append(
                            Declaration(
                                "biome",
                                str(dependency).split("@")[-1],
                                f".pre-commit-config.yaml {hook['id']}",
                            )
                        )

    biome = root / "biome.json"
    if biome.exists():
        schema = json.loads(biome.read_text(encoding="utf-8")).get("$schema", "")
        match = re.search(r"/schemas/([^/]+)/schema\.json$", schema)
        if match:
            found.append(Declaration("biome", match.group(1), "biome.json $schema"))

    for workflow in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        document = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
        workflow_env = document.get("env") or {}
        scopes = [("", document.get("env") or {})] + [
            (f" jobs.{name}", job.get("env") or {})
            for name, job in (document.get("jobs") or {}).items()
        ]
        for scope, env in scopes:
            for key, tool in _WORKFLOW_ENV_TOOLS.items():
                if key in env:
                    found.append(
                        Declaration(
                            tool, str(env[key]), f"{workflow.name}{scope} {key}"
                        )
                    )
        for name, job in (document.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                uses = str(step.get("uses", ""))
                version = (step.get("with") or {}).get("python-version")
                if uses.startswith("actions/setup-python@") and version is not None:
                    value = _resolve_env(
                        str(version), {**workflow_env, **(job.get("env") or {})}
                    )
                    found.append(
                        Declaration(
                            "python",
                            value,
                            f"{workflow.name} jobs.{name} setup-python",
                            exact=value.count(".") >= 2 or "${{" in value,
                        )
                    )
    return found


def drift(found: list[Declaration], lock: dict[str, str]) -> list[str]:
    """Return one message per declaration that disagrees with ``lock``."""
    problems = []
    for item in found:
        locked = lock[item.tool]
        if item.exact:
            agrees = item.value == locked
        else:
            agrees = locked.startswith(f"{item.value}.")
        if not agrees:
            problems.append(f"{item.where}: {item.tool} {item.value} != lock {locked}")
    return problems


def test_mirror_is_the_recorded_core_lock() -> None:
    digest = hashlib.sha256(MIRROR.read_bytes()).hexdigest()
    assert digest == MIRROR_SOURCE["sha256"], (
        ".l9/core-toolchain-lock.json is not the byte-for-byte copy of Core's lock "
        f"at {MIRROR_SOURCE['revision']}; copy Core's file and update MIRROR_SOURCE"
    )


def test_every_local_pin_equals_the_core_lock() -> None:
    lock = _lock()
    found = declarations(ROOT, set(lock))
    assert drift(found, lock) == []


def test_the_scan_sees_every_declaration_this_repository_carries() -> None:
    """Guard the scanner itself: an empty or shrunken scan would pass vacuously."""
    seen = {
        (item.tool, item.where.split(":")[0])
        for item in declarations(ROOT, set(_lock()))
    }
    for expected in [
        ("ruff", "pyproject.toml [ci]"),
        ("mypy", "pyproject.toml [ci]"),
        ("pytest", "pyproject.toml [ci]"),
        ("ruff", "requirements-ci.txt"),
        ("mypy", "requirements-ci.txt"),
        ("ruff", "uv.lock"),
        ("mypy", "uv.lock"),
        ("ruff", ".pre-commit-config.yaml ruff-pre-commit"),
        ("python", "l9-self-ci.yml jobs.classify setup-python"),
        ("biome", "biome.json $schema"),
        ("biome", "l9-biome-scan-dogfood.yml BIOME_VERSION"),
        ("gitleaks", "l9-self-ci.yml GITLEAKS_VERSION"),
        ("python", "ci.yml jobs.validate setup-python"),
    ]:
        assert expected in seen, f"scan missed {expected}"


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            {"requirements-ci.txt": "ruff==0.16.5\n"},
            ["requirements-ci.txt:1: ruff 0.16.5 != lock 0.16.1"],
        ),
        (
            {
                ".github/workflows/ci.yml": (
                    "jobs:\n  t:\n    steps:\n"
                    "      - uses: actions/setup-python@abc\n"
                    "        with:\n          python-version: '3.11'\n"
                )
            },
            ["ci.yml jobs.t setup-python: python 3.11 != lock 3.12.14"],
        ),
        (
            {
                ".github/workflows/s.yml": "env:\n  GITLEAKS_VERSION: '8.18.4'\njobs: {}\n"
            },
            ["s.yml GITLEAKS_VERSION: gitleaks 8.18.4 != lock 8.24.3"],
        ),
        (
            {
                ".github/workflows/v.yml": (
                    "env:\n  PYTHON_VERSION: ${{ vars.PYTHON_VERSION || '3.12' }}\n"
                    "jobs:\n  t:\n    steps:\n"
                    "      - uses: actions/setup-python@abc\n"
                    "        with:\n          python-version: ${{ env.PYTHON_VERSION }}\n"
                )
            },
            [
                "v.yml jobs.t setup-python: python "
                "${{ vars.PYTHON_VERSION || '3.12' }} != lock 3.12.14"
            ],
        ),
    ],
)
def test_known_bad_pins_are_reported(
    tmp_path: Path, files: dict[str, str], expected: list[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    lock = {"ruff": "0.16.1", "python": "3.12.14", "gitleaks": "8.24.3"}
    assert drift(declarations(tmp_path, set(lock)), lock) == expected


def test_known_good_pins_pass(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\n[project.optional-dependencies]\nci=['ruff==0.16.1']\n",
        encoding="utf-8",
    )
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "jobs:\n  t:\n    steps:\n      - uses: actions/setup-python@abc\n"
        "        with:\n          python-version: '3.12'\n",
        encoding="utf-8",
    )
    lock = {"ruff": "0.16.1", "python": "3.12.14"}
    found = declarations(tmp_path, set(lock))
    assert len(found) == 2
    assert drift(found, lock) == []
