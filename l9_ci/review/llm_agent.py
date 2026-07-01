"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
engine: platform
layer: [sdk, review, agent-review-loop]
tags: [L9_CI, agent-review-loop, llm-review, proposal-only]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from l9_ci.utils.files import FileMode

from .report import AgentRun, ReviewFinding
from .router_client import RoutingResult, build_task_descriptor, resolve_route

AGENT = "llm_review_agent"
ROLE = "llm-contract-review"
PROMPT_VERSION = "v1"

# Contract-aware review prompt (ported from EIE tools/ai_review.py). The model
# MUST return STRICT JSON. Style/formatting/docstrings are explicitly excluded.
SYSTEM_PROMPT = """You are a senior engineer reviewing a pull request for an L9 constellation repo.

Focus ONLY on real-impact issues:
1. Contract violations (TransportPacket only; PacketEnvelope is forbidden; Gate-only egress; handler signature TransportPacket -> TransportPacket)
2. Security (injection, auth bypass, SSRF, path traversal, unvalidated input, secret exposure)
3. Architecture (chassis/engine isolation, direct node-to-node calls, missing Gate routing)
4. Bugs (logic errors, None deref, missing awaits)
5. Concurrency (races, deadlocks, unbounded fan-out)
6. Error handling (bare except, swallowed exceptions)

Do NOT flag style, formatting, naming, or missing docstrings.

Return STRICT JSON only (no markdown fences):
{"issues":[{"severity":"critical|high|medium|low","category":"contract|security|architecture|bug|concurrency|error_handling","file":"path","line_hint":"snippet","description":"what is wrong","suggestion":"how to fix"}],"summary":"one line","block":false}
If no issues: {"issues":[],"summary":"No issues found.","block":false}
"""

_PROVIDER_ENDPOINTS = {
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "perplexity": ("https://api.perplexity.ai/chat/completions", "PERPLEXITY_API_KEY"),
}

_DANGEROUS = {"contract", "security", "architecture"}


def _api_key_for(provider: str) -> str:
    _, env_name = _PROVIDER_ENDPOINTS.get(provider, ("", ""))
    return os.environ.get(env_name, "") if env_name else ""


def _map_issue(issue: dict, touched: set[str]) -> ReviewFinding:
    category = str(issue.get("category", "bug"))
    severity = str(issue.get("severity", "medium"))
    file = str(issue.get("file", ""))
    is_touched = file.replace("\\", "/").lstrip("./") in touched
    recommended = "blocking" if (category in _DANGEROUS and severity in {"critical", "high"} and is_touched) else "advisory"
    return ReviewFinding(
        agent=AGENT,
        rule_id=f"LLM-{category.upper()}",
        message=str(issue.get("description", "")),
        category=category,
        severity=severity,  # type: ignore[arg-type]
        file=file,
        line=None,
        touched=is_touched,
        recommended_mode=recommended,  # type: ignore[arg-type]
        mode="advisory",
        suggestion=str(issue.get("suggestion", "")),
    )


def run_llm_agent(
    root: Path,
    changed_files: list[str],
    *,
    pr_class: str = "unknown_diff",
    diff_text: str = "",
    file_mode: FileMode = "git_tracked",  # noqa: ARG001 - parity with deterministic agents
    shim_path: str | None = None,
    trace_id: str = "",
    timeout: int = 60,
) -> tuple[list[ReviewFinding], AgentRun]:
    """LLM reviewer. Resolves a model via the router, calls the provider, and
    returns normalized findings. Degrades to a Null client (no findings) when the
    router, provider key, or diff are absent. NEVER persists the raw llm_response.
    """
    started = time.perf_counter()
    route = resolve_route(build_task_descriptor(pr_class), shim_path=shim_path)

    def _run(reason: str, *, findings: list[ReviewFinding], route: RoutingResult) -> tuple[list[ReviewFinding], AgentRun]:
        return findings, AgentRun(
            agent=AGENT,
            role=ROLE,
            model=route.model,
            provider=route.provider,
            estimated_cost_usd=route.estimated_cost_usd,
            latency_ms=int((time.perf_counter() - started) * 1000),
            trace_id=trace_id,
            finding_count=len(findings),
            failure_reason=reason,
        )

    if route.is_null:
        return _run(f"null_llm_client:{route.reason}", findings=[], route=route)
    if not diff_text.strip():
        return _run("no_diff", findings=[], route=route)
    api_key = _api_key_for(route.provider)
    if not api_key:
        return _run(f"missing_api_key:{route.provider}", findings=[], route=route)

    try:
        import httpx

        endpoint, _ = _PROVIDER_ENDPOINTS[route.provider]
        payload = {
            "model": route.model,
            "temperature": route.temperature,
            "max_tokens": route.max_tokens or 2048,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": diff_text[:400_000]},
            ],
        }
        resp = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        # Parse STRICT JSON. The raw content (llm_response) is deliberately NOT
        # stored anywhere — only parsed, normalized findings survive.
        parsed = json.loads(content)
        touched = {c.replace("\\", "/").lstrip("./") for c in changed_files}
        findings = [_map_issue(i, touched) for i in parsed.get("issues", [])]
        return _run("", findings=findings, route=route)
    except Exception as exc:  # noqa: BLE001 - fail advisory-degraded, never block on LLM errors
        return _run(f"llm_error:{type(exc).__name__}", findings=[], route=route)
