from l9_ci.artifacts import bundle_bytes
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    EvidenceRecord,
    Finding,
    FindingBundle,
    ProviderRun,
    SnapshotDescriptor,
    SourceLocation,
)


def build_bundle(
    reverse: bool, generated_at: str = "2026-07-17T00:00:00Z"
) -> FindingBundle:
    evidence = [
        EvidenceRecord(
            evidence_id="evidence-b",
            snapshot_id="snapshot-1",
            provider_id="example",
            provider_rule_id="RULE-B",
            evidence_type="issue",
            message="B",
            locations=(SourceLocation("b.py", start_line=2),),
        ),
        EvidenceRecord(
            evidence_id="evidence-a",
            snapshot_id="snapshot-1",
            provider_id="example",
            provider_rule_id="RULE-A",
            evidence_type="issue",
            message="A",
            locations=(SourceLocation("a.py", start_line=1),),
        ),
    ]
    findings = [
        Finding(
            finding_id="finding-b",
            snapshot_id="snapshot-1",
            provider_id="example",
            provider_rule_id="RULE-B",
            category="test",
            message="B",
            evidence_ids=("evidence-b",),
            locations=(SourceLocation("b.py", start_line=2),),
            fingerprint="fingerprint-b",
        ),
        Finding(
            finding_id="finding-a",
            snapshot_id="snapshot-1",
            provider_id="example",
            provider_rule_id="RULE-A",
            category="test",
            message="A",
            evidence_ids=("evidence-a",),
            locations=(SourceLocation("a.py", start_line=1),),
            fingerprint="fingerprint-a",
        ),
    ]
    if reverse:
        evidence.reverse()
        findings.reverse()
    return FindingBundle(
        SDK_version="1.0.0",
        generated_at=generated_at,
        snapshot=SnapshotDescriptor(
            snapshot_id="snapshot-1",
            repository_root=".",
        ),
        providers=(
            ProviderRun(
                provider_id="example",
                adapter_version="1.0.0",
                provider_version="1.0.0",
                mode="import",
                required=True,
            ),
        ),
        evidence=tuple(evidence),
        findings=tuple(findings),
        classifications=(),
        provider_failures=(),
        coverage=(
            Coverage(
                provider_id="example",
                status=CoverageStatus.COMPLETE,
                files_considered=2,
                files_analyzed=2,
                limitations=(),
            ),
        ),
    )


def test_bundle_serialization_is_order_independent() -> None:
    first = bundle_bytes(build_bundle(reverse=False))
    second = bundle_bytes(build_bundle(reverse=True))
    assert first == second


def test_bundle_serialization_ends_with_one_newline() -> None:
    content = bundle_bytes(build_bundle(reverse=False))
    assert content.endswith(b"\n")
    assert not content.endswith(b"\n\n")


def test_generated_at_excluded_from_content_identity() -> None:
    # QA-003: generated_at is invocation provenance, not content. Two bundles
    # that are identical except for their generation time (a simulated clock
    # boundary) must share a canonical content digest, even though their raw
    # serialized bytes legitimately differ by the timestamp. Previously the
    # determinism tests only ever pinned generated_at, so this entropy was
    # never exercised.
    early = build_bundle(reverse=False, generated_at="2026-07-17T00:00:00Z")
    late = build_bundle(reverse=True, generated_at="2027-01-01T12:34:56Z")
    assert early.canonical_digest() == late.canonical_digest()
    assert bundle_bytes(early) != bundle_bytes(late)
