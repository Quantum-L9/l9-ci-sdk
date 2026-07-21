from typing import Any
from pathlib import Path
import pytest
from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.pipeline import (
    SemgrepPipelineRequest,
    run_semgrep_pipeline,
)

FIXTURE = Path("tests/fixtures/semgrep/results.json")


def write_identity_map(path: Path) -> None:
    path.write_text(
        """
schema: l9.identity-map/v1
metadata:
  provider_id: semgrep
  version: 1.0.0
rules:
  python.lang.security.audit.exec-used.exec-used:
    canonical_rule_id: L9-PYTHON-EXEC-USED
  python.lang.correctness.useless-comparison.useless-comparison:
    canonical_rule_id: L9-PYTHON-USELESS-COMPARISON
""".strip()
        + "\n",
        encoding="utf-8",
    )


def write_policy(path: Path) -> None:
    path.write_text(
        """
schema: l9.finding-policy/v1
metadata:
  version: 1.0.0
defaults:
  mode: unresolved
rules:
  python.lang.security.audit.exec-used.exec-used:
    policy_key: L9-PYTHON-EXEC-USED
    mode: blocking
  python.lang.correctness.useless-comparison.useless-comparison:
    policy_key: L9-PYTHON-USELESS-COMPARISON
    mode: advisory
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_pipeline_emits_valid_bundle(tmp_path: Path) -> None:
    identity_map = tmp_path / "identity.yaml"
    policy = tmp_path / "policy.yaml"
    output = tmp_path / "bundle.json"
    write_identity_map(identity_map)
    write_policy(policy)
    result = run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=FIXTURE,
            repository_root=Path(".").resolve(),
            snapshot_id="snapshot-1",
            SDK_version="2.0.0-test",
            output_path=output,
            provider_version="1.100.0",
            identity_map_path=identity_map,
            policy_path=policy,
            strict=True,
            required=True,
            generated_at="2026-07-17T00:00:00Z",
        )
    )
    assert result.output_path == output
    assert output.exists()
    bundle = load_and_validate_bundle(output)
    assert len(bundle.evidence) == 2
    assert len(bundle.findings) == 2
    assert len(bundle.classifications) == 2
    assert bundle.provider_failures == ()


def test_strict_pipeline_rejects_empty_identity_map(
    tmp_path: Path,
) -> None:
    identity_map = tmp_path / "identity.yaml"
    policy = tmp_path / "policy.yaml"
    identity_map.write_text(
        """
schema: l9.identity-map/v1
metadata:
  provider_id: semgrep
  version: 1.0.0
rules: {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    write_policy(policy)
    with pytest.raises(ValueError, match="strict identity"):
        run_semgrep_pipeline(
            SemgrepPipelineRequest(
                report_path=FIXTURE,
                repository_root=Path(".").resolve(),
                snapshot_id="snapshot-1",
                SDK_version="2.0.0-test",
                output_path=tmp_path / "bundle.json",
                identity_map_path=identity_map,
                policy_path=policy,
                strict=True,
                generated_at="2026-07-17T00:00:00Z",
            )
        )


def test_pipeline_output_is_reproducible(tmp_path: Path) -> None:
    identity_map = tmp_path / "identity.yaml"
    policy = tmp_path / "policy.yaml"
    write_identity_map(identity_map)
    write_policy(policy)
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    common: dict[str, Any] = {
        "report_path": FIXTURE,
        "repository_root": Path(".").resolve(),
        "snapshot_id": "snapshot-1",
        "SDK_version": "2.0.0-test",
        "provider_version": "1.100.0",
        "identity_map_path": identity_map,
        "policy_path": policy,
        "strict": True,
        "generated_at": "2026-07-17T00:00:00Z",
    }
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            **common,
            output_path=first_path,
        )
    )
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            **common,
            output_path=second_path,
        )
    )
    assert first_path.read_bytes() == second_path.read_bytes()


def test_pipeline_content_identity_is_clock_independent(tmp_path: Path) -> None:
    # QA-003: exercise the production pipeline across a simulated clock boundary
    # (two different generated_at values). The canonical content digest must be
    # identical, proving reproducibility does not depend on wall-clock time,
    # even though the raw bundle bytes differ by the timestamp field.
    identity_map = tmp_path / "identity.yaml"
    policy = tmp_path / "policy.yaml"
    write_identity_map(identity_map)
    write_policy(policy)
    common: dict[str, Any] = {
        "report_path": FIXTURE,
        "repository_root": Path(".").resolve(),
        "snapshot_id": "snapshot-1",
        "SDK_version": "2.0.0-test",
        "provider_version": "1.100.0",
        "identity_map_path": identity_map,
        "policy_path": policy,
        "strict": True,
    }
    early = run_semgrep_pipeline(
        SemgrepPipelineRequest(
            **common,
            output_path=tmp_path / "early.json",
            generated_at="2026-07-17T00:00:00Z",
        )
    )
    late = run_semgrep_pipeline(
        SemgrepPipelineRequest(
            **common,
            output_path=tmp_path / "late.json",
            generated_at="2027-01-01T12:34:56Z",
        )
    )
    assert early.bundle.canonical_digest() == late.bundle.canonical_digest()
    assert (tmp_path / "early.json").read_bytes() != (
        tmp_path / "late.json"
    ).read_bytes()
