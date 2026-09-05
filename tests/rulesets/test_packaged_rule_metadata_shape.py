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

import re
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


# `l9.routing.gateclient-bypass-execute` is a `pattern-regex` rule, so it
# searches raw file text with no syntactic context. It was authored as a bare
# `/v1/execute|/execute`, which fired on every mention of the path anywhere in
# a file -- a filename ending in execute.md, CLI help text about skipping a
# paste step, an error string naming execute_via frontmatter, and docstrings
# that merely describe the Gate-routed endpoint. All of them are prose, none is
# a raw call, and the rule's own message is about raw calls bypassing
# GateClient, so every fleet occurrence was a false positive.
#
# (This comment deliberately avoids spelling those examples as quoted literals:
# a pattern-regex rule cannot tell a comment from code, so writing them out
# would make this very block a finding. The exact strings live in
# GATECLIENT_MUST_NOT_MATCH below, which is what the assertions read.)
#
# It now requires a string literal that ENDS at the path. These cases pin that
# boundary so a future edit cannot quietly widen it back to a text search.
GATECLIENT_RULE_ID = "l9.routing.gateclient-bypass-execute"
# These four are the rule's own positive fixtures, so the routing rules match
# them exactly as intended -- that is what the tests below assert. Suppressed by
# id rather than reworded, because the strings have to stay byte-for-byte what
# the rule is supposed to catch.
GATECLIENT_MUST_MATCH = (
    'requests.post("http://node:8000/v1/execute", json={})',  # nosemgrep: l9.routing.gateclient-bypass-execute,l9.routing.hardcoded-peer-node-url
    'EXECUTE_PATH = "/v1/execute"',  # nosemgrep: l9.routing.gateclient-bypass-execute
    'url = f"{base}/execute"',  # nosemgrep: l9.routing.gateclient-bypass-execute
    "PATH = '/execute'",  # nosemgrep: l9.routing.gateclient-bypass-execute
)
GATECLIENT_MUST_NOT_MATCH = (
    'FILES = ("references/execute.md",)',
    'help_text = "Skip paste/execute; only copy lower Results grid"',
    'err = "cursor-build render missing kind/execute_via frontmatter"',
    '"""The converge action EIE owns (POST /v1/execute) validates the rows."""',
    "# Route follow-up work through the Gate rather than POST /v1/execute.",
)


def _gateclient_pattern() -> str:
    for rule_file in _rule_files():
        for rule in _load_rules(rule_file):
            if rule["id"] == GATECLIENT_RULE_ID:
                pattern = rule.get("pattern-regex")
                assert isinstance(pattern, str), (
                    f"{GATECLIENT_RULE_ID} must keep a pattern-regex; if it is "
                    "rewritten as an AST rule, port these cases to the new form"
                )
                return pattern
    raise AssertionError(f"{GATECLIENT_RULE_ID} not found in the packaged ruleset")


@pytest.mark.parametrize("source", GATECLIENT_MUST_MATCH)
def test_gateclient_rule_still_catches_raw_execute_paths(source: str) -> None:
    assert re.search(_gateclient_pattern(), source), (
        f"{GATECLIENT_RULE_ID} no longer flags a raw /execute path: {source!r}"
    )


@pytest.mark.parametrize("source", GATECLIENT_MUST_NOT_MATCH)
def test_gateclient_rule_ignores_prose_mentions_of_execute(source: str) -> None:
    assert not re.search(_gateclient_pattern(), source), (
        f"{GATECLIENT_RULE_ID} fires on prose, not a call: {source!r}. The "
        "literal must end at the /execute path."
    )
