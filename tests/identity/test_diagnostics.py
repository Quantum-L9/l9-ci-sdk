"""Unit tests for the strict rule-identity failure diagnostic.

Regression origin: Quantum-L9 central CI (`Organization CI (Core)`) failed
closed on every Python consumer with `unresolved_strict_contract`, and the
message listed only content-addressed `finding_id` hashes. Nothing in that
output named a rule, so the blocking failure could not be diagnosed from its
own log. These tests lock the properties that make it actionable.
"""

from __future__ import annotations

from l9_ci.commands.errors import classify_exception
from l9_ci.cli import ExitCode
from l9_ci.contracts.source import SourceLocation
from l9_ci.identity import describe_unresolved_identity


class _Finding:
    """Minimal stand-in carrying only the attributes the diagnostic reads."""

    def __init__(self, finding_id, provider_rule_id, locations=()):
        self.finding_id = finding_id
        self.provider_rule_id = provider_rule_id
        self.locations = locations


def _finding(index: int, rule: str, path: str | None = None, line: int | None = None):
    locations = (SourceLocation(normalized_path=path, start_line=line),) if path else ()
    return _Finding(f"fn_semgrep_{index:04d}", rule, locations)


def test_message_names_provider_rules_not_only_finding_hashes() -> None:
    message = describe_unresolved_identity(
        [
            _finding(1, "python.lang.security.audit.eval-detected", "app/run.py", 31),
            _finding(2, "python.lang.security.audit.eval-detected", "app/other.py", 7),
            _finding(3, "python.lang.security.audit.subprocess-shell-true", "b.py", 2),
        ]
    )
    assert "python.lang.security.audit.eval-detected" in message
    assert "python.lang.security.audit.subprocess-shell-true" in message
    # The rule id is the actionable key; opaque finding hashes are not the payload.
    assert "fn_semgrep_0001" not in message


def test_rules_are_ordered_by_impact_then_name() -> None:
    message = describe_unresolved_identity(
        [
            _finding(1, "rule.b"),
            _finding(2, "rule.a"),
            _finding(3, "rule.a"),
        ]
    )
    assert message.index("rule.a") < message.index("rule.b")
    assert "rule.a: 2 finding(s)" in message
    assert "rule.b: 1 finding(s)" in message


def test_counts_report_findings_and_distinct_rules() -> None:
    message = describe_unresolved_identity(
        [_finding(i, f"rule.{i % 3}") for i in range(9)]
    )
    assert "9 finding(s)" in message
    assert "3 provider rule(s)" in message


def test_example_location_is_included_when_available() -> None:
    message = describe_unresolved_identity([_finding(1, "rule.a", "pkg/mod.py", 42)])
    assert "pkg/mod.py:42" in message


def test_missing_location_degrades_without_raising() -> None:
    message = describe_unresolved_identity([_finding(1, "rule.a")])
    assert "rule.a: 1 finding(s)" in message
    assert "e.g." not in message


def test_long_rule_sets_are_bounded_and_report_the_remainder() -> None:
    message = describe_unresolved_identity(
        [_finding(i, f"rule.{i:03d}") for i in range(30)]
    )
    listed = [line for line in message.splitlines() if line.startswith("  - ")]
    assert len(listed) == 20
    assert "... and 10 more provider rule(s)" in message


def test_message_is_deterministic_across_input_order() -> None:
    findings = [_finding(i, f"rule.{i % 4}") for i in range(12)]
    assert describe_unresolved_identity(findings) == describe_unresolved_identity(
        list(reversed(findings))
    )


def test_message_still_classifies_as_unresolved_strict_contract() -> None:
    """The CLI error boundary keys on the message text; exit 6 must not drift."""
    message = describe_unresolved_identity([_finding(1, "rule.a")])
    code, exit_code = classify_exception(
        ValueError(message), default=ExitCode.PROVIDER_EXECUTION_FAILURE
    )
    assert code == "unresolved_strict_contract"
    assert exit_code == ExitCode.UNRESOLVED_STRICT_CONTRACT
