"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
engine: platform
layer: [sdk, review, agent-review-loop]
tags: [L9_CI, agent-review-loop, deterministic-audit, transport-packet]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

from pathlib import Path

from l9_ci.governance import terminology_guard
from l9_ci.scanners import deprecated_api, packet_envelope
from l9_ci.utils.files import FileMode

from .report import ReviewFinding

AGENT = "audit_review_agent"
ROLE = "deterministic-audit"

# Categories the L9 blocking-policy treats as dangerous (hard-block when touched).
DANGEROUS_CATEGORIES = {"transport", "security", "contract", "runtime", "auth"}


def _rel_set(changed_files: list[str]) -> set[str]:
    return {c.replace("\\", "/").lstrip("./") for c in changed_files if c.strip()}


def _finding(
    *,
    rule_id: str,
    message: str,
    category: str,
    severity: str,
    file: str,
    line: int | None,
    touched: bool,
    suggestion: str = "",
) -> ReviewFinding:
    dangerous = category in DANGEROUS_CATEGORIES
    # Tier policy (L9 CI Kernel finding_policy): a dangerous finding blocks only
    # when the finding is in a touched file; inherited debt stays advisory.
    recommended = "blocking" if (dangerous and touched) else "advisory"
    return ReviewFinding(
        agent=AGENT,
        rule_id=rule_id,
        message=message,
        category=category,
        severity=severity,  # type: ignore[arg-type]
        file=file,
        line=line,
        touched=touched,
        recommended_mode=recommended,  # type: ignore[arg-type]
        mode="advisory",  # effective mode set later by policy.apply_effective_mode
        suggestion=suggestion,
    )


def run_audit_agent(
    root: Path,
    changed_files: list[str],
    *,
    file_mode: FileMode = "git_tracked",
) -> list[ReviewFinding]:
    """Deterministic reviewer. Composes existing L9 scanners and classifies each
    violation as touched (blocking-recommended) or inherited (advisory).

    Enforces LAW-T1 (TransportPacket only — PacketEnvelope forbidden) and the
    deprecated-API / terminology contracts. No LLM involved.
    """
    root = root.resolve()
    touched = _rel_set(changed_files)
    findings: list[ReviewFinding] = []

    # LAW-T1: PacketEnvelope is a superseded wire contract. transport category.
    for v in packet_envelope.scan([root], root=root, file_mode=file_mode):
        findings.append(
            _finding(
                rule_id=f"AUDIT-TRANSPORT-{v.code}",
                message=v.message,
                category="transport",
                severity="critical",
                file=v.file,
                line=v.line,
                touched=v.file in touched,
                suggestion="Replace PacketEnvelope usage with TransportPacket.",
            )
        )

    # Deprecated API migration (advisory contract). Violation exposes `.text`.
    for v in deprecated_api.check([root], root=root, file_mode=file_mode):
        findings.append(
            _finding(
                rule_id="AUDIT-DEPRECATED-API",
                message=v.text,
                category="deprecated_api",
                severity="medium",
                file=v.file,
                line=v.line,
                touched=v.file in touched,
                suggestion="Run `l9-ci fix-deprecated-api` or migrate manually.",
            )
        )

    # Terminology / style (low-severity, advisory even when touched).
    for v in terminology_guard.scan([root], file_mode=file_mode):
        findings.append(
            _finding(
                rule_id=f"AUDIT-STYLE-{v.pattern}",
                message=v.message,
                category="style",
                severity="low",
                file=v.file,
                line=v.line,
                touched=v.file in touched,
            )
        )

    return findings
