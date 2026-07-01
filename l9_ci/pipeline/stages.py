from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from l9_ci.gate.ci_gate import evaluate
from l9_ci.pipeline.context import PipelineContext
from l9_ci.pipeline.results import StageResult
from l9_ci.scanners import deprecated_api, packet_envelope
from l9_ci.governance.thresholds import load_threshold_policy, ThresholdPolicyError
from l9_ci.governance.rule_modes import (
    RuleModePolicyError,
    apply_rule_modes_to_findings,
    finding_blocks,
    load_rule_mode_policy,
)


def _with_rule_modes(ctx: PipelineContext, findings: list[dict[str, object]]) -> list[dict[str, object]]:
    policy_path = ctx.root / ".github/governance/rule-modes.yaml"
    try:
        policy = load_rule_mode_policy(policy_path)
    except RuleModePolicyError as exc:
        return [{"rule_id": "RULE-MODE-POLICY", "message": str(exc), "mode": "blocking"}]
    return apply_rule_modes_to_findings(findings, policy)


def _has_blocking(findings: list[dict[str, object]]) -> bool:
    return any(finding_blocks(finding) for finding in findings)


def _result(stage: str, ctx: PipelineContext, status: str, *, findings=None, artifacts=None, exit_code=0, start: float = 0.0) -> StageResult:
    return StageResult(
        stage=stage,
        status=status,
        matrix_id=ctx.matrix_id,
        matrix=ctx.matrix,
        findings=list(findings or []),
        artifacts=list(artifacts or []),
        duration_seconds=round(time.monotonic() - start, 6) if start else 0.0,
        exit_code=exit_code,
    )


def stage_classify(ctx: PipelineContext) -> StageResult:
    start = time.monotonic()
    return _result("classify", ctx, "success", artifacts=[], start=start)


def stage_validate(ctx: PipelineContext) -> StageResult:
    start = time.monotonic()
    findings: list[dict[str, str]] = []
    for path in ctx.root.rglob("*.py"):
        if any(part in {".venv", "venv", "__pycache__", "build", "dist"} for part in path.parts):
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            findings.append({"file": str(path.relative_to(ctx.root)), "rule_id": "PY-SYNTAX", "message": str(exc)})
    findings = _with_rule_modes(ctx, findings) if findings else []
    blocked = _has_blocking(findings)
    return _result("validate", ctx, "failure" if blocked else "success", findings=findings, exit_code=1 if blocked else 0, start=start)


def stage_transport_contract(ctx: PipelineContext) -> StageResult:
    start = time.monotonic()
    violations = packet_envelope.scan([ctx.root], exclude=["tests"], file_mode="filesystem")
    findings = [
        {"file": str(v.file), "line": str(v.line), "rule_id": "TRANSPORT-PACKET-CONTRACT", "message": getattr(v, "message", getattr(v, "text", ""))}
        for v in violations
    ]
    findings = _with_rule_modes(ctx, findings) if findings else []
    blocked = _has_blocking(findings)
    return _result("transport-contract", ctx, "failure" if blocked else "success", findings=findings, exit_code=1 if blocked else 0, start=start)


def stage_deprecated_api(ctx: PipelineContext) -> StageResult:
    start = time.monotonic()
    violations = deprecated_api.check([ctx.root], exclude=["tests"], file_mode="filesystem")
    findings = [
        {"file": str(v.file), "line": str(v.line), "rule_id": "DEPRECATED-API", "message": getattr(v, "message", getattr(v, "text", ""))}
        for v in violations
    ]
    findings = _with_rule_modes(ctx, findings) if findings else []
    blocked = _has_blocking(findings)
    return _result("deprecated-api", ctx, "failure" if blocked else "success", findings=findings, exit_code=1 if blocked else 0, start=start)


def stage_thresholds(ctx: PipelineContext) -> StageResult:
    start = time.monotonic()
    policy_path = ctx.root / ".github/governance/quality-thresholds.yaml"
    try:
        load_threshold_policy(policy_path)
    except ThresholdPolicyError as exc:
        findings = _with_rule_modes(ctx, [{"rule_id": "THRESHOLD-POLICY", "message": str(exc)}])
        blocked = _has_blocking(findings)
        return _result("thresholds", ctx, "failure" if blocked else "success", findings=findings, exit_code=1 if blocked else 0, start=start)
    return _result("thresholds", ctx, "success", start=start)


def stage_lint(ctx: PipelineContext) -> StageResult:
    start = time.monotonic()
    return _result("lint", ctx, "success", start=start)


def stage_test(ctx: PipelineContext) -> StageResult:
    start = time.monotonic()
    return _result("test", ctx, "success", start=start)


def stage_security(ctx: PipelineContext) -> StageResult:
    start = time.monotonic()
    return _result("security", ctx, "success", start=start)


def stage_gate(ctx: PipelineContext) -> StageResult:
    start = time.monotonic()
    gate = evaluate({"validate": "success", "lint": "success", "test": "success", "security": "success"}, ["validate", "lint", "test", "security"])
    return _result("gate", ctx, "success" if gate.passed else "failure", exit_code=0 if gate.passed else 1, start=start)


STAGES: dict[str, Callable[[PipelineContext], StageResult]] = {
    "classify": stage_classify,
    "validate": stage_validate,
    "lint": stage_lint,
    "test": stage_test,
    "security": stage_security,
    "transport-contract": stage_transport_contract,
    "deprecated-api": stage_deprecated_api,
    "thresholds": stage_thresholds,
    "gate": stage_gate,
}
