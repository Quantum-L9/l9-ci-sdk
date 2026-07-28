import pytest
from l9_ci.contracts import (
    Finding,
    RuleMode,
    SourceLocation,
)
from l9_ci.policy import (
    FindingPolicy,
    PolicyRule,
    classify_findings,
)


def finding() -> Finding:
    return Finding(
        finding_id="finding-1",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="rule.one",
        category="security",
        message="Example",
        evidence_ids=("evidence-1",),
        locations=(SourceLocation("example.py", start_line=1),),
        fingerprint="fingerprint-1",
    )


def test_explicit_policy_classifies_finding() -> None:
    policy = FindingPolicy(
        version="1.0.0",
        default_mode=RuleMode.UNRESOLVED,
        rules={
            "rule.one": PolicyRule(
                provider_rule_id="rule.one",
                policy_key="L9-RULE-ONE",
                mode=RuleMode.BLOCKING,
            ),
        },
    )
    result = classify_findings(
        (finding(),),
        policy,
        strict=True,
    )
    classification = result.classifications[0]
    assert classification.mode is RuleMode.BLOCKING
    assert classification.policy_key == "L9-RULE-ONE"
    assert not classification.used_default


def test_missing_policy_stays_unresolved() -> None:
    policy = FindingPolicy(
        version="1.0.0",
        default_mode=RuleMode.UNRESOLVED,
        rules={},
    )
    result = classify_findings(
        (finding(),),
        policy,
        strict=False,
    )
    assert result.classifications[0].mode is RuleMode.UNRESOLVED
    assert result.unresolved_finding_ids == ("finding-1",)


def test_strict_mode_rejects_unresolved_policy() -> None:
    policy = FindingPolicy(
        version="1.0.0",
        default_mode=RuleMode.UNRESOLVED,
        rules={},
    )
    with pytest.raises(ValueError, match="unresolved"):
        classify_findings(
            (finding(),),
            policy,
            strict=True,
        )
