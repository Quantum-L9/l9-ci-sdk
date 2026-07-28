#!/usr/bin/env python3
"""Generate commit-bound validation evidence (AUD-007).

Replaces the previously static, hand-maintained VALIDATION_REPORT.json (which
drifted from the tree and carried no commit identity) with evidence generated
from the actual repository state: commit SHA, generation time, Python/tool/
dependency versions, the exact gate commands CI runs, file count, and a
file-tree digest.

MANIFEST.md is a *separate* artifact owned by the `l9-ci manifest generate`
CLI command (see `.github/workflows/l9-manifest-reconcile.yml`, which
auto-commits corrections to PRs) — this script does not generate or touch it,
to avoid two competing, differently-formatted generators fighting over the
same file. `ci.yml` regenerates MANIFEST.md via that CLI command before
running this script, so the two stay consistent.

This records verifiable facts only; it does NOT assert that the gates passed —
that is proven by the CI job (ci.yml) succeeding before this runs. Run:

    python scripts/generate_validation_report.py
"""

from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPO_ROOT / "VALIDATION_REPORT.json"
# Files excluded from the inventory: the generated evidence file itself (self-
# reference would make the digest unstable) and memory-bank/, a local agent
# scratchpad never inventoried by MANIFEST.md either (see
# l9-manifest-reconcile.yml) — keeping the same exclusion here means this
# report's file_count/file_tree_digest are directly comparable to MANIFEST.md.
SELF_GENERATED = {"VALIDATION_REPORT.json"}
EXCLUDED_DIRS = {"memory-bank"}

# The exact gate commands CI runs (AUD-008). Recorded as evidence, not executed
# here.
GATE_COMMANDS = [
    "python -m compileall l9_ci",
    "python -m ruff check l9_ci tests scripts",
    "python -m ruff format --check l9_ci tests scripts",
    "python -m mypy l9_ci",
    "python -m pytest --cov=l9_ci --cov-branch",
]

RUNTIME_DEPENDENCIES = ["jsonschema", "referencing", "PyYAML"]
TOOLCHAIN = ["ruff", "mypy", "pytest", "pytest-cov", "coverage"]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _tracked_files() -> list[str]:
    # `-z` yields NUL-separated, unquoted paths -- plain `git ls-files` quotes
    # (C-style, wrapped in `"..."`) any path with unusual characters, which
    # then fails to open as-is; `-z` avoids that class of bug entirely.
    output = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = [f for f in output.split("\0") if f]
    return sorted(
        f
        for f in files
        if f not in SELF_GENERATED and f.split("/", 1)[0] not in EXCLUDED_DIRS
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _versions(names: list[str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name in names:
        try:
            resolved[name] = version(name)
        except PackageNotFoundError:
            resolved[name] = "not-installed"
    return resolved


def build_report(files: list[str], digests: dict[str, str]) -> dict[str, object]:
    # Deterministic file-tree digest: sha256 over "sha256␣path\n" lines.
    tree = "".join(f"{digests[f]} {f}\n" for f in files)
    file_tree_digest = hashlib.sha256(tree.encode("utf-8")).hexdigest()
    return {
        "schema": "l9.validation-report/v2",
        "repository": "Quantum-L9/l9-ci-sdk",
        "commit": _git("rev-parse", "HEAD"),
        "commit_committed_at": _git("show", "-s", "--format=%cI", "HEAD"),
        "generated_by": "scripts/generate_validation_report.py",
        "validated_by": ".github/workflows/ci.yml",
        # major.minor only — patch level varies across runners and is not part
        # of the reproducible commit-bound identity.
        "python_version": ".".join(sys.version.split()[0].split(".")[:2]),
        "toolchain_versions": _versions(TOOLCHAIN),
        "dependency_versions": _versions(RUNTIME_DEPENDENCIES),
        "gate_commands": GATE_COMMANDS,
        "file_count": len(files),
        "file_tree_digest": file_tree_digest,
    }


def main() -> int:
    files = _tracked_files()
    digests = {f: _sha256(REPO_ROOT / f) for f in files}
    report = build_report(files, digests)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {REPORT_PATH.name} ({len(files)} files inventoried)")
    print(f"commit={report['commit']} file_tree_digest={report['file_tree_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
