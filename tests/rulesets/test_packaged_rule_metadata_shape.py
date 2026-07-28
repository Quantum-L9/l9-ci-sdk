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
