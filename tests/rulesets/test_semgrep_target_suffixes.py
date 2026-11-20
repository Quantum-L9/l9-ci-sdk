"""The inventory's analysis targets claim exactly what Semgrep analyzes.

``l9_ci.commands.providers`` declares, per packaged Semgrep language run, the
inventory languages it serves and the file suffixes it scans. The inventory
counts a file as covered only on that declaration, so a wrong declaration is a
false coverage claim (L9-CI-SDK-001, L9-CI-SDK-002). These tests check it
against the real ``semgrep`` executable: every suffix the inventory maps to a
served language is written to disk, the target's packaged rulepack is run, and
the set of files Semgrep scanned must equal the declared set.

They also run the TypeScript pack's ``semgrep --test`` fixture, which is
JavaScript: every rule in that pack must flag its known-bad line and leave its
known-good line alone on JavaScript, or the pack does not serve JavaScript.
The fixture is stored as ``.jsfixture``, the repository's convention for a
scanner fixture (``rules/python/l9-file-permissions.pyfixture``): as ``.js``,
CodeQL default setup and the publish security gate analyse its deliberate
known-bad lines as product code.

Like tests/rulesets/test_semgrep_rule_fixtures.py these need a ``semgrep``
executable and skip without one; the ``semgrep rule fixtures`` step in
.github/workflows/ci.yml runs the same ``semgrep --test`` on every pull
request with the self-CI pinned Semgrep.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from l9_ci.capabilities.inventory import _LANGUAGE_SUFFIXES
from l9_ci.commands.providers import default_analysis_targets
from l9_ci.rulesets.semgrep import ruleset_dir

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "semgrep" / "rules" / "typescript"

_SEMGREP = shutil.which("semgrep")
_needs_semgrep = pytest.mark.skipif(
    _SEMGREP is None, reason="semgrep executable not available on PATH"
)

# One statement every packaged rulepack flags, so a scanned file is visible
# whichever rules apply to it.
_PROBE = {
    "python": "eval(source)\n",
    "typescript": "eval(source);\n",
    "javascript": "eval(source);\n",
}


def test_javascript_fixture_is_outside_javascript_extension_scanners() -> None:
    assert (TS_FIXTURES / "l9-baseline-security.jsfixture").is_file()
    assert not (TS_FIXTURES / "l9-baseline-security.js").exists()


def test_typescript_pack_has_a_javascript_fixture() -> None:
    fixture = TS_FIXTURES / "l9-baseline-security.jsfixture"
    assert fixture.is_file(), f"missing Semgrep fixture {fixture}"
    text = fixture.read_text(encoding="utf-8")
    rules = (ruleset_dir("typescript") / "l9-baseline-security.yml").read_text(
        encoding="utf-8"
    )
    for line in rules.splitlines():
        if line.startswith("  - id: "):
            rule_id = line.removeprefix("  - id: ").strip()
            assert f"// ruleid: {rule_id}" in text, f"{rule_id}: no known-bad .js"
            assert f"// ok: {rule_id}" in text, f"{rule_id}: no known-good .js"


@_needs_semgrep
def test_typescript_pack_passes_its_javascript_fixture() -> None:
    assert _SEMGREP is not None
    proc = subprocess.run(
        [
            _SEMGREP,
            "--test",
            "--metrics=off",
            "--json",
            "--config",
            str(ruleset_dir("typescript")),
            str(TS_FIXTURES),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert proc.returncode == 0, f"semgrep --test failed:\n{proc.stdout}\n{proc.stderr}"
    report = json.loads(proc.stdout)
    checked = 0
    for file_result in report["results"].values():
        for rule_id, check in file_result["checks"].items():
            assert check["passed"], f"{rule_id}: {check['matches']}"
            checked += 1
    assert checked == 7, f"expected the 7 TypeScript-pack rules, checked {checked}"


@_needs_semgrep
@pytest.mark.parametrize(
    "target", default_analysis_targets(REPO_ROOT), ids=lambda target: target.name
)
def test_declared_suffixes_are_exactly_what_semgrep_scans(
    target, tmp_path: Path
) -> None:
    assert _SEMGREP is not None
    candidates = sorted(
        suffix
        for suffix, language in _LANGUAGE_SUFFIXES.items()
        if language in target.languages
    )
    for suffix in candidates:
        language = _LANGUAGE_SUFFIXES[suffix]
        (tmp_path / f"sample{suffix}").write_text(_PROBE[language], encoding="utf-8")
    # An empty ignore file replaces Semgrep's built-in default list.
    (tmp_path / ".semgrepignore").write_text("", encoding="utf-8")

    proc = subprocess.run(
        [
            _SEMGREP,
            "scan",
            "--metrics=off",
            "--quiet",
            "--json",
            "--config",
            str(REPO_ROOT / str(target.rulepack)),
            ".",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert proc.returncode in (0, 1), proc.stderr
    report = json.loads(proc.stdout)
    assert report["errors"] == []
    scanned = sorted(Path(path).suffix for path in report["paths"]["scanned"])
    assert scanned == sorted(target.suffixes)
    flagged = sorted({Path(result["path"]).suffix for result in report["results"]})
    assert flagged == sorted(target.suffixes)
