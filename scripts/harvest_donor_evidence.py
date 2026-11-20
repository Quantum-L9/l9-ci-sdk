#!/usr/bin/env python3
"""Reproduce the behavioural evidence behind docs/harvest/semgrep-donor-ledger.yaml.

The ledger says, for each donor Semgrep rule, which known-bad lines it flags
and which known-good lines it leaves alone. Rules that stay at their owner are
not in this repository, so that evidence cannot be re-run by the SDK's own CI.
This script re-runs it for anyone who has the donor checkouts:

    python scripts/harvest_donor_evidence.py \
        --eie PATH --ceg PATH --cursor PATH --odoo PATH [--json]

It copies each fixture tree to a temporary directory outside any git
repository (so no ignore file hides a fixture), runs the donor rule file with
the real ``semgrep`` executable, and prints one line per (rule, fixture) with
the flagged line numbers. It reads donor checkouts and writes nothing to them.

Marker convention in authored fixtures: ``# bad: <rule id>`` (XML and SQL
fixtures carry no markers) says the next code line must be flagged by that
rule; ``# good: <rule id>`` says it must not.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
HARVEST = REPO_ROOT / "tests" / "fixtures" / "semgrep" / "harvest"
PORTABLE_PACK = REPO_ROOT / "l9_ci" / "rulesets" / "semgrep" / "packs"
PYTHON_BASELINE = REPO_ROOT / "l9_ci" / "rulesets" / "semgrep" / "python"
CURSOR_SAMPLE = HARVEST / "cursor" / "sample.pyfixture"
CURSOR_COPIES = ("ops/memory/sample.py", "svc/sample.py")
_MARKER = re.compile(r"#\s*(bad|good):\s*(\S+)")


def scan(
    config: Path,
    tree: Path,
    *,
    mount: str = "",
) -> dict[str, dict[str, list[int]]]:
    """Run ``config`` over a copy of ``tree``; return rule -> file -> lines.

    ``mount`` places the copy at that relative path under the scan root, for
    donor fixtures whose rules name them by repository-relative path.
    """
    semgrep = shutil.which("semgrep")
    if semgrep is None:
        raise SystemExit("semgrep executable not found on PATH")
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch) / "tree"
        destination = work / mount if mount else work
        if tree.is_dir():
            shutil.copytree(tree, destination)
        else:
            destination.mkdir(parents=True)
            shutil.copy2(tree, destination / tree.name)
        # An empty ignore file replaces Semgrep's built-in default list, which
        # would otherwise hide every fixture under a tests/ directory.
        (work / ".semgrepignore").write_text("", encoding="utf-8")
        proc = subprocess.run(
            [
                semgrep,
                "scan",
                "--metrics=off",
                "--disable-version-check",
                "--quiet",
                "--json",
                "--no-git-ignore",
                "--config",
                str(config),
                ".",
            ],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        if proc.returncode not in (0, 1):
            raise SystemExit(f"semgrep failed ({proc.returncode}): {proc.stderr}")
        report = json.loads(proc.stdout)
    if report["errors"]:
        raise SystemExit(f"semgrep reported errors: {report['errors']}")
    known = _declared_rule_ids(config)
    found: dict[str, dict[str, list[int]]] = {}
    for result in report["results"]:
        check_id = result["check_id"]
        # Semgrep prefixes a rule ID with the dotted path of its config file.
        candidates = [
            rule_id
            for rule_id in known
            if check_id == rule_id or check_id.endswith("." + rule_id)
        ]
        if not candidates:
            raise SystemExit(f"finding for an undeclared rule: {check_id}")
        rule_id = max(candidates, key=len)
        found.setdefault(rule_id, {}).setdefault(result["path"], []).append(
            result["start"]["line"]
        )
    return {
        rule: {path: sorted(set(lines)) for path, lines in sorted(files.items())}
        for rule, files in sorted(found.items())
    }


def _scan_cursor(config: Path) -> dict[str, dict[str, list[int]]]:
    """Scan the Cursor sample both inside and outside the memory path.

    The sample is stored as text (see its docstring), so it is written into a
    scratch tree as Python here.
    """
    with tempfile.TemporaryDirectory() as scratch:
        tree = Path(scratch) / "cursor"
        for relative in CURSOR_COPIES:
            target = tree / relative
            target.parent.mkdir(parents=True)
            shutil.copy2(CURSOR_SAMPLE, target)
        return scan(config, tree)


def _declared_rule_ids(config: Path) -> set[str]:
    files = sorted(config.rglob("*.yml")) if config.is_dir() else [config]
    declared: set[str] = set()
    for file in files:
        document = yaml.safe_load(file.read_text(encoding="utf-8"))
        declared.update(rule["id"] for rule in document["rules"])
    return declared


def markers(path: Path) -> dict[str, dict[str, list[int]]]:
    """Return rule -> {"bad": [...], "good": [...]} target line numbers."""
    lines = path.read_text(encoding="utf-8").splitlines()
    result: dict[str, dict[str, list[int]]] = {}
    for index, line in enumerate(lines):
        match = _MARKER.search(line)
        if not match:
            continue
        target = index + 1
        while target < len(lines) and lines[target].lstrip().startswith("#"):
            target += 1
        result.setdefault(match.group(2), {"bad": [], "good": []})[
            match.group(1)
        ].append(target + 1)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for name in ("eie", "ceg", "cursor", "odoo"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    overlap = HARVEST / "python_overlap.py"
    portable = (
        REPO_ROOT / "tests/fixtures/semgrep/rules/packs/python-portable"
        "/l9-python-portable.py"
    )
    odoo_rules = args.odoo / ".semgrep" / "odoo-patterns.yml"
    runs = {
        "eie/python_overlap": scan(args.eie / ".semgrep/semgrep-rules.yaml", overlap),
        "ceg/python_overlap": scan(args.ceg / ".semgrep/semgrep-rules.yaml", overlap),
        "sdk-baseline/python_overlap": scan(PYTHON_BASELINE, overlap),
        "eie/portable_fixture": scan(
            args.eie / ".semgrep/semgrep-rules.yaml", portable
        ),
        "ceg/portable_fixture": scan(
            args.ceg / ".semgrep/semgrep-rules.yaml", portable
        ),
        "sdk-portable/portable_fixture": scan(PORTABLE_PACK, portable),
        "cursor/tree": _scan_cursor(args.cursor / ".semgrep/l9-pr.yml"),
        "odoo/donor_tests": scan(
            odoo_rules, args.odoo / ".semgrep" / "tests", mount=".semgrep/tests"
        ),
        "odoo/tree": scan(odoo_rules, HARVEST / "odoo"),
        "sdk-baseline/odoo_donor_tests": scan(
            PYTHON_BASELINE,
            args.odoo / ".semgrep" / "tests",
            mount=".semgrep/tests",
        ),
    }
    payload = {
        "markers": {
            "python_overlap.py": markers(overlap),
            "cursor/sample.pyfixture": markers(CURSOR_SAMPLE),
            "odoo/plasticos_demo/models/bad.py": markers(
                HARVEST / "odoo/plasticos_demo/models/bad.py"
            ),
        },
        "runs": runs,
    }
    if args.json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    for run, rules in runs.items():
        print(f"== {run}")
        for rule, by_file in rules.items():
            for path, lines in by_file.items():
                print(f"   {rule}  {path}  {lines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
