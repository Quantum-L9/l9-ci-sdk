"""Parity checks between the repo-local Semgrep artifacts and the packaged
copies every downstream consumer receives via ``l9_ci.rulesets.semgrep``.

``.l9/semgrep-identity-map.yaml`` is the human-reviewed source of truth for
this repo's own CI; ``l9_ci/rulesets/semgrep/identity-map.yaml`` is the
mirror shipped as SDK package data. They must stay byte-identical, and the
mirror must always be a schema-valid, loadable identity map.
"""

from __future__ import annotations

from pathlib import Path

from l9_ci.identity.resolver import RuleIdentityMap
from l9_ci.rulesets.semgrep import (
    SUPPORTED_LANGUAGES,
    default_identity_map_path,
    ruleset_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_IDENTITY_MAP = REPO_ROOT / ".l9" / "semgrep-identity-map.yaml"


def test_packaged_identity_map_matches_repo_source() -> None:
    packaged_path = default_identity_map_path()
    assert packaged_path.read_text(encoding="utf-8") == REPO_IDENTITY_MAP.read_text(
        encoding="utf-8"
    ), (
        "l9_ci/rulesets/semgrep/identity-map.yaml has drifted from "
        ".l9/semgrep-identity-map.yaml; keep the packaged mirror byte-identical "
        "to the reviewed source of truth."
    )


def test_packaged_identity_map_is_schema_valid_and_populated() -> None:
    identity_map = RuleIdentityMap.load(default_identity_map_path())
    assert identity_map.provider_id == "semgrep"
    assert len(identity_map.rules) > 0, (
        "packaged identity map must contain real, verified entries -- an "
        "empty map defeats the purpose of shipping it as SDK data"
    )
    for provider_rule_id, canonical_rule_id in identity_map.rules.items():
        assert provider_rule_id.strip() == provider_rule_id
        assert canonical_rule_id.strip() == canonical_rule_id
        assert canonical_rule_id  # never an empty/synthesized identity


def test_every_supported_language_has_a_nonempty_ruleset_dir() -> None:
    for language in SUPPORTED_LANGUAGES:
        rule_files = sorted(ruleset_dir(language).glob("*.yml"))
        assert rule_files, f"expected at least one packaged rule file for {language!r}"
