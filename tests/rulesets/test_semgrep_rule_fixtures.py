"""Run the packaged L9 Semgrep rules against their annotated fixtures.

``tests/fixtures/semgrep/rules/python/<rule-file>.py`` pairs with
``l9_ci/rulesets/semgrep/python/<rule-file>.yml``. Every line annotated
``ruleid`` must be flagged and every other line must not; ``semgrep --test``
also fails when a rule in the paired file reports a line nobody annotated.
The fixtures carry the exact false positives that failed
Quantum-L9/Cognitive.Engine.Graphs PR #409 as negative cases, next to the real
leaks and raw dispatches the rules exist to catch, so neither direction can
drift without a red test.

These tests need a ``semgrep`` executable. The pytest job does not install
one, so they skip there (the same convention as
``tests/providers/semgrep/test_provider.py``); the ``semgrep rule fixtures``
gate in ``.github/workflows/ci.yml`` installs the self-CI pinned Semgrep and
runs ``semgrep --test`` over the same directories on every PR, so the
fixtures are enforced in CI either way.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from l9_ci.rulesets.semgrep import ruleset_dir

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "semgrep" / "rules" / "python"
FIXTURED_RULE_FILES = ("l9-logging", "l9-routing")

_SEMGREP = shutil.which("semgrep")
_needs_semgrep = pytest.mark.skipif(
    _SEMGREP is None, reason="semgrep executable not available on PATH"
)


@pytest.mark.parametrize("stem", FIXTURED_RULE_FILES)
def test_every_fixtured_rule_file_has_its_pair(stem: str) -> None:
    assert (ruleset_dir("python") / f"{stem}.yml").is_file()
    fixture = FIXTURE_DIR / f"{stem}.py"
    assert fixture.is_file(), f"missing Semgrep fixture {fixture}"
    text = fixture.read_text(encoding="utf-8")
    assert "# ruleid:" in text and "# ok:" in text, (
        f"{fixture.name} must pin both directions: cases the rules must flag "
        "and false positives they must not"
    )


def test_fixtures_are_excluded_from_the_self_ci_scan() -> None:
    ignore = (REPO_ROOT / ".semgrepignore").read_text(encoding="utf-8")
    assert "tests/fixtures/semgrep/rules/" in ignore.splitlines(), (
        "the rule fixtures are deliberate positives; without a .semgrepignore "
        "entry the SDK's own self-CI scan reports them"
    )


@_needs_semgrep
def test_packaged_python_rules_pass_their_fixtures() -> None:
    assert _SEMGREP is not None
    proc = subprocess.run(
        [
            _SEMGREP,
            "--test",
            "--metrics=off",
            "--json",
            "--config",
            str(ruleset_dir("python")),
            str(FIXTURE_DIR),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"semgrep --test failed (exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
    )
    report = json.loads(proc.stdout)
    checked: set[str] = set()
    for file_result in report["results"].values():
        for rule_id, check in file_result["checks"].items():
            assert check["passed"], f"{rule_id}: {check['matches']}"
            checked.add(rule_id)
    # The fixtures exist to pin these rules; an empty run is not a pass.
    assert {
        "l9.logging.forbidden-secret-field",
        "l9.logging.forbidden-secret-keyword",
        "l9.logging.f-string-secret",
        "l9.routing.gateclient-bypass-execute",
    } <= checked, f"fixtures did not exercise every pinned rule: {sorted(checked)}"
