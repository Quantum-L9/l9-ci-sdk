from pathlib import Path
from l9_ci.artifacts import (
    canonical_json_bytes,
    load_and_validate_bundle,
)
from l9_ci.integration import (
    project_agent_review_payload,
    validate_redaction,
)
from l9_ci.pipeline import (
    SemgrepPipelineRequest,
    run_semgrep_pipeline,
)


def test_semgrep_to_agent_payload_is_byte_deterministic(
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
rules:
  python.lang.security.audit.exec-used.exec-used:
    canonical_rule_id: L9-PYTHON-EXEC-USED
  python.lang.correctness.useless-comparison.useless-comparison:
    canonical_rule_id: L9-PYTHON-USELESS-COMPARISON
""".strip()
        + "\n",
        encoding="utf-8",
    )
    policy.write_text(
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
    common = {
        "report_path": Path("tests/fixtures/semgrep/results.json"),
        "repository_root": Path(".").resolve(),
        "snapshot_id": "snapshot-release-test",
        "SDK_version": "1.0.0",
        "provider_version": "fixture-version",
        "identity_map_path": identity_map,
        "policy_path": policy,
        "strict": True,
        "required": True,
        "generated_at": "2026-07-17T00:00:00Z",
    }
    first_bundle_path = tmp_path / "first-bundle.json"
    second_bundle_path = tmp_path / "second-bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            **common,
            output_path=first_bundle_path,
        )
    )
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            **common,
            output_path=second_bundle_path,
        )
    )
    assert first_bundle_path.read_bytes() == second_bundle_path.read_bytes()
    first_bundle = load_and_validate_bundle(first_bundle_path)
    second_bundle = load_and_validate_bundle(second_bundle_path)
    first_payload = project_agent_review_payload(
        first_bundle,
        strict=True,
    )
    second_payload = project_agent_review_payload(
        second_bundle,
        strict=True,
    )
    first_bytes = canonical_json_bytes(first_payload.to_dict())
    second_bytes = canonical_json_bytes(second_payload.to_dict())
    assert first_bytes == second_bytes
    validate_redaction(first_bundle.to_dict()).require_valid()
    validate_redaction(first_payload.to_dict()).require_valid()
