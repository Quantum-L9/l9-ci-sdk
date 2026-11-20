"""Real-Semgrep witnesses for required central runs (lane L1f).

Each case runs ``l9-ci semgrep run`` end to end, with the packaged L9 baseline
profile (no registry download), against a throwaway Git repository and reads
the canonical bundle back:

* known-bad nosem: a line carrying ``# nosemgrep`` still yields its finding
  under ``--required``;
* known-good nosem: the same line is suppressed without ``--required``, and a
  clean line yields nothing either way;
* known-bad scope: a consumer ``.semgrepignore`` that lists ``src/`` does not
  hide a finding in ``src/`` under ``--required``;
* known-good scope: a path the SDK policy declares out of scope (``tests/``)
  stays out, and the scope evidence beside the raw report is schema-valid.

The known-bad source lines are assembled at runtime so that this file holds no
literal match for the rule (this repository's own Semgrep, CodeQL and publish
gate scan tests/). Like the other real-Semgrep tests these skip without a
``semgrep`` executable; the ``semgrep rule fixtures`` step of
.github/workflows/ci.yml runs this file with the self-CI pinned Semgrep.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

# The CI step that runs this file sets L9_REQUIRE_SEMGREP=1: there a missing
# executable is a broken step, not a reason to skip, so the tests run and fail.
_needs_semgrep = pytest.mark.skipif(
    shutil.which("semgrep") is None and os.environ.get("L9_REQUIRE_SEMGREP") != "1",
    reason="semgrep executable not available on PATH",
)

_RULE = "L9-PYTHON-EXEC-EVAL-USE"
_CALL = "ev" + "al"
_BAD = f"{_CALL}(user_input)\n"
_BAD_SUPPRESSED = f"{_CALL}(other_input)  # nosemgrep\n"
_CLEAN = "value = int(user_input)\n"


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *arguments], check=True, capture_output=True
    )


def _repository(root: Path, tree: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "witness@example.invalid")
    _git(root, "config", "user.name", "witness")
    for relative, content in tree.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(root, "add", "--", *tree)
    _git(root, "commit", "-q", "-m", "witness")
    return root


def _findings(root: Path, out: Path, *, required: bool) -> set[tuple[str, int]]:
    command = [
        sys.executable,
        "-m",
        "l9_ci",
        "semgrep",
        "run",
        "--language",
        "python",
        "--profile",
        "l9-baseline",
        "--root",
        str(root),
        "--snapshot-id",
        "witness",
        "--output",
        str(out / "bundle.json"),
        "--raw-output",
        str(out / "raw" / "report.json"),
        "--format",
        "json",
    ]
    if required:
        command.append("--required")
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    bundle = json.loads((out / "bundle.json").read_text(encoding="utf-8"))
    return {
        (location["normalized_path"], location["start_line"])
        for finding in bundle["findings"]
        if finding["canonical_rule_id"] == _RULE
        for location in finding["locations"]
    }


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    return _repository(
        tmp_path / "repo",
        {
            ".semgrepignore": "src/\n",
            "src/bad.py": _BAD,
            "src/suppressed.py": _BAD_SUPPRESSED,
            "src/clean.py": _CLEAN,
            "tests/test_bad.py": _BAD,
        },
    )


@_needs_semgrep
def test_required_run_reports_nosemgrep_lines_and_ignores_consumer_semgrepignore(
    repository: Path, tmp_path: Path
) -> None:
    found = _findings(repository, tmp_path / "required", required=True)
    # Known-bad scope: .semgrepignore lists src/, yet src/ is scanned.
    assert ("src/bad.py", 1) in found
    # Known-bad nosem: the annotated line still yields its finding.
    assert ("src/suppressed.py", 1) in found
    # Known-good: a clean line yields nothing; a declared exclusion stays out.
    assert not any(path in {"src/clean.py", "tests/test_bad.py"} for path, _ in found)


@_needs_semgrep
def test_non_required_run_keeps_semgreps_own_scope_and_nosem(
    repository: Path, tmp_path: Path
) -> None:
    found = _findings(repository, tmp_path / "plain", required=False)
    # Unchanged behaviour outside required runs: the consumer file decides.
    assert not any(path.startswith("src/") for path, _ in found)


@_needs_semgrep
def test_required_run_writes_schema_valid_scope_evidence(
    repository: Path, tmp_path: Path
) -> None:
    out = tmp_path / "required"
    _findings(repository, out, required=True)
    evidence = json.loads((out / "raw" / "report.scope.json").read_text("utf-8"))
    schema = files("l9_ci").joinpath("schemas", "v1", "semgrep-scan-scope.schema.json")
    validator = Draft202012Validator(json.loads(schema.read_text(encoding="utf-8")))
    assert sorted(validator.iter_errors(evidence), key=str) == []
    assert evidence["consumer_semgrepignore"] == {
        "files": [".semgrepignore"],
        "honored": False,
    }
    assert {item["pattern"]: item["count"] for item in evidence["excluded"]} == {
        "directory_names:tests": 1
    }


# --- JavaScript planned through the TypeScript pack (Cursor-Governance P0) ----


def _required_typescript_run(root: Path, out: Path) -> tuple[dict, dict, int]:
    """Run the required TypeScript instance as Core does; return bundle, raw, gate."""
    command = [
        sys.executable,
        "-m",
        "l9_ci",
        "semgrep",
        "run",
        "--language",
        "typescript",
        "--profile",
        "l9-baseline",
        "--root",
        str(root),
        "--snapshot-id",
        "witness",
        "--output",
        str(out / "bundle.json"),
        "--raw-output",
        str(out / "raw" / "report.json"),
        "--required",
        "--format",
        "json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    gate = subprocess.run(
        [
            sys.executable,
            "-m",
            "l9_ci",
            "gate",
            "evaluate",
            "--bundle",
            str(out / "bundle.json"),
            "--output",
            str(out / "gate.json"),
            "--no-strict-unresolved",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    bundle = json.loads((out / "bundle.json").read_text(encoding="utf-8"))
    raw = json.loads((out / "raw" / "report.json").read_text(encoding="utf-8"))
    return bundle, raw, gate.returncode


@_needs_semgrep
def test_required_typescript_instance_completes_on_in_scope_javascript(
    tmp_path: Path,
) -> None:
    """A repository that really has JavaScript gets a completed instance."""
    root = _repository(
        tmp_path / "repo",
        {
            "web/app.js": "module.exports = function add(a, b) { return a + b; };\n",
            "web/util.ts": "export const y: number = 1;\n",
            "tests/fixture.js": "module.exports = {};\n",
        },
    )
    bundle, raw, gate = _required_typescript_run(root, tmp_path / "out")
    assert sorted(raw["paths"]["scanned"]) == ["web/app.js", "web/util.ts"]
    (coverage,) = bundle["coverage"]
    assert coverage["status"] == "complete"
    assert coverage["files_analyzed"] == 2
    assert gate in (0, 1), "a completed instance concludes pass or fail"


@_needs_semgrep
def test_typescript_instance_on_test_fixtures_only_cannot_complete(
    tmp_path: Path,
) -> None:
    """Why the inventory must not plan it: JS only under tests/ scans nothing."""
    root = _repository(
        tmp_path / "repo",
        {
            "ops/app.py": "x = 1\n",
            "ops/scripts/tests/fixtures/run_workflow.js": "module.exports = {};\n",
        },
    )
    bundle, raw, gate = _required_typescript_run(root, tmp_path / "out")
    assert raw["paths"]["scanned"] == []
    assert bundle["coverage"][0]["status"] == "partial"
    assert gate == 6
