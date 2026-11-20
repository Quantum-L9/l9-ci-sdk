"""Real-Semgrep witnesses for ``l9-ci semgrep consumer-run`` (ADR 0021).

* known-bad: a consumer rule fires on a file inside its declared
  ``paths.include`` and carries the consumer canonical ID;
* known-good: the same code outside the rule's declared paths yields nothing;
* consumer scope is the consumer's: an inline ``nosemgrep`` is honoured;
* the central run never loads the consumer rule;
* a refused declaration fails the consumer run before Semgrep starts.

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
import yaml
from jsonschema import Draft202012Validator

_needs_semgrep = pytest.mark.skipif(
    shutil.which("semgrep") is None and os.environ.get("L9_REQUIRE_SEMGREP") != "1",
    reason="semgrep executable not available on PATH",
)

OWNER = "Quantum-L9/Cursor-Governance"
CANONICAL = "CONSUMER-CURSOR-GOVERNANCE-NO-FORBIDDEN-CALL"
RULE = {
    "id": "l9.memory-boundary-no-forbidden-call",
    "languages": ["python"],
    "message": "forbidden_call is not allowed in the memory boundary",
    "severity": "ERROR",
    "pattern": "forbidden_call(...)",
    "paths": {"include": ["ops/memory/"], "exclude": ["**/test_*.py"]},
    "metadata": {"l9": {"canonical_rule_id": CANONICAL}},
}
_BAD = "forbidden_call(1)\n"


def _repository(root: Path, rule: dict) -> Path:
    tree = {
        "ops/memory/bad.py": _BAD,
        "ops/memory/suppressed.py": "forbidden_call(2)  # nosemgrep\n",
        "ops/memory/test_bad.py": _BAD,
        "src/outside.py": _BAD,
        ".semgrep/l9-pr.yml": yaml.safe_dump({"rules": [rule]}),
        ".l9/semgrep-consumer-rules.yaml": yaml.safe_dump(
            {
                "schema": "l9.semgrep-consumer-rulepack/v1",
                "owner": OWNER,
                "rule_files": [".semgrep/l9-pr.yml"],
            }
        ),
    }
    for relative, content in tree.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _run(root: Path, out: Path, *command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "l9_ci",
            "semgrep",
            *command,
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
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _locations(bundle: dict, rule: str) -> set[str]:
    return {
        location["normalized_path"]
        for finding in bundle["findings"]
        if finding["canonical_rule_id"] == rule
        for location in finding["locations"]
    }


@_needs_semgrep
def test_consumer_rule_fires_only_inside_its_declared_paths(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo", RULE)
    out = tmp_path / "consumer"
    completed = _run(root, out, "consumer-run", "--required")
    assert completed.returncode == 0, completed.stderr or completed.stdout
    bundle = json.loads((out / "bundle.json").read_text("utf-8"))
    # Known-bad inside the declared path; nothing outside it, nothing in the
    # rule's own exclusion, and the consumer's nosemgrep is honoured.
    assert _locations(bundle, CANONICAL) == {"ops/memory/bad.py"}
    assert bundle["providers"][0]["required"] is True
    record = json.loads((out / "raw" / "report.consumer.json").read_text("utf-8"))
    schema = files("l9_ci").joinpath(
        "schemas", "v1", "semgrep-consumer-rulepack-evidence.schema.json"
    )
    validator = Draft202012Validator(json.loads(schema.read_text(encoding="utf-8")))
    assert sorted(validator.iter_errors(record), key=str) == []
    assert record["owner"] == OWNER
    assert [item["path"] for item in record["rule_files"]] == [".semgrep/l9-pr.yml"]


@_needs_semgrep
def test_central_run_never_loads_the_consumer_rule(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo", RULE)
    out = tmp_path / "central"
    completed = _run(
        root, out, "run", "--language", "python", "--profile", "l9-baseline"
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    bundle = json.loads((out / "bundle.json").read_text("utf-8"))
    assert _locations(bundle, CANONICAL) == set()


def test_refused_declaration_fails_before_semgrep_runs(tmp_path: Path) -> None:
    unscoped = {key: value for key, value in RULE.items() if key != "paths"}
    root = _repository(tmp_path / "repo", unscoped)
    out = tmp_path / "consumer"
    completed = _run(root, out, "consumer-run")
    assert completed.returncode == 2
    assert "must declare paths" in (completed.stdout + completed.stderr)
    assert not (out / "bundle.json").exists()
    assert not (out / "raw" / "report.json").exists()


def test_missing_declaration_fails_the_consumer_run(tmp_path: Path) -> None:
    (tmp_path / "repo").mkdir()
    completed = _run(tmp_path / "repo", tmp_path / "out", "consumer-run")
    assert completed.returncode == 2
    assert "no consumer rulepack declaration" in (completed.stdout + completed.stderr)
