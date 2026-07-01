"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
engine: platform
layer: [sdk, review, agent-review-loop]
tags: [L9_CI, agent-review-loop, comment-protocol, marker]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

from .report import ReviewReport

# Stable marker from the L9 CI Kernel comment-protocol. The workflow finds this
# exact marker and updates the existing comment (never duplicates).
AGENT_REVIEW_MARKER = "<!-- l9-agent-review-marker: v1 -->"

# Comment-protocol limits (kernel): GitHub hard limit 65536, 200 char buffer.
MAX_COMMENT_CHARS = 65336
MAX_LINE_CHARS = 500


def _line(f: dict[str, object]) -> str:
    loc = f.get("file") or "(repo)"
    line = f.get("line")
    where = f"{loc}:{line}" if line else str(loc)
    msg = str(f.get("message", ""))
    if len(msg) > MAX_LINE_CHARS:
        msg = msg[:MAX_LINE_CHARS] + "..."
    return f"- `{f.get('rule_id', '?')}` [{f.get('severity', '?')}] {msg} — `{where}`"


def render_comment(report: ReviewReport, *, max_chars: int = MAX_COMMENT_CHARS) -> str:
    """Render the single idempotent agent-review PR comment (advisory-first)."""
    blocking = [f for f in report.findings if f.get("mode") == "blocking"]
    advisory = [f for f in report.findings if f.get("mode") == "advisory"]

    lines: list[str] = [
        AGENT_REVIEW_MARKER,
        "## L9 Agent Review",
        "",
        "### Status",
        f"- Result: `{'blocking' if blocking else 'advisory_only'}`",
        f"- PR class: `{report.pr_class}`",
        f"- Blocking: **{len(blocking)}** · Advisory: **{len(advisory)}** · Shadow: **{report.shadow_count}**",
        "",
        "### Agents",
        "| Agent | Role | Model | Cost (USD) | Latency (ms) | Findings |",
        "|---|---|---|---:|---:|---:|",
    ]
    for a in report.agents:
        lines.append(
            f"| {a.get('agent')} | {a.get('role')} | {a.get('model') or '—'} | "
            f"{a.get('estimated_cost_usd', 0)} | {a.get('latency_ms', 0)} | {a.get('finding_count', 0)} |"
        )
    lines.append("")

    if blocking:
        lines += ["### Blocking findings", ""]
        lines += [_line(f) for f in blocking]
        lines.append("")
    lines += ["### Advisory findings", ""]
    lines += [_line(f) for f in advisory] if advisory else ["- none"]
    lines += [
        "",
        "_Proposal-only. No autofixes applied, nothing pushed or merged. "
        "Suggested patches are handed to Quantum-L9/PR_Repair._",
    ]

    body = "\n".join(lines) + "\n"
    if len(body) > max_chars:
        suffix = (
            "\n\n... truncated due to GitHub comment limit; see the uploaded "
            "agent-review-payload artifact ...\n"
        )
        # Guarantee the result is always <= max_chars for any positive
        # max_chars, even when max_chars is smaller than the suffix itself.
        if max_chars <= len(suffix):
            body = suffix[:max_chars]
        else:
            body = body[: max_chars - len(suffix)] + suffix
    return body
