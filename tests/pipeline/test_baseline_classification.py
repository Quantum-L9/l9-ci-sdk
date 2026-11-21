"""Unit witnesses for baseline classification (ADR 0023); no Semgrep needed."""

from __future__ import annotations

import json
from importlib.resources import files

import pytest
from jsonschema import Draft202012Validator

from l9_ci.contracts import (
    BaselineStatus,
    Finding,
    FindingClassification,
    ResolutionStatus,
    RuleMode,
    SourceLocation,
)
from l9_ci.pipeline.baseline import apply_baseline

BASE = "a" * 40


def _finding(name: str) -> Finding:
    return Finding(
        finding_id=f"finding-{name}",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="l9.rule",
        category="security",
        message="m",
        evidence_ids=(f"evidence-{name}",),
        locations=(
            SourceLocation(normalized_path=f"src/{name}.py", start_line=1, end_line=1),
        ),
        fingerprint=f"{name:0<64}"[:64],
    )


def _classification(
    name: str, mode: RuleMode, **extra: object
) -> FindingClassification:
    return FindingClassification(
        finding_id=f"finding-{name}",
        mode=mode,
        resolution_status=ResolutionStatus.DEFAULTED,
        used_default=True,
        **extra,  # type: ignore[arg-type]
    )


def test_new_keeps_its_mode_and_pre_existing_blocking_becomes_advisory() -> None:
    findings = [_finding("a"), _finding("b"), _finding("c")]
    classifications = [
        _classification("a", RuleMode.BLOCKING),
        _classification("b", RuleMode.BLOCKING, waiver_id="W-1"),
        _classification("c", RuleMode.SHADOW),
    ]
    result = apply_baseline(
        findings,
        classifications,
        baseline_commit=BASE,
        new_fingerprints=frozenset({findings[0].fingerprint}),
    )
    a, b, c = result.classifications
    assert (a.baseline_status, a.mode) == (BaselineStatus.NEW, RuleMode.BLOCKING)
    # Pre-existing: blocking reported as advisory; the waiver id is kept.
    assert (b.baseline_status, b.mode, b.waiver_id) == (
        BaselineStatus.PRE_EXISTING,
        RuleMode.ADVISORY,
        "W-1",
    )
    # A non-blocking mode is never raised or lowered.
    assert (c.baseline_status, c.mode) == (BaselineStatus.PRE_EXISTING, RuleMode.SHADOW)
    assert (result.new_count, result.pre_existing_count, result.unknown_count) == (
        1,
        2,
        0,
    )
    assert result.limitations == (
        f"baseline {BASE[:12]}: 1 new, 2 pre-existing "
        "(1 blocking reported as advisory), 0 unknown",
    )


def test_an_unresolved_baseline_marks_everything_unknown_and_keeps_modes() -> None:
    findings = [_finding("a")]
    result = apply_baseline(
        findings,
        [_classification("a", RuleMode.BLOCKING)],
        baseline_commit=BASE,
        new_fingerprints=None,
        unresolved_reason="the baseline scan failed",
    )
    (only,) = result.classifications
    assert (only.baseline_status, only.mode) == (
        BaselineStatus.UNKNOWN,
        RuleMode.BLOCKING,
    )
    assert any("the baseline scan failed" in item for item in result.limitations)


@pytest.mark.parametrize("status", list(BaselineStatus))
def test_baseline_status_round_trips_and_validates(status: BaselineStatus) -> None:
    classification = _classification("a", RuleMode.ADVISORY, baseline_status=status)
    payload = classification.to_dict()
    assert payload["baseline_status"] == status.value
    assert FindingClassification.from_dict(payload) == classification
    schema = files("l9_ci").joinpath(
        "schemas", "v1", "finding-classification.schema.json"
    )
    validator = Draft202012Validator(json.loads(schema.read_text(encoding="utf-8")))
    assert sorted(validator.iter_errors(payload), key=str) == []


def test_without_a_baseline_the_field_is_absent() -> None:
    payload = _classification("a", RuleMode.BLOCKING).to_dict()
    assert "baseline_status" not in payload
    assert FindingClassification.from_dict(payload).baseline_status is None
