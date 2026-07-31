from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from l9_ci.governance import (
    Diagnostic,
    EvaluationResult,
    EvaluationStatus,
    compare_attestation,
    compare_authority,
    contract_file_hashes,
    contract_set_digest,
    evaluate_promotion,
    validate_governed_report,
)


def valid_policy() -> dict:
    return {
        "schema": "l9.promotion-policy/v1",
        "transitions": {"shadow": ["advisory"]},
        "requirements": {
            "minimum_observation_runs": 20,
            "minimum_observation_days": 7,
            "maximum_contract_failures": 0,
            "maximum_artifact_validation_failures": 0,
            "approval_required": True,
        },
    }


def valid_observation() -> dict:
    return {
        "schema": "l9.policy-observation/v1",
        "first_observed_at": "2026-07-01T00:00:00Z",
        "last_observed_at": "2026-07-10T00:00:00Z",
        "completed_runs": 20,
        "contract_failures": 0,
        "artifact_validation_failures": 0,
    }


def valid_attestation() -> dict:
    return {
        "node_id": "n1",
        "node_version": "1",
        "contract_version": "1",
        "contract_digest": "sha256:" + "a" * 64,
        "generated_at": "2026-07-29T12:00:00Z",
        "tracked_contract_hashes": {"contract.yml": "sha256:" + "b" * 64},
        "action_inventory": ["scan"],
        "tool_inventory": [],
        "event_inventory": [],
        "dependency_readiness": {
            "Semgrep": {
                "required": True,
                "ready": True,
                "env_vars": [],
                "missing_env": [],
            }
        },
        "degraded_modes": [],
        "policy_mode": "enforced",
    }


def constitution() -> dict:
    return {
        "node": {"id": "n1", "version": "1", "contract_version": "1"},
        "actions": {"scan": {}},
        "tools": {},
        "events": {},
        "dependencies": {"Semgrep": {"required": True, "degraded_modes": []}},
    }


def valid_report() -> dict:
    return {
        "schema": "l9.evidence-report/v1",
        "report_id": "r1",
        "producer": {"id": "p"},
        "subject": {},
        "operation": {},
        "outcome": {"status": "pass"},
        "evidence_refs": ["e1"],
        "diagnostics": [],
        "limitations": [],
        "provenance": {},
    }


def test_result_contract_is_deeply_immutable_and_round_trips():
    source = {"nested": {"values": [1, 2]}}
    result = EvaluationResult(
        EvaluationStatus.PASS, (Diagnostic("x", "ok", details=source),), source
    )
    source["nested"]["values"].append(3)
    assert result.to_dict()["evidence"] == {"nested": {"values": [1, 2]}}
    with pytest.raises(TypeError):
        result.evidence["x"] = 1  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        result.status = EvaluationStatus.FAIL  # type: ignore[misc]


def test_contract_digest_is_order_independent_and_normalizes_newlines():
    assert contract_set_digest(
        {"b.yml": b"x: 1\r\n", "a.yml": b"y: 2\n"}
    ) == contract_set_digest({"a.yml": b"y: 2\n", "b.yml": b"x: 1\n"})


@pytest.mark.parametrize(
    "path", ["../secret", "/tmp/x", "C:\\temp\\x", "C:relative", "a\x00b"]
)
def test_contract_digest_rejects_unsafe_paths(path: str):
    with pytest.raises(ValueError, match="unsafe"):
        contract_set_digest({path: b"x"})


def test_contract_digest_rejects_normalized_and_unicode_collisions():
    with pytest.raises(ValueError, match="collide"):
        contract_file_hashes({"a\\b.yml": b"one", "a/b.yml": b"two"})
    with pytest.raises(ValueError, match="collide"):
        contract_file_hashes({"caf\u00e9.yml": b"one", "cafe\u0301.yml": b"two"})


def test_contract_digest_rejects_non_mapping_and_non_bytes():
    with pytest.raises(TypeError, match="mapping"):
        contract_set_digest([])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="bytes"):
        contract_set_digest({"a.yml": "x"})  # type: ignore[dict-item]


def test_illegal_promotion_transition_is_invalid():
    policy = valid_policy()
    policy["transitions"] = {"disabled": ["shadow"]}
    result = evaluate_promotion(policy, "disabled", "blocking", valid_observation())
    assert result.status is EvaluationStatus.INVALID


def test_insufficient_runs_is_ineligible_not_invalid():
    observation = valid_observation()
    observation["completed_runs"] = 19
    result = evaluate_promotion(
        valid_policy(), "shadow", "advisory", observation, approval_present=True
    )
    assert result.status is EvaluationStatus.INELIGIBLE
    assert {d.code for d in result.diagnostics} == {
        "promotion.observation_runs_insufficient"
    }


def test_promotion_requires_versioned_contracts_and_all_requirements():
    policy = valid_policy()
    del policy["schema"]
    del policy["requirements"]["minimum_observation_days"]
    observation = valid_observation()
    del observation["schema"]
    result = evaluate_promotion(policy, "shadow", "advisory", observation)
    assert result.status is EvaluationStatus.INVALID
    assert {
        "promotion.policy_schema_unsupported",
        "promotion.observation_schema_unsupported",
        "promotion.requirement_missing",
    } <= {d.code for d in result.diagnostics}


def test_promotion_rejects_naive_reverse_window_and_nonboolean_approval():
    observation = valid_observation()
    observation["first_observed_at"] = "2026-07-10T00:00:00"
    observation["last_observed_at"] = "2026-07-01T00:00:00Z"
    assert (
        evaluate_promotion(
            valid_policy(), "shadow", "advisory", observation, approval_present=1
        ).status
        is EvaluationStatus.INVALID
    )  # type: ignore[arg-type]


def test_authority_diff_detects_weakening_removal_and_addition():
    before = {
        "actions": {
            "write": {
                "approval_mode": "human",
                "mutation_class": "propose_only",
                "replay_safe": True,
                "required_provenance": ["hash"],
                "required_dependencies": ["db"],
            }
        }
    }
    after = {
        "actions": {
            "write": {
                "approval_mode": "autonomous",
                "mutation_class": "external_mutation",
                "replay_safe": "conditional",
                "required_provenance": [],
                "required_dependencies": ["queue"],
            }
        }
    }
    result = compare_authority(before, after)
    assert result.status is EvaluationStatus.PASS
    assert {
        "authority.approval_mode_weakened",
        "authority.mutation_class_escalated",
        "authority.replay_safety_reduced",
        "authority.required_provenance_removed",
        "authority.required_dependency_removed",
        "authority.required_dependency_added",
    } <= {d.code for d in result.diagnostics}


def test_authority_validates_added_actions_and_duplicate_collections():
    result = compare_authority(
        {"actions": {}},
        {
            "actions": {
                "x": {"mutation_class": "magic", "required_dependencies": ["db", "db"]}
            }
        },
    )
    assert result.status is EvaluationStatus.INVALID


def test_attestation_passes_when_matching():
    assert (
        compare_attestation(
            constitution(), valid_attestation(), expected_policy_mode="enforced"
        ).status
        is EvaluationStatus.PASS
    )


def test_attestation_missing_required_dependency_is_incomplete():
    attestation = valid_attestation()
    attestation["dependency_readiness"]["Semgrep"]["ready"] = False
    assert (
        compare_attestation(constitution(), attestation).status
        is EvaluationStatus.INCOMPLETE
    )


def test_attestation_detects_digest_inventory_policy_and_undeclared_dependency_drift():
    attestation = valid_attestation()
    attestation["action_inventory"] = ["other"]
    attestation["dependency_readiness"]["Other"] = {
        "required": False,
        "ready": True,
        "env_vars": [],
        "missing_env": [],
    }
    result = compare_attestation(
        constitution(),
        attestation,
        expected_contract_digest="sha256:" + "c" * 64,
        expected_policy_mode="shadow",
    )
    assert result.status is EvaluationStatus.FAIL
    assert {
        "attestation.contract_digest_mismatch",
        "attestation.action_missing",
        "attestation.action_undeclared",
        "attestation.policy_mode_mismatch",
        "attestation.dependency_undeclared",
    } <= {d.code for d in result.diagnostics}


def test_attestation_rejects_bad_hashes_paths_and_inconsistent_readiness():
    attestation = valid_attestation()
    attestation["contract_digest"] = "bad"
    attestation["tracked_contract_hashes"] = {"../x": "bad"}
    attestation["dependency_readiness"]["Semgrep"] = {
        "required": True,
        "ready": True,
        "env_vars": ["TOKEN"],
        "missing_env": ["TOKEN"],
    }
    assert (
        compare_attestation(constitution(), attestation).status
        is EvaluationStatus.INVALID
    )


@pytest.mark.parametrize(
    "path",
    [
        "/Users/example/repo",
        "C:\\Users\\example\\repo",
        "file:///etc/passwd",
        "file://server/share/x",
    ],
)
def test_governed_report_rejects_absolute_paths(path: str):
    report = valid_report()
    report["subject"] = {"path": path}
    result = validate_governed_report(report)
    assert result.status is EvaluationStatus.INVALID
    assert "report.absolute_path_detected" in {d.code for d in result.diagnostics}


def test_governed_report_accepts_https_url_and_redacted_secret():
    report = valid_report()
    report["subject"]["url"] = "https://example.com/a/b"
    report["limitations"] = ["password=[REDACTED]"]
    assert validate_governed_report(report).status is EvaluationStatus.PASS


def test_governed_report_rejects_real_secret_duplicates_and_bad_producer():
    report = valid_report()
    report["producer"] = {"id": ""}
    report["evidence_refs"] = ["e1", "e1"]
    report["limitations"] = ["api_key=abc123"]
    result = validate_governed_report(report)
    assert result.status is EvaluationStatus.INVALID
    assert {
        "report.producer_invalid",
        "report.evidence_ref_duplicate",
        "report.secret_material_detected",
    } <= {d.code for d in result.diagnostics}


def test_promotion_eligible_when_every_requirement_is_met():
    result = evaluate_promotion(
        valid_policy(), "shadow", "advisory", valid_observation(), approval_present=True
    )
    assert result.status is EvaluationStatus.ELIGIBLE
    assert result.diagnostics == ()
    assert result.evidence["elapsed_days"] == 9
    assert result.evidence["current_mode"] == "shadow"
    assert result.evidence["requested_mode"] == "advisory"


def test_promotion_ineligible_reports_every_unmet_requirement():
    observation = valid_observation()
    observation["last_observed_at"] = "2026-07-02T00:00:00Z"
    observation["contract_failures"] = 1
    observation["artifact_validation_failures"] = 2
    result = evaluate_promotion(
        valid_policy(), "shadow", "advisory", observation, approval_present=False
    )
    assert result.status is EvaluationStatus.INELIGIBLE
    assert {
        "promotion.observation_days_insufficient",
        "promotion.contract_failure_budget_exceeded",
        "promotion.artifact_failure_budget_exceeded",
        "promotion.approval_absent",
    } == {d.code for d in result.diagnostics}


def test_promotion_rejects_non_mapping_inputs():
    result = evaluate_promotion([], "shadow", "advisory", valid_observation())  # type: ignore[arg-type]
    assert result.status is EvaluationStatus.INVALID
    assert {d.code for d in result.diagnostics} == {"promotion.input_invalid"}


def test_promotion_flags_unknown_requirement_and_missing_transition_source():
    policy = valid_policy()
    policy["requirements"]["surprise"] = 1
    result = evaluate_promotion(
        policy, "unlisted", "advisory", valid_observation(), approval_present=True
    )
    assert result.status is EvaluationStatus.INVALID
    codes = {d.code for d in result.diagnostics}
    assert "promotion.requirement_unknown" in codes
    assert "promotion.transition_source_unknown" in codes


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"code": "", "message": "m"}, "code"),
        ({"code": "c", "message": " "}, "message"),
    ],
)
def test_diagnostic_rejects_blank_code_or_message(kwargs: dict, match: str):
    with pytest.raises(ValueError, match=match):
        Diagnostic(**kwargs)


def test_diagnostic_rejects_bad_path_severity_and_details_types():
    with pytest.raises(TypeError, match="path"):
        Diagnostic("c", "m", path=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="severity"):
        Diagnostic("c", "m", severity="critical")
    with pytest.raises(TypeError, match="details"):
        Diagnostic("c", "m", details=[])  # type: ignore[arg-type]


def test_evaluation_result_rejects_bad_status_diagnostics_and_evidence():
    with pytest.raises(TypeError, match="status"):
        EvaluationResult("pass")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Diagnostic"):
        EvaluationResult(EvaluationStatus.PASS, ("nope",))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="evidence"):
        EvaluationResult(EvaluationStatus.PASS, (), evidence=[])  # type: ignore[arg-type]


def test_evaluation_result_freezes_and_thaws_set_evidence_deterministically():
    result = EvaluationResult(EvaluationStatus.PASS, evidence={"seen": {"b", "a"}})
    assert isinstance(result.evidence["seen"], frozenset)
    assert result.to_dict()["evidence"] == {"seen": ["a", "b"]}
