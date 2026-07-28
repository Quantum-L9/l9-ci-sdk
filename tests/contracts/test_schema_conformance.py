from l9_ci.artifacts import validate_bundle
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    FindingBundle,
    ProviderRun,
    SnapshotDescriptor,
)


def test_minimal_bundle_conforms() -> None:
    bundle = FindingBundle(
        SDK_version="1.0.0",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor(
            snapshot_id="snapshot-1",
            repository_root=".",
        ),
        providers=(
            ProviderRun(
                provider_id="example",
                adapter_version="1.0.0",
                provider_version=None,
                mode="import",
                required=False,
            ),
        ),
        evidence=(),
        findings=(),
        classifications=(),
        provider_failures=(),
        coverage=(
            Coverage(
                provider_id="example",
                status=CoverageStatus.SKIPPED,
                files_considered=0,
                files_analyzed=0,
                limitations=("No provider implementation in Phase 1.",),
            ),
        ),
        limitations=("Phase 1 contract bundle.",),
    )
    result = validate_bundle(bundle)
    assert result.valid, result.errors
