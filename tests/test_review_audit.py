from __future__ import annotations

from pathlib import Path

from l9_ci.review import (
    AGENT_REVIEW_MARKER,
    apply_effective_mode,
    render_comment,
    run_audit_agent,
    run_review,
)


def _make_repo(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("from x import PacketEnvelope\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text("from x import TransportPacket\n", encoding="utf-8")


def test_audit_agent_flags_packet_envelope_as_transport(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    findings = run_audit_agent(tmp_path, ["bad.py"], file_mode="filesystem")
    transport = [f for f in findings if f.category == "transport"]
    assert transport, "PacketEnvelope must be flagged as a transport finding"
    f = transport[0]
    assert f.severity == "critical"
    assert f.touched is True
    # Touched + dangerous ⇒ tier policy recommends blocking (before promotion gate).
    assert f.recommended_mode == "blocking"


def test_inherited_finding_is_advisory_not_touched(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    findings = run_audit_agent(tmp_path, changed_files=[], file_mode="filesystem")
    transport = [f for f in findings if f.category == "transport"][0]
    assert transport.touched is False
    assert transport.recommended_mode == "advisory"  # inherited debt is advisory


def test_advisory_only_until_promoted(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    findings = run_audit_agent(tmp_path, ["bad.py"], file_mode="filesystem")
    rule_id = [f for f in findings if f.category == "transport"][0].rule_id

    # advisory agent, no promotions ⇒ nothing blocks even though touched+dangerous
    advisory = apply_effective_mode(findings, agent_mode="advisory", promotions=set())
    assert all(f.mode != "blocking" for f in advisory)

    # promote the rule ⇒ the touched dangerous finding blocks
    promoted = apply_effective_mode(findings, agent_mode="advisory", promotions={rule_id})
    assert any(f.mode == "blocking" and f.rule_id == rule_id for f in promoted)

    # shadow agent ⇒ nothing surfaces
    shadow = apply_effective_mode(findings, agent_mode="shadow", promotions={rule_id})
    assert all(f.mode == "shadow" for f in shadow)


def test_run_review_advisory_report_and_comment(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    report = run_review(
        tmp_path,
        ["bad.py"],
        pr_class="app_code",
        agents=["audit"],
        agent_modes={"audit": "advisory"},
        promotions=set(),
        file_mode="filesystem",
        trace_id="trace-123",
    )
    assert report.blocking_count == 0
    assert report.advisory_count >= 1
    assert report.agents[0]["trace_id"] == "trace-123"
    assert report.agents[0]["role"] == "deterministic-audit"

    comment = render_comment(report)
    assert AGENT_REVIEW_MARKER in comment
    assert "advisory_only" in comment
    assert len(comment) <= 65336


def test_unknown_agent_is_skipped_cleanly(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    report = run_review(tmp_path, ["bad.py"], agents=["llm"], file_mode="filesystem")
    assert report.agents[0]["failure_reason"] == "agent_not_registered"


def test_comment_truncates_to_limit(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    report = run_review(tmp_path, ["bad.py"], agent_modes={"audit": "advisory"}, file_mode="filesystem")
    body = render_comment(report, max_chars=200)
    assert len(body) <= 200
