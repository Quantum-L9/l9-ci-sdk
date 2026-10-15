"""The SDK's own toolchain pins agree with each other (ADR 0017).

Core owns organization tool-version selection; these pins govern only this
repository. They still have to agree inside the repository, or a hook would run
a different ruff than the one CI gates on, and the self-CI Semgrep pin has to
be a version the SDK's normalizer is validated for. Nothing here reads Core
files: alignment with Core's lock is checked by Core's own toolchain-alignment
step, which runs on this repository.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml

from l9_ci.providers.semgrep.versioning import (
    DEFAULT_SEMGREP_VERSION_POLICY,
    parse_semgrep_version,
)

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
REQUIREMENTS_CI = ROOT / "requirements-ci.txt"
PRECOMMIT = ROOT / ".pre-commit-config.yaml"
SELF_CI = ROOT / ".github" / "workflows" / "l9-self-ci.yml"

RUFF_PIN = re.compile(r"^ruff==(\S+)$")


def _pyproject_ruff() -> str:
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    pins = [
        match.group(1)
        for requirement in pyproject["project"]["optional-dependencies"]["ci"]
        if (match := RUFF_PIN.match(requirement))
    ]
    assert len(pins) == 1, f"expected one exact ruff pin in [ci]: {pins}"
    return pins[0]


def _requirements_ci_ruff() -> str:
    pins = [
        match.group(1)
        for line in REQUIREMENTS_CI.read_text(encoding="utf-8").splitlines()
        if (match := RUFF_PIN.match(line.strip()))
    ]
    assert len(pins) == 1, f"expected one exact ruff pin: {pins}"
    return pins[0]


def _ruff_hook_rev() -> str:
    precommit = yaml.safe_load(PRECOMMIT.read_text(encoding="utf-8"))
    revs = [
        repo["rev"]
        for repo in precommit["repos"]
        if repo["repo"] == "https://github.com/astral-sh/ruff-pre-commit"
    ]
    assert len(revs) == 1, f"expected one ruff-pre-commit repo: {revs}"
    return str(revs[0])


def test_ruff_hook_rev_matches_the_ci_pins() -> None:
    pyproject = _pyproject_ruff()
    assert _requirements_ci_ruff() == pyproject, (
        "requirements-ci.txt and pyproject.toml [ci] pin different ruff versions"
    )
    assert _ruff_hook_rev() == f"v{pyproject}", (
        "the ruff-pre-commit rev must run the ruff CI gates on "
        f"(v{pyproject}); bump them together"
    )


def test_self_ci_semgrep_pin_is_inside_the_supported_range() -> None:
    workflow = yaml.safe_load(SELF_CI.read_text(encoding="utf-8"))
    pins = [
        job["env"]["L9_SEMGREP_VERSION"]
        for job in workflow["jobs"].values()
        if "L9_SEMGREP_VERSION" in job.get("env", {})
    ]
    assert pins, "l9-self-ci.yml no longer pins L9_SEMGREP_VERSION"
    for raw in pins:
        assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", raw), (
            f"self-CI Semgrep pin must be exact: {raw!r}"
        )
        assert DEFAULT_SEMGREP_VERSION_POLICY.supports(parse_semgrep_version(raw)), (
            f"self-CI Semgrep {raw} is outside DEFAULT_SEMGREP_VERSION_POLICY"
        )
