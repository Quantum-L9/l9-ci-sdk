"""Proves the SDK wheel is a faithful, installable artifact -- not just that
the source tree happens to import correctly.

This is the regression guard for a real bug this test caught during
authoring: an unanchored ``artifacts/`` line in ``.gitignore`` (meant only
for the repo-root CI scratch directory the l9-analysis*.yml workflows write
to) also matched ``l9_ci/artifacts/`` at any depth. hatchling's wheel
builder treats gitignore patterns as build-exclusion rules, so it silently
dropped the entire ``l9_ci/artifacts`` module from every built wheel --
`import l9_ci.artifacts` failed in a clean install even though every test in
this suite (which imports it from the source tree via PYTHONPATH/editable
mode, never from a built wheel) passed. Source-tree-only testing cannot
catch this class of defect; only building and installing a real wheel can.
"""

from __future__ import annotations

import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# What ships inside l9_ci/ that must survive into the wheel unchanged. Built
# from the actual source tree (not hand-maintained) so this test fails loud
# the moment a new module, schema, or ruleset file is added to the source
# tree but silently excluded from the packaged artifact -- exactly the class
# of defect it caught once already (see module docstring).
_EXCLUDED_DIR_NAMES = {"__pycache__"}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _source_package_files() -> set[str]:
    package_root = REPO_ROOT / "l9_ci"
    files: set[str] = set()
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in _EXCLUDED_SUFFIXES:
            continue
        if _EXCLUDED_DIR_NAMES & set(path.relative_to(package_root).parts):
            continue
        files.add(path.relative_to(REPO_ROOT).as_posix())
    return files


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a real wheel from this checkout via ``pip wheel``.

    ``--no-deps`` only skips fetching/building wheels for *l9-ci's own*
    runtime dependencies (jsonschema, PyYAML, referencing) -- irrelevant to
    what ends up inside the l9-ci wheel itself, and it keeps this fixture
    fast. Build isolation is left on (no ``--no-build-isolation``) so pip
    resolves the ``hatchling>=1.25.0`` build backend declared in
    ``pyproject.toml`` itself, matching how a real consumer would build this
    package -- not a hand-picked local toolchain.
    """
    dist_dir = tmp_path_factory.mktemp("l9ci-wheel-dist")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(dist_dir),
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"pip wheel build failed (exit {result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    wheels = sorted(dist_dir.glob("l9_ci-*.whl"))
    assert len(wheels) == 1, f"expected exactly one built l9-ci wheel, found {wheels}"
    return wheels[0]


def test_wheel_contains_every_source_package_file(built_wheel: Path) -> None:
    source_files = _source_package_files()
    assert source_files, "expected l9_ci/ to contain package files to compare against"

    with zipfile.ZipFile(built_wheel) as archive:
        wheel_members = set(archive.namelist())

    missing = sorted(source_files - wheel_members)
    assert not missing, (
        "files present in the l9_ci/ source tree are missing from the built "
        f"wheel (packaging silently dropped them): {missing}"
    )


def test_wheel_contains_no_bytecode_cache(built_wheel: Path) -> None:
    with zipfile.ZipFile(built_wheel) as archive:
        leaked = [
            name
            for name in archive.namelist()
            if "__pycache__" in name or name.endswith((".pyc", ".pyo"))
        ]
    assert not leaked, f"built wheel must not contain bytecode cache files: {leaked}"


def test_wheel_installs_cleanly_and_cli_runs_outside_repo(
    built_wheel: Path, tmp_path: Path
) -> None:
    """End-to-end proof: a brand-new venv, with real dependency resolution
    (no ``--no-deps`` this time), installing only the built wheel -- then
    invoking the installed ``l9-ci`` console script from a working
    directory outside this repository entirely. This is the "clean
    build/wheel install outside repo" proof itself, codified so it runs on
    every CI invocation instead of only when a human happens to check by
    hand.
    """
    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    venv_python = venv_dir / "bin" / "python"
    assert venv_python.is_file(), f"expected venv python at {venv_python}"

    install = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", str(built_wheel)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert install.returncode == 0, (
        f"installing built wheel into a clean venv failed "
        f"(exit {install.returncode}):\n"
        f"--- stdout ---\n{install.stdout}\n--- stderr ---\n{install.stderr}"
    )

    outside_repo_cwd = tmp_path / "outside-repo-cwd"
    outside_repo_cwd.mkdir()
    run = subprocess.run(
        [str(venv_python), "-m", "l9_ci", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=outside_repo_cwd,
    )
    assert run.returncode == 0, (
        f"`python -m l9_ci --help` failed from the installed wheel "
        f"(exit {run.returncode}):\n"
        f"--- stdout ---\n{run.stdout}\n--- stderr ---\n{run.stderr}"
    )
    assert "semgrep" in run.stdout, "expected the semgrep subcommand to be registered"

    resolver_check = subprocess.run(
        [
            str(venv_python),
            "-c",
            "from l9_ci.rulesets.semgrep import ruleset_dir, default_identity_map_path, "
            "SUPPORTED_LANGUAGES\n"
            "for language in SUPPORTED_LANGUAGES:\n"
            "    assert list(ruleset_dir(language).glob('*.yml')), language\n"
            "assert default_identity_map_path().is_file()\n"
            "print('packaged-ruleset-resolution-ok')\n",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=outside_repo_cwd,
    )
    assert resolver_check.returncode == 0, (
        "packaged ruleset resolution failed from the installed wheel "
        f"(exit {resolver_check.returncode}):\n"
        f"--- stdout ---\n{resolver_check.stdout}\n--- stderr ---\n{resolver_check.stderr}"
    )
    assert "packaged-ruleset-resolution-ok" in resolver_check.stdout
