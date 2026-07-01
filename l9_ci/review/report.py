"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
engine: platform
layer: [sdk, review, agent-review-loop]
tags: [L9_CI, agent-review-loop, review-findings]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# Effective mode of a finding after policy is applied. Review agents are
# advisory-only until a rule_id is promoted in blocking-policy.yaml, so the
# default effective mode is never "blocking" unless explicitly promoted.
FindingMode = Literal["blocking", "advisory", "shadow"]
Severity = Literal["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True)
class ReviewFinding:
    """One normalized finding from a review agent."""

    agent: str
    rule_id: str
    message: str
    category: str
    severity: Severity = "medium"
    file: str = ""
    line: int | None = None
    touched: bool = False
    # What the tier policy recommends (before promotion gating).
    recommended_mode: FindingMode = "advisory"
    # Effective mode after blocking-policy promotion gating is applied.
    mode: FindingMode = "advisory"
    autofix_safe: bool = False
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentRun:
    """Observability record for a single agent invocation (kernel: audit log)."""

    agent: str
    role: str
    model: str = ""
    provider: str = ""
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0
    trace_id: str = ""
    finding_count: int = 0
    failure_reason: str = ""
    human_intervention: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewReport:
    """Aggregate output of the review loop for one PR, advisory-first."""

    schema_version: int
    marker: str
    pr_class: str
    agents: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    blocking_count: int = 0
    advisory_count: int = 0
    shadow_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
