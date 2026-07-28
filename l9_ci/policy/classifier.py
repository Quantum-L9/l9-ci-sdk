"""Canonical finding policy classification."""

from __future__ import annotations
from dataclasses import dataclass
from l9_ci.contracts import (
    Finding,
    FindingClassification,
    ResolutionStatus,
    RuleMode,
)
from .model import FindingPolicy


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    classifications: tuple[FindingClassification, ...]
    unresolved_finding_ids: tuple[str, ...]

    def require_resolved(self) -> None:
        if self.unresolved_finding_ids:
            joined = ", ".join(self.unresolved_finding_ids)
            raise ValueError(f"unresolved finding classifications: {joined}")


def classify_findings(
    findings: tuple[Finding, ...],
    policy: FindingPolicy,
    *,
    strict: bool,
) -> ClassificationResult:
    classifications: list[FindingClassification] = []
    unresolved: list[str] = []
    for finding in sorted(findings, key=lambda item: item.finding_id):
        rule = policy.rules.get(finding.provider_rule_id)
        if rule is not None:
            classification = FindingClassification(
                finding_id=finding.finding_id,
                mode=rule.mode,
                resolution_status=ResolutionStatus.EXPLICIT,
                used_default=False,
                policy_key=rule.policy_key,
                policy_version=policy.version,
            )
        elif policy.default_mode is RuleMode.UNRESOLVED:
            classification = FindingClassification(
                finding_id=finding.finding_id,
                mode=RuleMode.UNRESOLVED,
                resolution_status=ResolutionStatus.UNRESOLVED,
                used_default=False,
                policy_version=policy.version,
            )
            unresolved.append(finding.finding_id)
        else:
            classification = FindingClassification(
                finding_id=finding.finding_id,
                mode=policy.default_mode,
                resolution_status=ResolutionStatus.DEFAULTED,
                used_default=True,
                policy_version=policy.version,
            )
        classifications.append(classification)
    result = ClassificationResult(
        classifications=tuple(classifications),
        unresolved_finding_ids=tuple(sorted(unresolved)),
    )
    if strict:
        result.require_resolved()
    return result
