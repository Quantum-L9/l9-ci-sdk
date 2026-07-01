"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
engine: platform
layer: [sdk, review, agent-review-loop]
tags: [L9_CI, agent-review-loop, orchestrator]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

import time
from pathlib import Path

from l9_ci.utils.files import FileMode

from . import audit_agent
from .llm_agent import run_llm_agent
from .policy import apply_effective_mode
from .render import AGENT_REVIEW_MARKER
from .report import AgentRun, FindingMode, ReviewReport

SCHEMA_VERSION = 1

# Agent registry. Phase 3 adds "llm" (llm_review_agent) here.
DETERMINISTIC_AGENTS = {"audit": (audit_agent.run_audit_agent, audit_agent.AGENT, audit_agent.ROLE)}


def run_review(
    root: Path,
    changed_files: list[str],
    *,
    pr_class: str = "unknown_diff",
    agents: list[str] | None = None,
    agent_modes: dict[str, FindingMode] | None = None,
    promotions: set[str] | None = None,
    file_mode: FileMode = "git_tracked",
    trace_id: str = "",
    diff_text: str = "",
    shim_path: str | None = None,
) -> ReviewReport:
    """Run the selected review agents and aggregate an advisory-first report.

    ``agent_modes`` maps each agent to its rule-mode (shadow/advisory/blocking).
    Agents default to ``shadow`` — nothing surfaces until deliberately promoted.
    """
    agents = agents or ["audit"]
    agent_modes = agent_modes or {}
    promotions = promotions or set()

    all_findings: list[dict[str, object]] = []
    runs: list[dict[str, object]] = []

    for name in agents:
        mode: FindingMode = agent_modes.get(name, "shadow")
        if name == "llm":
            raw, run = run_llm_agent(
                root,
                changed_files,
                pr_class=pr_class,
                diff_text=diff_text,
                file_mode=file_mode,
                shim_path=shim_path,
                trace_id=trace_id,
            )
            effective = apply_effective_mode(raw, agent_mode=mode, promotions=promotions)
            all_findings.extend(f.to_dict() for f in effective)
            runs.append(run.to_dict())
            continue
        entry = DETERMINISTIC_AGENTS.get(name)
        if entry is None:
            # Non-deterministic agents (e.g. "llm") are wired in Phase 3; skip
            # cleanly here so the deterministic path ships independently.
            runs.append(
                AgentRun(
                    agent=name, role="unavailable", failure_reason="agent_not_registered"
                ).to_dict()
            )
            continue
        fn, agent_id, role = entry
        started = time.perf_counter()
        raw = fn(root, changed_files, file_mode=file_mode)
        effective = apply_effective_mode(raw, agent_mode=mode, promotions=promotions)
        latency_ms = int((time.perf_counter() - started) * 1000)
        all_findings.extend(f.to_dict() for f in effective)
        runs.append(
            AgentRun(
                agent=agent_id,
                role=role,
                trace_id=trace_id,
                latency_ms=latency_ms,
                finding_count=len(effective),
            ).to_dict()
        )

    blocking = sum(1 for f in all_findings if f["mode"] == "blocking")
    advisory = sum(1 for f in all_findings if f["mode"] == "advisory")
    shadow = sum(1 for f in all_findings if f["mode"] == "shadow")

    return ReviewReport(
        schema_version=SCHEMA_VERSION,
        marker=AGENT_REVIEW_MARKER,
        pr_class=pr_class,
        agents=runs,
        findings=all_findings,
        blocking_count=blocking,
        advisory_count=advisory,
        shadow_count=shadow,
    )
