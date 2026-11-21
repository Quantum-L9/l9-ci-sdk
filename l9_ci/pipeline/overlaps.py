"""Withdraw registry findings that a superseding packaged L9 finding covers.

The supersessions come from ``l9_ci/rulesets/semgrep/rule-overlaps.yaml``; the
command layer passes them here as a plain mapping (registry rule ID -> packaged
L9 rule ID), so this layer does not depend on the rulesets package.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from l9_ci.contracts import Finding


def _is_rule(provider_rule_id: str, rule_id: str) -> bool:
    """A packaged rule's check ID may carry Semgrep's config-path prefix."""
    return provider_rule_id == rule_id or provider_rule_id.endswith(f".{rule_id}")


def _span(finding: Finding) -> tuple[str, int, int] | None:
    if not finding.locations or finding.locations[0].start_line is None:
        return None
    location = finding.locations[0]
    start = location.start_line
    assert start is not None
    end = location.end_line if location.end_line is not None else start
    return location.normalized_path, start, end


def supersede_findings(
    findings: Iterable[Finding], supersessions: Mapping[str, str]
) -> tuple[tuple[Finding, ...], tuple[str, ...]]:
    """Withdraw registry findings that a superseding L9 finding covers.

    A finding of a superseded registry rule is withdrawn only when a finding of
    its superseding L9 rule sits in the same file and its span contains the
    registry finding's start line. Every other finding, including a registry
    finding no L9 finding covers, is kept. Returns the kept findings and one
    limitation per withdrawn registry rule.
    """
    items = tuple(findings)
    withdrawn: dict[tuple[str, str], list[str]] = {}
    kept: list[Finding] = []
    for finding in items:
        l9_rule = supersessions.get(finding.provider_rule_id)
        span = _span(finding)
        if l9_rule is None or span is None:
            kept.append(finding)
            continue
        path, line, _ = span
        covered = False
        for other in items:
            other_span = _span(other)
            if (
                other_span is not None
                and _is_rule(other.provider_rule_id, l9_rule)
                and other_span[0] == path
                and other_span[1] <= line <= other_span[2]
            ):
                covered = True
                break
        if not covered:
            kept.append(finding)
            continue
        withdrawn.setdefault((finding.provider_rule_id, l9_rule), []).append(
            f"{path}:{line}"
        )
    limitations = tuple(
        f"registry rule {rule} superseded by packaged rule {l9_rule}: "
        f"{len(sites)} finding(s) withdrawn where {l9_rule} reported the same "
        f"call, evidence kept ({', '.join(sorted(sites))})"
        for (rule, l9_rule), sites in sorted(withdrawn.items())
    )
    return tuple(kept), limitations


__all__ = ["supersede_findings"]
