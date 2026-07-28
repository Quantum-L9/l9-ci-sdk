from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    FindingBundle,
    ProviderRun,
    SnapshotDescriptor,
)
from l9_ci.gates import GateStatus, evaluate_gate


def bundle(status=CoverageStatus.COMPLETE):
    return FindingBundle(
        SDK_version="1.0.0",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor("snapshot-1", "."),
        providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", True),),
        evidence=(),
        findings=(),
        classifications=(),
        provider_failures=(),
        coverage=(
            Coverage(
                "semgrep", status, 1, 1 if status is CoverageStatus.COMPLETE else 0, ()
            ),
        ),
    )


def test_complete_empty_bundle_passes():
    assert evaluate_gate(bundle()).status is GateStatus.PASS


def test_required_partial_coverage_is_incomplete():
    assert evaluate_gate(bundle(CoverageStatus.PARTIAL)).status is GateStatus.INCOMPLETE
