"""Regression guard for the exact defect this GMP fixed: L9-authored Semgrep
rules under ``l9_ci/rulesets/semgrep/`` were originally authored with
``metadata.l9_rule_id: X`` (a flat key the resolver never reads), while
``SemgrepProvider._trusted_canonical_rule_id`` only ever reads
``metadata.l9.canonical_rule_id`` (see ``l9_ci/providers/semgrep/provider.py``).
Every finding from these rules therefore silently fell through to
``UNRESOLVED`` identity resolution instead of ``TRUSTED_METADATA`` -- with no
error, just quietly wrong data. This suite loads every packaged rule file
directly (independent of the resolver/provider code paths those modules
already test) and asserts the metadata shape the provider actually reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from l9_ci.rulesets.semgrep import SUPPORTED_LANGUAGES, ruleset_dir


def _load_rules(path: Path) -> list[Mapping[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping), f"{path}: root must be a mapping"
    rules = payload.get("rules")
    assert isinstance(rules, list) and rules, f"{path}: expected a non-empty rules list"
    return rules


def _rule_files() -> list[Path]:
    files: list[Path] = []
    for language in SUPPORTED_LANGUAGES:
        files.extend(sorted(ruleset_dir(language).glob("*.yml")))
    assert files, "expected packaged Semgrep rule files across all languages"
    return files


@pytest.mark.parametrize("rule_file", _rule_files(), ids=lambda p: p.name)
def test_every_rule_carries_trusted_l9_canonical_rule_id(rule_file: Path) -> None:
    for rule in _load_rules(rule_file):
        rule_id = rule.get("id")
        metadata = rule.get("metadata")
        assert isinstance(metadata, Mapping), (
            f"{rule_file.name}:{rule_id}: rule metadata must be an object"
        )
        assert "l9_rule_id" not in metadata, (
            f"{rule_file.name}:{rule_id}: found legacy flat 'l9_rule_id' key -- "
            "the resolver only reads metadata.l9.canonical_rule_id (nested); "
            "a flat key is silently ignored, not an error"
        )
        l9_metadata = metadata.get("l9")
        assert isinstance(l9_metadata, Mapping), (
            f"{rule_file.name}:{rule_id}: metadata.l9 must be an object "
            "(the shape SemgrepProvider._trusted_canonical_rule_id reads)"
        )
        canonical_rule_id = l9_metadata.get("canonical_rule_id")
        assert isinstance(canonical_rule_id, str) and canonical_rule_id.strip(), (
            f"{rule_file.name}:{rule_id}: metadata.l9.canonical_rule_id must be "
            "a non-empty string"
        )


def test_canonical_rule_ids_are_unique_within_each_ruleset_directory() -> None:
    for language in SUPPORTED_LANGUAGES:
        canonical_ids: dict[str, str] = {}
        for rule_file in sorted(ruleset_dir(language).glob("*.yml")):
            for rule in _load_rules(rule_file):
                canonical_rule_id = rule["metadata"]["l9"]["canonical_rule_id"]
                assert canonical_rule_id not in canonical_ids, (
                    f"duplicate canonical_rule_id {canonical_rule_id!r} in "
                    f"{language} ruleset: {canonical_ids[canonical_rule_id]} and "
                    f"{rule_file.name} both claim it"
                )
                canonical_ids[canonical_rule_id] = rule_file.name


def test_every_rule_declares_a_staged_rollout_mode() -> None:
    """Every packaged L9 rule must self-document its rollout mode (shadow,
    advisory, blocking) so a new rule cannot silently ship at a stricter
    stage than the staged disabled -> shadow -> advisory -> blocking rollout
    `.github/governance/promotion-policy.yaml` requires."""
    allowed_modes = {"disabled", "shadow", "advisory", "blocking"}
    for rule_file in _rule_files():
        for rule in _load_rules(rule_file):
            mode = rule["metadata"].get("mode")
            assert mode in allowed_modes, (
                f"{rule_file.name}:{rule['id']}: metadata.mode must be one of "
                f"{sorted(allowed_modes)}, got {mode!r}"
            )


# Semgrep's rule schema divides operators into two groups: the pattern
# operators that may stand alone at rule top level (`pattern`, `patterns`,
# `pattern-either`, `pattern-regex`) and the *constraint* operators below,
# which -- per
# https://docs.semgrep.dev/writing-rules/rule-syntax -- "must be nested
# underneath a `patterns` field". A constraint written as a sibling of
# `pattern-either` is not a schema error: `semgrep --validate` reports the
# config valid and then silently drops the constraint, so the rule matches
# everything its bare pattern matches.
#
# That defect shipped in two packaged rules and produced 79 false positives
# across the fleet: `l9.logging.forbidden-secret-field` flagged every logger
# call with an argument (`logging.getLogger(__name__)` included) because its
# $SECRET regex never applied, and
# `l9.handler.missing-transportpacket-return` would have flagged compliant
# `-> TransportPacket` handlers for the same reason.
SEMGREP_PATTERNS_ONLY_OPERATORS = frozenset(
    {
        "focus-metavariable",
        "metavariable-analysis",
        "metavariable-comparison",
        "metavariable-pattern",
        "metavariable-regex",
        "metavariable-type",
        "pattern-inside",
        "pattern-not",
        "pattern-not-inside",
        "pattern-not-regex",
    }
)


@pytest.mark.parametrize("rule_file", _rule_files(), ids=lambda p: p.name)
def test_constraint_operators_are_nested_under_patterns(rule_file: Path) -> None:
    for rule in _load_rules(rule_file):
        misplaced = sorted(SEMGREP_PATTERNS_ONLY_OPERATORS & set(rule))
        assert not misplaced, (
            f"{rule_file.name}:{rule['id']}: {misplaced} sit at rule top level. "
            "Semgrep only honours these as items of a `patterns` list; as a "
            "sibling of `pattern`/`pattern-either` they are silently dropped "
            "and the rule over-matches. `semgrep --validate` will NOT catch "
            "this -- nest them under `patterns`."
        )


# `l9.routing.gateclient-bypass-execute` (AST-ROUTING-004) and the three
# `l9.logging.*` rules (AST-LOGGING-001..003) were `pattern-regex` / whole-text
# regex rules, and each shape produced fleet-wide false positives because a
# regex over raw text cannot tell code from prose:
#
#   * AST-ROUTING-004 fired first on every prose mention of the execute path,
#     then -- once narrowed to a literal ending at the path -- on a node's own
#     INGRESS: its route decorator and the constant it compares the inbound
#     request path against (Cognitive.Engine.Graphs PR #409).
#   * AST-LOGGING-001 bound string literals as $SECRET, so a message that
#     merely names "token" or "API key" fired with no value logged (same PR).
#
# They are now structural rules (AST-ROUTING-004 is a taint rule over outbound
# client calls). Their behaviour is pinned by the annotated Semgrep fixtures in
# tests/fixtures/semgrep/rules/python/, run by
# tests/rulesets/test_semgrep_rule_fixtures.py. The guards below need no
# semgrep binary: they fail if any of these rules is turned back into a text
# search, which is the regression that produced the false positives.
#
# (This comment deliberately avoids quoting execute-path literals: the SDK's
# own self-CI scans this file.)
STRUCTURAL_RULE_IDS = (
    "l9.routing.gateclient-bypass-execute",
    "l9.logging.forbidden-secret-field",
    "l9.logging.forbidden-secret-keyword",
    "l9.logging.f-string-secret",
)


def _packaged_rule(rule_id: str) -> Mapping[str, Any]:
    for rule_file in _rule_files():
        for rule in _load_rules(rule_file):
            if rule["id"] == rule_id:
                return rule
    raise AssertionError(f"{rule_id} not found in the packaged ruleset")


def _contains_key(node: object, key: str) -> bool:
    if isinstance(node, Mapping):
        return key in node or any(_contains_key(v, key) for v in node.values())
    if isinstance(node, list):
        return any(_contains_key(item, key) for item in node)
    return False


@pytest.mark.parametrize("rule_id", STRUCTURAL_RULE_IDS)
def test_precision_rules_are_not_text_searches(rule_id: str) -> None:
    rule = _packaged_rule(rule_id)
    assert not _contains_key(rule, "pattern-regex"), (
        f"{rule_id} uses pattern-regex again. A text search cannot tell a call "
        "from prose or an ingress from a dispatch; keep it structural and pin "
        "new cases in tests/fixtures/semgrep/rules/python/."
    )


def test_gateclient_rule_is_an_outbound_taint_rule() -> None:
    rule = _packaged_rule("l9.routing.gateclient-bypass-execute")
    assert rule.get("mode") == "taint", (
        "AST-ROUTING-004 must track an execute target INTO an outbound client "
        "call; a search rule flags the node's own ingress constant and route."
    )
    assert rule.get("pattern-sources") and rule.get("pattern-sinks")


@pytest.mark.parametrize(
    "rule_id",
    [
        "l9.logging.forbidden-secret-field",
        "l9.logging.f-string-secret",
    ],
)
def test_secret_value_rules_search_inside_the_argument(rule_id: str) -> None:
    """The secret-like name must be matched in a code position INSIDE the
    argument (metavariable-pattern), not as a regex over the argument's whole
    text -- which is what let message prose bind $SECRET."""
    rule = _packaged_rule(rule_id)
    patterns = rule.get("patterns")
    assert isinstance(patterns, list)
    secret_regexes = [
        item["metavariable-regex"]
        for item in patterns
        if isinstance(item, Mapping)
        and "metavariable-regex" in item
        and item["metavariable-regex"].get("metavariable") == "$SECRET"
    ]
    assert not secret_regexes, (
        f"{rule_id}: a metavariable-regex on $SECRET matches string-literal "
        "prose; constrain $SECRET with metavariable-pattern instead"
    )
    assert any(
        isinstance(item, Mapping)
        and item.get("metavariable-pattern", {}).get("metavariable") == "$SECRET"
        for item in patterns
    )
