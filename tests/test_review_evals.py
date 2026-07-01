from __future__ import annotations

import json
from pathlib import Path

from l9_ci.review import evals as evals_module
from l9_ci.review.evals import _run_case, run_evals

GOLDEN = Path(__file__).resolve().parents[1] / "evals" / "golden_sets"


def test_shipped_golden_sets_pass() -> None:
    report = run_evals(GOLDEN)
    assert report.cases, "golden sets must exist"
    assert report.passed, f"golden sets regressed: {report.hard_failures}"


def test_regression_is_a_hard_failure(tmp_path: Path) -> None:
    # A case that expects a category the deterministic agent will not produce.
    case = {
        "name": "expect_missing_category",
        "pr_class": "app_code",
        "agents": ["audit"],
        "files": {"a.py": "x = 1\n"},
        "changed_files": ["a.py"],
        "expected": {"categories": ["security"], "min_findings": 1},
    }
    (tmp_path / "bad_case.json").write_text(json.dumps(case), encoding="utf-8")
    report = run_evals(tmp_path)
    assert not report.passed
    assert report.hard_failures


def test_schema_invalid_report_hard_fails_without_crash(monkeypatch) -> None:
    # A report missing "findings" (schema-invalid) must degrade to a
    # deterministic schema_invalid hard-fail, not raise KeyError.
    class _BadReport:
        def to_dict(self) -> dict:
            return {"schema_version": 1, "marker": "x"}  # no "findings" key

    monkeypatch.setattr(evals_module, "run_review", lambda *a, **k: _BadReport())
    result = _run_case({"name": "schema_broken", "files": {}, "expected": {}})
    assert result.structured_output_valid is False
    assert not result.passed
    assert "schema_invalid" in result.reasons
    assert result.finding_count == 0
