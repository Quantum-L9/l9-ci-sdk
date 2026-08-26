from __future__ import annotations

import json
import sys

import pytest

import l9_ci.__main__ as main_module
from l9_ci.artifacts import bundle_bytes
from l9_ci.contracts import (
    Confidence,
    Coverage,
    CoverageStatus,
    EvidenceRecord,
    Finding,
    FindingBundle,
    FindingClassification,
    ProviderRun,
    ResolutionStatus,
    RuleMode,
    Severity,
    SnapshotDescriptor,
    SourceLocation,
)

REVISION = "a" * 40
DIGEST = "b" * 64


def run_cli(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sys, "argv", ["l9-ci", *argv])
    return main_module.main()


def test_observation_build_cli(monkeypatch, tmp_path) -> None:
    output = tmp_path / "tests-observation.json"
    code = run_cli(
        [
            "observation",
            "build",
            "--repository",
            "Quantum-L9/example",
            "--revision",
            REVISION,
            "--check-id",
            "l9.tests",
            "--configuration-digest",
            DIGEST,
            "--run-id",
            "12345",
            "--attempt",
            "1",
            "--status",
            "passed",
            "--started-at",
            "2026-08-21T20:00:00Z",
            "--completed-at",
            "2026-08-21T20:00:01Z",
            "--output",
            str(output),
        ],
        monkeypatch,
    )
    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["producer"]["id"] == "l9-ci-sdk"
    assert payload["producer"]["version"] == "2.0.0"
    assert payload["check"]["id"] == "l9.tests"
    assert payload["subject"]["revision"]["commit"] == REVISION


def test_observation_build_rejects_unknown_check(monkeypatch, tmp_path) -> None:
    output = tmp_path / "bad.json"
    code = run_cli(
        [
            "observation",
            "build",
            "--repository",
            "Quantum-L9/example",
            "--revision",
            REVISION,
            "--check-id",
            "repo.custom",
            "--configuration-digest",
            DIGEST,
            "--run-id",
            "12345",
            "--attempt",
            "1",
            "--status",
            "passed",
            "--started-at",
            "2026-08-21T20:00:00Z",
            "--completed-at",
            "2026-08-21T20:00:01Z",
            "--output",
            str(output),
        ],
        monkeypatch,
    )
    assert code != 0
    assert not output.exists()


def _bundle() -> FindingBundle:
    location = SourceLocation("src/example.py", start_line=7)
    evidence = EvidenceRecord(
        evidence_id="ev-1",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="python.example",
        evidence_type="static-analysis",
        message="example evidence",
        locations=(location,),
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
    )
    finding = Finding(
        finding_id="finding-1",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="python.example",
        canonical_rule_id="l9.example.rule",
        category="security",
        message="example finding",
        evidence_ids=("ev-1",),
        locations=(location,),
        fingerprint="fingerprint-1",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
    )
    classification = FindingClassification(
        finding_id="finding-1",
        mode=RuleMode.BLOCKING,
        resolution_status=ResolutionStatus.DEFAULTED,
        used_default=True,
    )
    return FindingBundle(
        SDK_version="2.0.0",
        generated_at="2026-08-21T20:00:00Z",
        snapshot=SnapshotDescriptor(
            snapshot_id="snapshot-1",
            repository_root=".",
            revision=REVISION,
            dirty=False,
        ),
        # The CLI path runs the full artifact validator, which rejects evidence
        # and findings whose provider_id is not a registered provider run.
        providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", True),),
        evidence=(evidence,),
        findings=(finding,),
        classifications=(classification,),
        provider_failures=(),
        coverage=(Coverage("semgrep", CoverageStatus.COMPLETE, 1, 1, ()),),
    )


def test_project_mandatory_findings_accepts_absolute_cli_input(
    monkeypatch, tmp_path
) -> None:
    bundle_path = tmp_path / "finding-bundle.json"
    bundle_path.write_bytes(bundle_bytes(_bundle()))
    output = tmp_path / "mandatory-findings-observation.json"

    code = run_cli(
        [
            "observation",
            "project-mandatory-findings",
            "--input",
            str(bundle_path),
            "--repository",
            "Quantum-L9/example",
            "--configuration-digest",
            DIGEST,
            "--run-id",
            "12345",
            "--attempt",
            "1",
            "--started-at",
            "2026-08-21T20:00:00Z",
            "--completed-at",
            "2026-08-21T20:00:01Z",
            "--output",
            str(output),
        ],
        monkeypatch,
    )

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["check"]["id"] == "l9.mandatory-findings"
    assert payload["subject"]["revision"]["commit"] == REVISION
    assert payload["artifacts"][0].get("path") is None
