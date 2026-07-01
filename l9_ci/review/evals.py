"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
engine: platform
layer: [sdk, review, agent-review-loop, evals]
tags: [L9_CI, agent-review-loop, evals, golden-sets]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .orchestrator import run_review

REQUIRED_REPORT_KEYS = {"schema_version", "marker", "findings", "blocking_count", "advisory_count"}


@dataclass
class CaseResult:
    name: str
    passed: bool
    structured_output_valid: bool
    categories_present: bool
    finding_count: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "structured_output_valid": self.structured_output_valid,
            "categories_present": self.categories_present,
            "finding_count": self.finding_count,
            "reasons": self.reasons,
        }


@dataclass
class EvalReport:
    passed: bool
    cases: list[dict[str, Any]]
    hard_failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "cases": self.cases, "hard_failures": self.hard_failures}


def _run_case(case: dict[str, Any]) -> CaseResult:
    name = str(case.get("name", "unnamed"))
    expected = case.get("expected", {})
    reasons: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, content in case.get("files", {}).items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        report = run_review(
            root,
            case.get("changed_files", []),
            pr_class=case.get("pr_class", "app_code"),
            agents=case.get("agents", ["audit"]),
            agent_modes={a: "advisory" for a in case.get("agents", ["audit"])},
            file_mode="filesystem",
        )
    data = report.to_dict()

    # structured_output_validity (hard-fail per Platform Doctrine).
    structured_valid = REQUIRED_REPORT_KEYS.issubset(data)
    if not structured_valid:
        reasons.append("schema_invalid")

    # Read findings defensively: when the report is schema-invalid ``findings``
    # may be absent, so fall back to an empty list instead of raising KeyError
    # (schema-invalid is a deterministic hard-fail, not a harness crash).
    findings = data.get("findings", [])

    # regression: expected categories must appear.
    got_categories = {f["category"] for f in findings}
    want_categories = set(expected.get("categories", []))
    categories_present = want_categories.issubset(got_categories)
    if not categories_present:
        reasons.append(f"missing_categories:{sorted(want_categories - got_categories)}")

    min_findings = int(expected.get("min_findings", 0))
    if len(findings) < min_findings:
        reasons.append(f"too_few_findings:{len(findings)}<{min_findings}")

    passed = structured_valid and categories_present and len(findings) >= min_findings
    return CaseResult(
        name=name,
        passed=passed,
        structured_output_valid=structured_valid,
        categories_present=categories_present,
        finding_count=len(findings),
        reasons=reasons,
    )


def run_evals(golden_dir: Path) -> EvalReport:
    cases = sorted(golden_dir.glob("*.json"))
    results: list[CaseResult] = []
    hard_failures: list[str] = []
    for path in cases:
        case = json.loads(path.read_text(encoding="utf-8"))
        result = _run_case(case)
        results.append(result)
        if not result.structured_output_valid:
            hard_failures.append(f"{result.name}:schema_invalid")
        elif not result.passed:
            hard_failures.append(f"{result.name}:regression")
    return EvalReport(
        passed=not hard_failures and bool(results),
        cases=[r.to_dict() for r in results],
        hard_failures=hard_failures,
    )
