"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
engine: platform
layer: [sdk, review, agent-review-loop]
tags: [L9_CI, agent-review-loop, blocking-policy, promotion-gate]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

from dataclasses import replace

from .report import FindingMode, ReviewFinding


def effective_mode(
    finding: ReviewFinding,
    *,
    agent_mode: FindingMode,
    promotions: set[str],
) -> FindingMode:
    """Resolve a finding's effective mode.

    Doctrine: the Agent Review Loop is advisory-only until a rule_id is
    explicitly promoted in blocking-policy.yaml (``review_blocking_promotions``).
    A shadow agent surfaces nothing. A finding blocks ONLY when its agent is not
    in shadow, the tier policy recommended blocking, and the rule_id is promoted.
    """
    if agent_mode == "shadow":
        return "shadow"
    if finding.recommended_mode == "blocking" and finding.rule_id in promotions:
        return "blocking"
    return "advisory"


def apply_effective_mode(
    findings: list[ReviewFinding],
    *,
    agent_mode: FindingMode,
    promotions: set[str],
) -> list[ReviewFinding]:
    return [
        replace(f, mode=effective_mode(f, agent_mode=agent_mode, promotions=promotions))
        for f in findings
    ]
