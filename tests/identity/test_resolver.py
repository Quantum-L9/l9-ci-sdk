from l9_ci.identity import (
    IdentityResolutionStatus,
    RuleIdentityMap,
    resolve_rule_identity,
)


def test_unmapped_identity_stays_unresolved() -> None:
    result = resolve_rule_identity(
        provider_id="semgrep",
        provider_rule_id="rule.one",
        trusted_canonical_rule_id=None,
        identity_map=None,
    )
    assert result.canonical_rule_id is None
    assert result.status is IdentityResolutionStatus.UNRESOLVED


def test_explicit_mapping_resolves_identity() -> None:
    identity_map = RuleIdentityMap(
        provider_id="semgrep",
        version="1.0.0",
        rules={
            "rule.one": "L9-RULE-ONE",
        },
    )
    result = resolve_rule_identity(
        provider_id="semgrep",
        provider_rule_id="rule.one",
        trusted_canonical_rule_id=None,
        identity_map=identity_map,
    )
    assert result.canonical_rule_id == "L9-RULE-ONE"
    assert result.status is IdentityResolutionStatus.EXPLICIT_MAPPING


def test_trusted_metadata_has_priority() -> None:
    identity_map = RuleIdentityMap(
        provider_id="semgrep",
        version="1.0.0",
        rules={
            "rule.one": "L9-MAPPED",
        },
    )
    result = resolve_rule_identity(
        provider_id="semgrep",
        provider_rule_id="rule.one",
        trusted_canonical_rule_id="L9-TRUSTED",
        identity_map=identity_map,
    )
    assert result.canonical_rule_id == "L9-TRUSTED"
    assert result.status is IdentityResolutionStatus.TRUSTED_METADATA
