from __future__ import annotations

from dataclasses import dataclass, field

from l9_ci.governance.approval import GovernanceApprovalResult, evaluate_governance_approval

PASSING = {"success", "skipped", "neutral"}


@dataclass(frozen=True)
class GateResult:
    passed: bool
    failed_required: dict[str, str]
    observed: dict[str, str]
    governance_approval: GovernanceApprovalResult | None = None
    governance_failures: list[str] = field(default_factory=list)


def evaluate(
    results: dict[str, str],
    required: list[str],
    *,
    changed_files: list[str] | None = None,
    pr_labels: list[str] | None = None,
    labels_known: bool = True,
) -> GateResult:
    normalized = {name: value.lower() for name, value in results.items()}
    failed: dict[str, str] = {}
    for job in required:
        value = normalized.get(job, "missing")
        if value not in PASSING:
            failed[job] = value

    approval: GovernanceApprovalResult | None = None
    governance_failures: list[str] = []
    if changed_files is not None:
        approval = evaluate_governance_approval(changed_files, pr_labels, labels_known=labels_known)
        if not approval.passed:
            governance_failures.append(approval.reason)

    return GateResult(not failed and not governance_failures, failed, normalized, approval, governance_failures)


def parse_result_pairs(pairs: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid result pair: {pair}. Expected name=status")
        name, value = pair.split("=", 1)
        parsed[name.strip()] = value.strip()
    return parsed


def format_gate(result: GateResult) -> str:
    lines = ["CI Pipeline Results"]
    for name in sorted(result.observed):
        lines.append(f"  {name}: {result.observed[name]}")
    if result.governance_approval is not None:
        lines.append(f"  governance approval: {'passed' if result.governance_approval.passed else 'failed'}")
        lines.append(f"  governance approval reason: {result.governance_approval.reason}")
    if result.passed:
        lines.append("CI gate passed")
    else:
        lines.append("CI gate failed")
        for name, value in result.failed_required.items():
            lines.append(f"  required job failed: {name}={value}")
        for failure in result.governance_failures:
            lines.append(f"  governance failure: {failure}")
    return "\n".join(lines)
