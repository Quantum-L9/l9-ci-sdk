"""Projection from canonical finding bundle to agent-review payload."""

from __future__ import annotations
from l9_ci.contracts import (
    Finding,
    FindingBundle,
    FindingClassification,
    ResolutionStatus,
    RuleMode,
)
from .agent_payload import AgentFinding, AgentReviewPayload


def project_agent_review_payload(
    bundle: FindingBundle,
    *,
    strict: bool,
) -> AgentReviewPayload:
    classifications = {
        classification.finding_id: classification
        for classification in bundle.classifications
    }
    buckets: dict[RuleMode, list[AgentFinding]] = {
        RuleMode.BLOCKING: [],
        RuleMode.ADVISORY: [],
        RuleMode.SHADOW: [],
        RuleMode.DISABLED: [],
        RuleMode.UNRESOLVED: [],
    }
    autofix_candidates: list[AgentFinding] = []
    for finding in sorted(bundle.findings, key=lambda item: item.finding_id):
        classification = classifications.get(finding.finding_id)
        if classification is None:
            classification = FindingClassification(
                finding_id=finding.finding_id,
                mode=RuleMode.UNRESOLVED,
                resolution_status=ResolutionStatus.UNRESOLVED,
                used_default=False,
            )
        projected = _project_finding(finding, classification)
        buckets[classification.mode].append(projected)
        if _is_autofix_candidate(finding, classification):
            autofix_candidates.append(projected)
    if strict and buckets[RuleMode.UNRESOLVED]:
        unresolved_ids = ", ".join(
            finding.finding_id for finding in buckets[RuleMode.UNRESOLVED]
        )
        raise ValueError(
            f"strict payload projection rejected unresolved findings: {unresolved_ids}"
        )
    return AgentReviewPayload(
        SDK_version=bundle.SDK_version,
        source_bundle_schema=bundle.schema,
        source_bundle_schema_version=bundle.schema_version,
        snapshot_id=bundle.snapshot.snapshot_id,
        blocking_findings=tuple(buckets[RuleMode.BLOCKING]),
        advisory_findings=tuple(buckets[RuleMode.ADVISORY]),
        shadow_findings=tuple(buckets[RuleMode.SHADOW]),
        unresolved_findings=tuple(buckets[RuleMode.UNRESOLVED]),
        disabled_findings=tuple(buckets[RuleMode.DISABLED]),
        autofix_candidates=tuple(
            sorted(
                autofix_candidates,
                key=lambda item: item.finding_id,
            )
        ),
        provider_failures=tuple(
            failure.to_dict()
            for failure in sorted(
                bundle.provider_failures,
                key=lambda item: (
                    item.provider_id,
                    item.failure_type.value,
                    item.message,
                ),
            )
        ),
        coverage=tuple(
            item.to_dict()
            for item in sorted(
                bundle.coverage,
                key=lambda item: item.provider_id,
            )
        ),
        limitations=tuple(sorted(bundle.limitations)),
    )


def _project_finding(
    finding: Finding,
    classification: FindingClassification,
) -> AgentFinding:
    return AgentFinding(
        finding_id=finding.finding_id,
        provider_id=finding.provider_id,
        provider_rule_id=finding.provider_rule_id,
        canonical_rule_id=finding.canonical_rule_id,
        policy_key=classification.policy_key,
        severity=finding.severity.value if finding.severity else None,
        category=finding.category,
        message=finding.message,
        fingerprint=finding.fingerprint,
        locations=tuple(location.to_dict() for location in finding.locations),
        limitations=finding.limitations,
    )


def _is_autofix_candidate(
    finding: Finding,
    classification: FindingClassification,
) -> bool:
    if classification.mode in {
        RuleMode.DISABLED,
        RuleMode.UNRESOLVED,
    }:
        return False
    return finding.remediation_class in {
        "safe-autofix",
        "mechanical",
    }
