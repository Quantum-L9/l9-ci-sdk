"""Trusted remediation-class producer tests (DWA-007).

Proves the mechanism: a trusted canonical-rule -> remediation-class map assigns
remediation_class (only after canonical identity resolution), so the projection
can emit autofix candidates that were previously always empty. The SDK ships no
built-in classifications, so these tests supply their own map data.
"""

from __future__ import annotations
from pathlib import Path
import pytest
from l9_ci.contracts import Finding
from l9_ci.policy.remediation import (
    ALLOWED_REMEDIATION_CLASSES,
    RemediationMap,
    apply_remediation_classes,
)


def _finding(finding_id: str, canonical_rule_id: str | None) -> Finding:
    return Finding(
        finding_id=finding_id,
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="native.rule",
        category="security",
        message="issue",
        evidence_ids=(f"{finding_id}-e1",),
        locations=(),
        fingerprint=f"{finding_id}-fp",
        canonical_rule_id=canonical_rule_id,
    )


def test_maps_canonical_rule_to_remediation_class() -> None:
    finding = _finding("f1", "L9-X")
    remediation_map = RemediationMap(version="1", mappings={"L9-X": "safe-autofix"})
    (out,) = apply_remediation_classes((finding,), remediation_map)
    assert out.remediation_class == "safe-autofix"


def test_unmapped_and_unresolved_findings_unchanged() -> None:
    mapped_absent = _finding("f1", "L9-Y")
    unresolved = _finding("f2", None)
    remediation_map = RemediationMap(version="1", mappings={"L9-X": "safe-autofix"})
    out = apply_remediation_classes((mapped_absent, unresolved), remediation_map)
    assert all(finding.remediation_class is None for finding in out)


def test_empty_map_is_noop() -> None:
    finding = _finding("f1", "L9-X")
    (out,) = apply_remediation_classes((finding,), RemediationMap.empty())
    assert out.remediation_class is None


def test_rejects_class_outside_allowed_set() -> None:
    assert ALLOWED_REMEDIATION_CLASSES == frozenset({"safe-autofix", "mechanical"})
    with pytest.raises(ValueError, match="outside"):
        RemediationMap(version="1", mappings={"L9-X": "please-just-fix-it"})


def test_load_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "map.yaml"
    path.write_text(
        "metadata:\n  version: '2'\n"
        "rules:\n  L9-X:\n    remediation_class: mechanical\n",
        encoding="utf-8",
    )
    remediation_map = RemediationMap.load(path)
    assert remediation_map.version == "2"
    assert remediation_map.remediation_for("L9-X") == "mechanical"
    assert remediation_map.remediation_for("L9-UNKNOWN") is None


def test_example_map_file_is_valid_and_empty() -> None:
    # The shipped example must load and carry no built-in classifications.
    remediation_map = RemediationMap.load(
        Path(".l9/semgrep-remediation-map.example.yaml")
    )
    assert dict(remediation_map.mappings) == {}


def test_pipeline_populates_remediation_class_end_to_end(tmp_path: Path) -> None:
    from l9_ci.artifacts import load_and_validate_bundle
    from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline

    identity = tmp_path / "identity.yaml"
    identity.write_text(
        "schema: l9.identity-map/v1\n"
        "metadata:\n  provider_id: semgrep\n  version: 1.0.0\n"
        "rules:\n"
        "  python.lang.security.audit.exec-used.exec-used:\n"
        "    canonical_rule_id: L9-PYTHON-EXEC-USED\n"
        "  python.lang.correctness.useless-comparison.useless-comparison:\n"
        "    canonical_rule_id: L9-PYTHON-USELESS-COMPARISON\n",
        encoding="utf-8",
    )
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "schema: l9.finding-policy/v1\n"
        "metadata:\n  version: 1.0.0\n"
        "defaults:\n  mode: unresolved\n"
        "rules:\n"
        "  python.lang.security.audit.exec-used.exec-used:\n"
        "    policy_key: L9-PYTHON-EXEC-USED\n    mode: blocking\n"
        "  python.lang.correctness.useless-comparison.useless-comparison:\n"
        "    policy_key: L9-PYTHON-USELESS-COMPARISON\n    mode: advisory\n",
        encoding="utf-8",
    )
    remediation = tmp_path / "remediation.yaml"
    remediation.write_text(
        "metadata:\n  version: '1'\n"
        "rules:\n  L9-PYTHON-EXEC-USED:\n    remediation_class: safe-autofix\n",
        encoding="utf-8",
    )
    output = tmp_path / "bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=Path("tests/fixtures/semgrep/results.json"),
            repository_root=Path(".").resolve(),
            snapshot_id="snapshot-1",
            SDK_version="1.0.0",
            output_path=output,
            provider_version="1.100.0",
            identity_map_path=identity,
            policy_path=policy,
            strict=True,
            required=True,
            generated_at="2026-07-17T00:00:00Z",
            remediation_map_path=remediation,
        )
    )
    bundle = load_and_validate_bundle(output)
    by_rule = {f.canonical_rule_id: f for f in bundle.findings}
    assert by_rule["L9-PYTHON-EXEC-USED"].remediation_class == "safe-autofix"
    # An unmapped canonical rule is left untouched.
    assert by_rule["L9-PYTHON-USELESS-COMPARISON"].remediation_class is None
