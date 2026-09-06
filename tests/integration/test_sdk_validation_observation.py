"""`l9.sdk-validation` must observe validation, not be told about it.

`L9.CI.SDK_VALIDATION` is one of the five controls in the pull-request
assurance profile that had no producer at all, so Assurance returned
CONTROL_CARDINALITY_VIOLATION for it on every evaluation. The gap was not that
the SDK could not emit the check id -- `build_observation` has always accepted
it -- but that the generic builder takes the verdict from its caller. Wiring
that up would have satisfied cardinality with a value nobody checked, which is
worse than the honest indeterminate it replaced.

So the thing under test here is mostly a negative: that there is no way to
assert a pass. The projector runs `l9-ci bundle validate`'s two halves itself
and reports what they did.
"""

from __future__ import annotations

import json
import inspect
from pathlib import Path

import pytest

from l9_ci.contracts import (
    Confidence,
    Coverage,
    CoverageStatus,
    EvidenceRecord,
    Finding,
    FindingBundle,
    ProviderRun,
    Severity,
    SnapshotDescriptor,
    SourceLocation,
)
from l9_ci.commands.observations import project_sdk_validation_observation
from l9_ci.integration import validate_observation

REVISION = "a" * 40
OTHER_REVISION = "b" * 40
DIGEST = "c" * 64
STARTED = "2026-09-06T04:00:00Z"
COMPLETED = "2026-09-06T04:00:01Z"

COMMON = dict(
    repository="Quantum-L9/example",
    configuration_digest=DIGEST,
    run_id="99001",
    attempt=1,
    started_at=STARTED,
    completed_at=COMPLETED,
)


def _valid_bundle(revision: str = REVISION) -> FindingBundle:
    evidence = EvidenceRecord(
        evidence_id="ev-1",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id="python.example",
        evidence_type="static-analysis",
        message="example evidence",
        locations=(SourceLocation("src/example.py", start_line=7),),
        severity=Severity.LOW,
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
        locations=(SourceLocation("src/example.py", start_line=7, end_line=7),),
        fingerprint="fingerprint-1",
        severity=Severity.LOW,
        confidence=Confidence.HIGH,
    )
    return FindingBundle(
        SDK_version="2.0.0",
        generated_at="2026-09-06T04:00:00Z",
        snapshot=SnapshotDescriptor(
            snapshot_id="snapshot-1",
            repository_root=".",
            revision=revision,
            dirty=False,
        ),
        # The full validator enforces provider registration -- an evidence
        # record naming a provider the bundle never declares is rejected.
        # `project_mandatory_findings_observation` never sees this because
        # it takes an already-constructed bundle; this projector runs the
        # real validation, so the fixture has to be a real bundle.
        providers=(
            ProviderRun(
                provider_id="semgrep",
                adapter_version="1.0.0",
                provider_version="1.176.1",
                mode="execute",
                required=True,
            ),
        ),
        evidence=(evidence,),
        findings=(finding,),
        classifications=(),
        provider_failures=(),
        # Every declared provider needs a coverage record; the validator
        # refuses a bundle that runs a provider and reports nothing about
        # what it looked at.
        coverage=(
            Coverage(
                provider_id="semgrep",
                status=CoverageStatus.COMPLETE,
                files_considered=1,
                files_analyzed=1,
                limitations=(),
            ),
        ),
    )


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_valid(tmp_path: Path, revision: str = REVISION) -> Path:
    return _write(tmp_path / "bundle.json", _valid_bundle(revision).to_dict())


class TestTheVerdictIsObservedNotAsserted:
    def test_the_projector_takes_no_status_parameter(self) -> None:
        """The whole point. A status argument would defeat the control."""
        parameters = inspect.signature(project_sdk_validation_observation).parameters
        assert "status" not in parameters
        for forbidden in ("passed", "valid", "success", "ok"):
            assert forbidden not in parameters

    def test_a_valid_bundle_is_observed_as_passed(self, tmp_path: Path) -> None:
        observation = project_sdk_validation_observation(
            _write_valid(tmp_path), revision=REVISION, **COMMON
        )
        validate_observation(observation)
        assert observation["check"]["id"] == "l9.sdk-validation"
        assert observation["execution"]["status"] == "passed"

    def test_a_schema_invalid_bundle_is_observed_as_failed(
        self, tmp_path: Path
    ) -> None:
        path = _write(tmp_path / "bundle.json", {"SDK_version": "2.0.0"})
        observation = project_sdk_validation_observation(
            path, revision=REVISION, **COMMON
        )
        validate_observation(observation)
        assert observation["execution"]["status"] == "failed"

    def test_a_bundle_carrying_an_absolute_path_is_observed_as_failed(
        self, tmp_path: Path
    ) -> None:
        """Redaction is the second half of `bundle validate`, so it counts."""
        payload = _valid_bundle().to_dict()
        payload["snapshot"]["repository_root"] = "/home/someone/checkout"
        path = _write(tmp_path / "bundle.json", payload)
        observation = project_sdk_validation_observation(
            path, revision=REVISION, **COMMON
        )
        assert observation["execution"]["status"] == "failed"

    def test_unparseable_json_is_observed_as_failed(self, tmp_path: Path) -> None:
        path = tmp_path / "bundle.json"
        path.write_text("{not json", encoding="utf-8")
        observation = project_sdk_validation_observation(
            path, revision=REVISION, **COMMON
        )
        validate_observation(observation)
        assert observation["execution"]["status"] == "failed"

    def test_a_missing_file_is_observed_as_failed_with_no_artifact(
        self, tmp_path: Path
    ) -> None:
        """No content to address, so no fabricated artifact record."""
        observation = project_sdk_validation_observation(
            tmp_path / "absent.json", revision=REVISION, **COMMON
        )
        validate_observation(observation)
        assert observation["execution"]["status"] == "failed"
        assert observation["artifacts"] == []


class TestIdentityIsPreserved:
    def test_repository_revision_and_run_survive_the_projection(
        self, tmp_path: Path
    ) -> None:
        observation = project_sdk_validation_observation(
            _write_valid(tmp_path), revision=REVISION, **COMMON
        )
        assert observation["subject"]["repository"] == {
            "host": "github.com",
            "owner": "Quantum-L9",
            "name": "example",
        }
        assert observation["subject"]["revision"]["commit"] == REVISION
        assert observation["execution"]["runId"] == "99001"
        assert observation["execution"]["attempt"] == 1

    def test_a_revision_that_disagrees_with_the_bundle_raises(
        self, tmp_path: Path
    ) -> None:
        """Not a failed observation -- there is no honest verdict to record.

        A `failed` result here would say "this revision failed validation",
        which is false: a different revision was validated.
        """
        with pytest.raises(ValueError, match="different subject"):
            project_sdk_validation_observation(
                _write_valid(tmp_path, OTHER_REVISION), revision=REVISION, **COMMON
            )

    def test_an_empty_revision_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="revision is required"):
            project_sdk_validation_observation(
                _write_valid(tmp_path), revision="   ", **COMMON
            )

    def test_the_artifact_addresses_what_was_validated(self, tmp_path: Path) -> None:
        path = _write_valid(tmp_path)
        observation = project_sdk_validation_observation(
            path, revision=REVISION, **COMMON
        )
        artifact = observation["artifacts"][0]
        assert artifact["digest"] == {
            "algorithm": "sha256",
            "value": _valid_bundle().canonical_digest(),
        }
        assert artifact["sdkVersion"] == "2.0.0"

    def test_a_rejected_bundle_still_gets_a_content_address(
        self, tmp_path: Path
    ) -> None:
        """Which file was rejected must remain answerable."""
        import hashlib

        path = tmp_path / "bundle.json"
        path.write_text("{not json", encoding="utf-8")
        observation = project_sdk_validation_observation(
            path, revision=REVISION, **COMMON
        )
        artifact = observation["artifacts"][0]
        assert artifact["digest"]["value"] == hashlib.sha256(b"{not json").hexdigest()
        assert "sdkVersion" not in artifact

    def test_an_absolute_source_path_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="repository-relative"):
            project_sdk_validation_observation(
                _write_valid(tmp_path),
                revision=REVISION,
                source_path="/etc/bundle.json",
                **COMMON,
            )

    def test_a_traversing_source_path_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="repository-relative"):
            project_sdk_validation_observation(
                _write_valid(tmp_path),
                revision=REVISION,
                source_path="../bundle.json",
                **COMMON,
            )


class TestTheObservationIsWellFormed:
    def test_it_is_deterministic(self, tmp_path: Path) -> None:
        path = _write_valid(tmp_path)
        first = project_sdk_validation_observation(path, revision=REVISION, **COMMON)
        second = project_sdk_validation_observation(path, revision=REVISION, **COMMON)
        assert first == second
        assert first["observationId"] == second["observationId"]

    def test_it_carries_no_findings_and_zero_counts(self, tmp_path: Path) -> None:
        """The control evaluates `all-requirements-satisfied` from status.

        Summary counts describe a findings array; this check has none, so all
        four are zero and `build_observation`'s sum rule holds trivially.
        """
        observation = project_sdk_validation_observation(
            _write_valid(tmp_path), revision=REVISION, **COMMON
        )
        assert observation["findings"] == []
        assert observation["summary"] == {
            "findingCount": 0,
            "errorCount": 0,
            "warningCount": 0,
            "informationalCount": 0,
        }

    def test_the_producer_is_the_running_sdk_not_the_bundles(
        self, tmp_path: Path
    ) -> None:
        """A 2.0.0 bundle must not make this observation claim to be 2.0.0."""
        from l9_ci import __version__

        observation = project_sdk_validation_observation(
            _write_valid(tmp_path), revision=REVISION, **COMMON
        )
        assert observation["producer"]["version"] == __version__
        assert observation["producer"]["id"] == "l9-ci-sdk"

    def test_a_mutated_observation_fails_validation(self, tmp_path: Path) -> None:
        """Fail-closed downstream: the id is a content address.

        Assurance recomputes it on admission, so flipping a failed result to
        passed after the fact does not survive.
        """
        observation = project_sdk_validation_observation(
            _write_valid(tmp_path), revision=REVISION, **COMMON
        )
        observation["execution"]["status"] = "failed"
        with pytest.raises(ValueError, match="does not match the content address"):
            validate_observation(observation)


class TestOnlyValidationFailuresBecomeFailedObservations:
    """Code scanning flagged the original `except Exception` here, correctly.

    A defect in the SDK must not be reported as someone's bundle failing
    validation. An observation that blames the wrong party is worse than a
    crash, because it is admissible evidence.
    """

    def test_an_internal_defect_propagates_rather_than_becoming_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from l9_ci.commands import observations

        def exploding_validator(_path: Path) -> object:
            raise AttributeError("a refactor broke the validator")

        monkeypatch.setattr(
            observations, "load_and_validate_bundle", exploding_validator
        )
        with pytest.raises(AttributeError, match="a refactor broke the validator"):
            project_sdk_validation_observation(
                _write_valid(tmp_path), revision=REVISION, **COMMON
            )

    def test_a_validation_rejection_still_becomes_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from l9_ci.commands import observations

        def rejecting_validator(_path: Path) -> object:
            raise ValueError("artifact validation failed")

        monkeypatch.setattr(
            observations, "load_and_validate_bundle", rejecting_validator
        )
        observation = project_sdk_validation_observation(
            _write_valid(tmp_path), revision=REVISION, **COMMON
        )
        assert observation["execution"]["status"] == "failed"
