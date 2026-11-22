"""An advisory-classified rule's finding never fails the gate (CTO P0, 2026-11-21).

End to end, with Core's own finding policy: a real Semgrep report from
Cursor-Governance run 44843122770 (SDK fbe14fec) is normalized and classified with a
verbatim copy of Core's ``semgrep-policy.yaml`` version 4, then evaluated by the
gate. Core keys its policy by Semgrep ``provider_rule_id`` and defaults every
unclassified rule to blocking. ``dangerous-subprocess-use-tainted-env-args`` is
classified advisory there, and it must stay advisory through the gate.
"""

from __future__ import annotations

import json
from pathlib import Path

from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.gates import GateStatus, evaluate_gate
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline

FIXTURES = Path("tests/fixtures/semgrep")
REPORT = FIXTURES / "report-policy-advisory-cg-44843122770.json"
POLICY = FIXTURES / "core-semgrep-policy-v4.json"
ADVISORY_RULE = (
    "python.lang.security.audit.dangerous-subprocess-use-tainted-env-args."
    "dangerous-subprocess-use-tainted-env-args"
)


def _bundle(tmp_path: Path, report: Path):  # type: ignore[no-untyped-def]
    output = tmp_path / "bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=report,
            repository_root=Path(".").resolve(),
            snapshot_id="snapshot-1",
            SDK_version="2.0.0-test",
            output_path=output,
            provider_version="1.171.0",
            policy_path=POLICY,
            required=True,
            generated_at="2026-11-21T00:00:00Z",
        )
    )
    return load_and_validate_bundle(output)


def test_core_policy_advisory_rule_is_advisory_and_unclassified_rule_blocks(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path, REPORT)
    modes = {
        finding.provider_rule_id: next(
            c for c in bundle.classifications if c.finding_id == finding.finding_id
        )
        for finding in bundle.findings
    }
    advisory = modes[ADVISORY_RULE]
    assert advisory.mode.value == "advisory"
    assert advisory.policy_key == "actions.env-sourced-argv"
    assert advisory.used_default is False
    (blocking_rule,) = [rule for rule in modes if rule != ADVISORY_RULE]
    assert blocking_rule.endswith("python.subprocess-shell-true")
    assert modes[blocking_rule].mode.value == "blocking"
    assert modes[blocking_rule].used_default is True
    result = evaluate_gate(bundle)
    assert result.status is GateStatus.FAIL
    (blocked,) = result.blocking_finding_ids
    assert blocked == next(
        f.finding_id for f in bundle.findings if f.provider_rule_id == blocking_rule
    )


def test_core_policy_advisory_finding_alone_passes_the_gate(tmp_path: Path) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["results"] = [r for r in report["results"] if r["check_id"] == ADVISORY_RULE]
    report["paths"]["scanned"] = sorted({r["path"] for r in report["results"]})
    only_advisory = tmp_path / "report.json"
    only_advisory.write_text(json.dumps(report), encoding="utf-8")
    bundle = _bundle(tmp_path, only_advisory)
    assert len(bundle.findings) == 1
    assert evaluate_gate(bundle).status is GateStatus.PASS
