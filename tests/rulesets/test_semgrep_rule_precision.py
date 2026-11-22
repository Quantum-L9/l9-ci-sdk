"""Witnesses for registry-rule precision (rule-precision.yaml, ADR 0024).

CTO 2026-11-21: the registry SHA-1 rule blocked hashlib.sha1 used to compute
git object IDs, where the git object format requires SHA-1 and nothing is
security-relevant. Python's ``usedforsecurity=False`` declares exactly that;
the registry MD5 rule honours it, the SHA-1 rule does not. The SDK withholds
the SHA-1 finding only where the call passes that keyword as the literal
``False``; every other form keeps its finding.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline
from l9_ci.pipeline.precision import declares_keyword_false
from l9_ci.rulesets.semgrep.precision import (
    RulePrecisionError,
    load_rule_precisions,
    packaged_rule_precisions,
    rule_precision_path,
)

SHA1_RULE = "python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1"
FORMS = Path("tests/fixtures/semgrep/rules/precision/sha1_forms.pyfixture")
# Line numbers of the calls in FORMS.
DECLARED = {9, 13}
UNDECLARED = {19, 23, 27}  # no keyword, usedforsecurity=True, a variable

_needs_semgrep = pytest.mark.skipif(
    shutil.which("semgrep") is None and os.environ.get("L9_REQUIRE_SEMGREP") != "1",
    reason="semgrep executable not available on PATH",
)


def test_the_packaged_declaration_covers_the_sha1_rule() -> None:
    assert packaged_rule_precisions().keywords("python") == {
        SHA1_RULE: "usedforsecurity"
    }
    assert packaged_rule_precisions().keywords("typescript") == {}


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda d: d.update(schema="x/v1"), "schema must be"),
        (lambda d: d["precisions"][0].pop("reason"), "must carry exactly"),
        (
            lambda d: d["precisions"][0].update(rule_id="l9.baseline.python.x"),
            "packaged L9 rule",
        ),
        (
            lambda d: d["precisions"][0].update(not_when_keyword_false="not a name"),
            "malformed keyword",
        ),
        (lambda d: d["precisions"][0].update(language="typescript"), "python only"),
        (lambda d: d["precisions"].append(dict(d["precisions"][0])), "declared twice"),
        (lambda d: d["precisions"][0].update(reason="  "), "non-empty"),
    ],
)
def test_a_malformed_declaration_is_refused(
    tmp_path: Path, mutation, message: str
) -> None:  # type: ignore[no-untyped-def]
    document = yaml.safe_load(rule_precision_path().read_text(encoding="utf-8"))
    mutation(document)
    path = tmp_path / "rule-precision.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(RulePrecisionError, match=message):
        load_rule_precisions(path)


def test_only_a_literal_false_on_the_finding_line_declares_non_security() -> None:
    tree = ast.parse(FORMS.read_text(encoding="utf-8"))
    for line in DECLARED:
        assert declares_keyword_false(tree, line, "usedforsecurity"), line
    for line in UNDECLARED:
        assert not declares_keyword_false(tree, line, "usedforsecurity"), line
    # Another keyword name never matches.
    assert not declares_keyword_false(tree, 9, "other")


def _scan(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "sha1_forms.py").write_text(FORMS.read_text(encoding="utf-8"), "utf-8")
    completed = subprocess.run(
        [
            "semgrep",
            "scan",
            "--metrics=off",
            "--json",
            "--config",
            f"r/{SHA1_RULE}",
            "--",
            "sha1_forms.py",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=root,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    report = tmp_path / "report.json"
    report.write_text(completed.stdout, encoding="utf-8")
    return report


@_needs_semgrep
def test_the_registry_rule_flags_every_form_including_the_declared_ones(
    tmp_path: Path,
) -> None:
    """Why the precision is needed: Semgrep alone reports all five calls."""
    results = json.loads(_scan(tmp_path).read_text("utf-8"))["results"]
    lines = {item["start"]["line"] for item in results if item["check_id"] == SHA1_RULE}
    assert lines == DECLARED | UNDECLARED


@_needs_semgrep
def test_the_pipeline_withholds_only_the_declared_forms(tmp_path: Path) -> None:
    report = _scan(tmp_path)
    output = tmp_path / "bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=report,
            repository_root=(tmp_path / "repo").resolve(),
            snapshot_id="snapshot-1",
            SDK_version="2.0.0-test",
            output_path=output,
            provider_version="1.171.0",
            generated_at="2026-11-21T00:00:00Z",
            precision_keywords=packaged_rule_precisions().keywords("python"),
        )
    )
    bundle = load_and_validate_bundle(output)
    kept = {finding.locations[0].start_line for finding in bundle.findings}
    assert kept == UNDECLARED
    assert len(bundle.evidence) == len(DECLARED | UNDECLARED)  # evidence kept
    (note,) = [i for i in bundle.limitations if i.startswith("registry rule")]
    assert "usedforsecurity=False" in note
    assert "sha1_forms.py:9" in note and "sha1_forms.py:13" in note


@_needs_semgrep
def test_an_unparseable_file_keeps_every_finding(tmp_path: Path) -> None:
    report = _scan(tmp_path)
    (tmp_path / "repo" / "sha1_forms.py").write_text("def broken(:\n", "utf-8")
    output = tmp_path / "bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=report,
            repository_root=(tmp_path / "repo").resolve(),
            snapshot_id="snapshot-1",
            SDK_version="2.0.0-test",
            output_path=output,
            provider_version="1.171.0",
            generated_at="2026-11-21T00:00:00Z",
            precision_keywords=packaged_rule_precisions().keywords("python"),
        )
    )
    bundle = load_and_validate_bundle(output)
    assert {f.locations[0].start_line for f in bundle.findings} == (
        DECLARED | UNDECLARED
    )
