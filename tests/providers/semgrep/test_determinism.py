import json
from pathlib import Path
from l9_ci.artifacts import bundle_bytes
from l9_ci.contracts import (
    FindingBundle,
    ProviderRun,
    SnapshotDescriptor,
)
from l9_ci.providers import ProviderNormalizationContext
from l9_ci.providers.semgrep import SemgrepProvider

FIXTURE = Path("tests/fixtures/semgrep/results.json")


def build_bundle() -> FindingBundle:
    provider = SemgrepProvider()
    report = json.loads(FIXTURE.read_text(encoding="utf-8"))
    normalized = provider.normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=Path(".").resolve(),
            provider_version="fixture-version",
            required=False,
        ),
    )
    return FindingBundle(
        SDK_version="2.0.0-test",
        generated_at="2026-07-17T00:00:00Z",
        snapshot=SnapshotDescriptor(
            snapshot_id="snapshot-1",
            repository_root=".",
        ),
        providers=(
            ProviderRun(
                provider_id="semgrep",
                adapter_version=provider.metadata.adapter_version,
                provider_version="fixture-version",
                mode="import",
                required=False,
            ),
        ),
        evidence=normalized.evidence,
        findings=normalized.findings,
        classifications=(),
        provider_failures=normalized.failures,
        coverage=(normalized.coverage,),
        limitations=normalized.limitations,
    )


def test_semgrep_bundle_is_byte_deterministic() -> None:
    first = bundle_bytes(build_bundle())
    second = bundle_bytes(build_bundle())
    assert first == second


def test_identifiers_are_stable() -> None:
    first = build_bundle()
    second = build_bundle()
    assert tuple(item.evidence_id for item in first.evidence) == tuple(
        item.evidence_id for item in second.evidence
    )
    assert tuple(item.finding_id for item in first.findings) == tuple(
        item.finding_id for item in second.findings
    )
