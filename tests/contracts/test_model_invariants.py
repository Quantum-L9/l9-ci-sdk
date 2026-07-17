import pytest
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    Finding,
    FindingClassification,
    ResolutionStatus,
    RuleMode,
    SourceLocation,
)


def test_source_location_rejects_absolute_path() -> None:
    with pytest.raises(ValueError):
        SourceLocation("/tmp/example.py")


def test_source_location_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        SourceLocation("../example.py")


def test_source_location_normalizes_windows_separator() -> None:
    location = SourceLocation("package\\module.py", start_line=2)
    assert location.normalized_path == "package/module.py"


def test_finding_requires_evidence() -> None:
    with pytest.raises(ValueError):
        Finding(
            finding_id="finding-1",
            snapshot_id="snapshot-1",
            provider_id="example",
            provider_rule_id="RULE-1",
            category="security",
            message="Example",
            evidence_ids=(),
            locations=(),
            fingerprint="fingerprint-1",
        )


def test_coverage_rejects_more_analyzed_than_considered() -> None:
    with pytest.raises(ValueError):
        Coverage(
            provider_id="example",
            status=CoverageStatus.COMPLETE,
            files_considered=1,
            files_analyzed=2,
            limitations=(),
        )


def test_explicit_classification_requires_policy_key() -> None:
    with pytest.raises(ValueError):
        FindingClassification(
            finding_id="finding-1",
            mode=RuleMode.BLOCKING,
            resolution_status=ResolutionStatus.EXPLICIT,
            used_default=False,
        )


def test_unresolved_mode_requires_unresolved_status() -> None:
    with pytest.raises(ValueError):
        FindingClassification(
            finding_id="finding-1",
            mode=RuleMode.UNRESOLVED,
            resolution_status=ResolutionStatus.DEFAULTED,
            used_default=True,
        )
