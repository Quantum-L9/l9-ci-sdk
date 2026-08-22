"""Parity checks between the repo-local Semgrep artifacts and the packaged
copies every downstream consumer receives via ``l9_ci.rulesets.semgrep``.

``.l9/semgrep-identity-map.yaml`` is the human-reviewed source of truth for
this repo's own CI; ``l9_ci/rulesets/semgrep/identity-map.yaml`` is the
mirror shipped as SDK package data. They must stay byte-identical, and the
mirror must always be a schema-valid, loadable identity map.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from l9_ci.identity.resolver import (
    IdentityResolutionStatus,
    RuleIdentityMap,
    resolve_rule_identity,
)
from l9_ci.rulesets.semgrep import (
    PROFILES_SCHEMA,
    SUPPORTED_LANGUAGES,
    default_identity_map_path,
    default_profile_name,
    profile_names,
    profiles_path,
    resolve_profile,
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


def test_tainted_subprocess_argv_rule_resolves_explicitly() -> None:
    """Regression: the rule that broke l9-cognitive-runtime's release gate.

    `release-staging` run 32545475954 (l9-cognitive-runtime@45d87e9) died with
    `unresolved_strict_contract` because this third-party `p/python` registry
    rule carried no `metadata.l9.canonical_rule_id` and had no entry here, so
    `resolve_rule_identity()` returned UNRESOLVED and `--strict` exited 6.

    The canonical ID must stay L9-PYTHON-SUBPROCESS-TAINTED-ARGS and must NOT
    collapse into L9-PYTHON-SUBPROCESS-SHELL-TRUE: this rule fires on tainted
    argv passed to a list-form subprocess call where no shell interprets the
    command, which is a different mechanism from `shell=True`.
    """
    provider_rule_id = (
        "python.lang.security.audit.dangerous-subprocess-use-tainted-env-args"
        ".dangerous-subprocess-use-tainted-env-args"
    )
    identity_map = RuleIdentityMap.load(default_identity_map_path())

    resolution = resolve_rule_identity(
        provider_id="semgrep",
        provider_rule_id=provider_rule_id,
        trusted_canonical_rule_id=None,
        identity_map=identity_map,
    )

    assert resolution.status is IdentityResolutionStatus.EXPLICIT_MAPPING
    assert resolution.canonical_rule_id == "L9-PYTHON-SUBPROCESS-TAINTED-ARGS"
    assert resolution.resolved


def test_every_supported_language_has_a_nonempty_ruleset_dir() -> None:
    for language in SUPPORTED_LANGUAGES:
        rule_files = sorted(ruleset_dir(language).glob("*.yml"))
        assert rule_files, f"expected at least one packaged rule file for {language!r}"


def test_packaged_profile_registry_is_schema_valid_and_default_resolves() -> None:
    """The profile registry must be present, carry the pinned schema, and name
    a default profile that resolves -- a broken default fails run() closed."""
    document = yaml.safe_load(profiles_path().read_text(encoding="utf-8"))
    assert document["schema"] == PROFILES_SCHEMA
    assert document["metadata"]["provider_id"] == "semgrep"
    assert isinstance(document["metadata"]["version"], str)
    assert document["metadata"]["version"].strip()

    names = profile_names()
    assert names, "profile registry must define at least one profile"
    assert names == tuple(sorted(names)), "profile_names() must be deterministic"

    default_profile = resolve_profile(default_profile_name())
    assert default_profile.name in names
    assert default_profile.include_registry_ruleset is True
    assert default_profile.include_l9_ruleset is True, (
        "the default profile must include the packaged L9 ruleset so every "
        "consumer inherits the L9 baseline rules by default"
    )


def test_profile_registry_provider_matches_identity_map_provider() -> None:
    """Profile registry <-> identity-map parity: both are Semgrep artifacts and
    must agree on the provider they describe."""
    document = yaml.safe_load(profiles_path().read_text(encoding="utf-8"))
    identity_map = RuleIdentityMap.load(default_identity_map_path())
    assert document["metadata"]["provider_id"] == identity_map.provider_id == "semgrep"


def test_every_profile_including_l9_ruleset_resolves_authored_rules() -> None:
    """Profile registry <-> authored rules parity: any profile that claims to
    include the L9 ruleset must resolve, for every supported language, to a
    ruleset directory that actually contains authored rule files."""
    for name in profile_names():
        profile = resolve_profile(name)
        if not profile.include_l9_ruleset:
            continue
        for language in SUPPORTED_LANGUAGES:
            rule_files = sorted(ruleset_dir(language).glob("*.yml"))
            assert rule_files, (
                f"profile {name!r} includes the L9 ruleset but {language!r} has "
                "no authored rule files"
            )


def test_unknown_profile_fails_closed() -> None:
    with pytest.raises(ValueError):
        resolve_profile("definitely-not-a-real-profile")
