"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
engine: platform
layer: [sdk, review, agent-review-loop]
tags: [L9_CI, agent-review-loop, llm-router, model-selection]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Deterministic PR-class → task descriptor mapping (input to @quantum-l9/llm-router).
# Higher-risk classes request stronger reasoning; docs/tests stay cheap.
_COMPLEXITY_BY_CLASS = {
    "docs_only": "trivial",
    "tests_only": "low",
    "ci_workflow": "low",
    "dependency": "low",
    "dependency_python": "low",
    "app_code": "high",
    "security": "critical",
    "compliance": "high",
    "unknown_diff": "high",
    "unknown": "high",
}


@dataclass(frozen=True)
class RoutingResult:
    model: str
    provider: str
    temperature: float
    max_tokens: int
    estimated_cost_usd: float
    reason: str
    budget_gated: bool

    @property
    def is_null(self) -> bool:
        return self.provider == "null"


def null_route(reason: str) -> RoutingResult:
    """Advisory-degraded route: no model available; the LLM lane reports nothing."""
    return RoutingResult(
        model="",
        provider="null",
        temperature=0.0,
        max_tokens=0,
        estimated_cost_usd=0.0,
        reason=reason,
        budget_gated=False,
    )


def build_task_descriptor(pr_class: str, *, requires_reasoning: bool = True) -> dict[str, object]:
    return {
        "type": "code_generation",  # LLM-Router TaskType for code review/generation
        "complexity": _COMPLEXITY_BY_CLASS.get(pr_class, "high"),
        "requiresReasoning": requires_reasoning,
        "requiresSearch": False,
        "description": f"L9 code review for pr_class={pr_class}",
    }


def resolve_route(
    task: dict[str, object],
    *,
    shim_path: str | None = None,
    timeout: int = 30,
) -> RoutingResult:
    """Resolve a model via the Node router-shim wrapping @quantum-l9/llm-router.

    The shim reads a TaskDescriptor JSON on stdin and writes a RoutingResult JSON
    on stdout. When the shim is absent or errors, degrade to a null route (the
    LLM lane then produces no findings) rather than failing the review.
    """
    shim = shim_path or os.environ.get("L9_LLM_ROUTER_SHIM", "")
    if not shim or not Path(shim).exists():
        return null_route("router_shim_absent")
    try:
        proc = subprocess.run(
            ["node", shim],
            input=json.dumps(task),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=True,
        )
        data = json.loads(proc.stdout)
        cfg = data.get("config", data)
        return RoutingResult(
            model=str(cfg.get("model", "")),
            provider=str(data.get("provider", cfg.get("provider", ""))),
            temperature=float(cfg.get("temperature", 0.0)),
            max_tokens=int(cfg.get("maxTokens", cfg.get("max_tokens", 1024))),
            estimated_cost_usd=float(data.get("estimatedCost", cfg.get("estimatedCostPerCall", 0.0))),
            reason=str(data.get("reason", "routed")),
            budget_gated=bool(data.get("budgetGated", False)),
        )
    except (subprocess.SubprocessError, json.JSONDecodeError, ValueError, OSError) as exc:
        return null_route(f"router_error:{type(exc).__name__}")
