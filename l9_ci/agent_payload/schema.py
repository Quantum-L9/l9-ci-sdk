"""
L9_META
l9_schema: 1
origin: l9-ci-universal-base
layer: [sdk, schema, agent-payload]
tags: [L9_TEMPLATE, agent-payload, schema]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

GateStatus = Literal["pass", "fail"]
FindingMode = Literal["blocking", "advisory", "shadow", "disabled"]


@dataclass(frozen=True)
class NormalizedFinding:
    rule_id: str
    message: str
    file: str = ""
    line: int | None = None
    severity: str = "medium"
    mode: FindingMode = "blocking"
    stage: str = ""
    matrix_id: str = "default"
    autofix_safe: bool = False
    recommended_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MatrixRun:
    stage: str
    matrix_id: str
    matrix: dict[str, str]
    status: str
    summary_path: str
    duration_seconds: float
    findings_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactProvenance:
    input_dir: str
    consumed_files: list[str]
    missing_expected_files: list[str] = field(default_factory=list)
    duplicate_matrix_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentReviewPayload:
    repo: str
    commit: str
    branch: str
    pr_number: str | None
    pr_class: str
    gate_status: GateStatus
    rule_modes_hash: str
    policy_hash: str
    blocking_findings: list[dict[str, Any]]
    advisory_findings: list[dict[str, Any]]
    failed_checks: list[dict[str, Any]]
    skipped_checks: list[dict[str, Any]]
    infrastructure_failures: list[dict[str, Any]]
    autofix_candidates: list[dict[str, Any]]
    manual_review_required: list[dict[str, Any]]
    next_actions: list[str]
    matrix_runs: list[dict[str, Any]]
    artifact_provenance: dict[str, Any]
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
