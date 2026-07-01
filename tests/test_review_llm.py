from __future__ import annotations

from pathlib import Path

from l9_ci.review.llm_agent import run_llm_agent
from l9_ci.review.orchestrator import run_review
from l9_ci.review.router_client import build_task_descriptor, resolve_route


def test_task_descriptor_complexity_by_class() -> None:
    assert build_task_descriptor("security")["complexity"] == "critical"
    assert build_task_descriptor("docs_only")["complexity"] == "trivial"
    assert build_task_descriptor("app_code")["complexity"] == "high"


def test_router_null_when_shim_absent(monkeypatch) -> None:
    monkeypatch.delenv("L9_LLM_ROUTER_SHIM", raising=False)
    route = resolve_route(build_task_descriptor("app_code"), shim_path=None)
    assert route.is_null
    assert route.reason == "router_shim_absent"


def test_llm_agent_degrades_to_null(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("L9_LLM_ROUTER_SHIM", raising=False)
    findings, run = run_llm_agent(
        tmp_path, ["a.py"], pr_class="app_code", diff_text="--- a/x\n+++ b/x\n", shim_path=None
    )
    assert findings == []
    assert run.agent == "llm_review_agent"
    assert run.failure_reason.startswith("null_llm_client")


def test_run_review_with_llm_shadow_does_not_crash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("L9_LLM_ROUTER_SHIM", raising=False)
    (tmp_path / "bad.py").write_text("from x import PacketEnvelope\n", encoding="utf-8")
    report = run_review(
        tmp_path,
        ["bad.py"],
        agents=["audit", "llm"],
        agent_modes={"audit": "advisory", "llm": "shadow"},
        file_mode="filesystem",
        diff_text="--- a/bad.py\n+++ b/bad.py\n",
    )
    roles = {a["agent"] for a in report.agents}
    assert "audit_review_agent" in roles
    assert "llm_review_agent" in roles
    # LLM lane produced nothing (router absent); deterministic lane still advisory.
    assert report.advisory_count >= 1
