"""Human-actionable diagnostics for strict rule-identity failures.

Under ``--strict`` every normalized finding must carry a ``canonical_rule_id``.
When some do not, the run fails closed with ``unresolved_strict_contract``
(exit 6). That contract is correct, but the failure has to name something an
operator can act on.

The original message listed only ``finding_id`` values -- content-addressed
hashes that identify nothing a human or an identity map can be keyed on. A
central-CI failure across the Quantum-L9 fleet therefore reported fifty opaque
hashes and no way to tell which rules were unmapped, so the same red gate could
not be diagnosed from its own output.

Identity is resolved per *rule*, not per finding, so the diagnosis belongs at
rule granularity: group by ``provider_rule_id``, count the findings each rule
accounts for, and show one example location per rule. That is exactly the input
needed to either add ``metadata.l9.canonical_rule_id`` to an L9-authored rule or
add an identity-map entry for a third-party registry rule.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

# Keep a failure legible in a CI log. A run that trips this on hundreds of
# distinct rules has one systemic cause, not hundreds; the head of the list is
# enough to find it, and the remainder is reported as a count.
MAX_REPORTED_RULES = 20


class _Located(Protocol):
    # Read-only members: a mutable protocol attribute is invariant, which would
    # reject the concrete `tuple[SourceLocation, ...]` the Finding contract uses.
    # Bodies are docstrings, matching `providers.spi.Provider` -- a bare `...`
    # is a statement with no effect and CodeQL reports it.
    @property
    def normalized_path(self) -> str:
        """Return the repository-relative source path."""

    @property
    def start_line(self) -> int | None:
        """Return the 1-based start line when the provider reported one."""


class _UnresolvedFinding(Protocol):
    @property
    def finding_id(self) -> str:
        """Return the content-addressed finding identifier."""

    @property
    def provider_rule_id(self) -> str:
        """Return the provider's own rule identifier."""

    @property
    def locations(self) -> Sequence[_Located]:
        """Return the source locations this finding was raised at."""


def _example_location(finding: _UnresolvedFinding) -> str:
    locations = tuple(finding.locations)
    if not locations:
        return ""
    location = locations[0]
    path = getattr(location, "normalized_path", "")
    if not path:
        return ""
    line = getattr(location, "start_line", None)
    return f"{path}:{line}" if line else path


def describe_unresolved_identity(findings: Iterable[_UnresolvedFinding]) -> str:
    """Return the strict-identity failure message for ``findings``.

    The message always begins with ``strict identity resolution failed`` so the
    CLI error boundary keeps classifying it as ``unresolved_strict_contract``.
    """
    grouped: dict[str, list[_UnresolvedFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.provider_rule_id, []).append(finding)

    if not grouped:  # pragma: no cover - callers only invoke on a non-empty set
        return "strict identity resolution failed for 0 findings"

    # Most-impactful rule first, then lexicographic so the message is stable
    # across runs and diffable between them.
    ordered = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    finding_total = sum(len(items) for _, items in ordered)

    lines = [
        f"strict identity resolution failed for {finding_total} finding(s) "
        f"across {len(ordered)} provider rule(s); every finding needs a "
        "canonical_rule_id. Add metadata.l9.canonical_rule_id to an L9-authored "
        "rule, or an identity-map entry for a third-party registry rule:"
    ]
    for provider_rule_id, items in ordered[:MAX_REPORTED_RULES]:
        example = _example_location(sorted(items, key=lambda f: f.finding_id)[0])
        suffix = f" (e.g. {example})" if example else ""
        lines.append(f"  - {provider_rule_id}: {len(items)} finding(s){suffix}")

    remaining = len(ordered) - MAX_REPORTED_RULES
    if remaining > 0:
        lines.append(f"  ... and {remaining} more provider rule(s)")
    return "\n".join(lines)
