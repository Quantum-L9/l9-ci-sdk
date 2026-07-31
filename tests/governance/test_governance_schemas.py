from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

SCHEMA_DIR = Path(__file__).parents[2] / "l9_ci" / "schemas" / "v1"


def load(name: str) -> dict:
    payload = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(payload)
    return payload


def test_governance_schemas_are_valid_and_have_unique_ids():
    ids: set[str] = set()
    expected = {
        "promotion-policy.schema.json",
        "policy-observation.schema.json",
        "attestation-envelope.schema.json",
        "evidence-report.schema.json",
    }
    assert expected <= {path.name for path in SCHEMA_DIR.glob("*.json")}
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        payload = load(path.name)
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert payload["$id"] not in ids
        ids.add(payload["$id"])
        assert payload["type"] == "object"


def test_promotion_and_observation_schemas_enforce_contract_depth():
    policy = {
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
    observation = {
        "schema": "l9.policy-observation/v1",
        "first_observed_at": "2026-07-01T00:00:00Z",
        "last_observed_at": "2026-07-08T00:00:00Z",
        "completed_runs": 20,
        "contract_failures": 0,
        "artifact_validation_failures": 0,
    }
    Draft202012Validator(load("promotion-policy.schema.json")).validate(policy)
    Draft202012Validator(
        load("policy-observation.schema.json"), format_checker=FormatChecker()
    ).validate(observation)
    with pytest.raises(ValidationError):
        Draft202012Validator(load("promotion-policy.schema.json")).validate(
            {**policy, "requirements": {}}
        )
    with pytest.raises(ValidationError):
        Draft202012Validator(
            load("policy-observation.schema.json"), format_checker=FormatChecker()
        ).validate({**observation, "first_observed_at": "not-a-date"})


def test_attestation_and_report_schemas_reject_shallow_invalid_shapes():
    attestation = {
        "node_id": "n",
        "node_version": "1",
        "contract_version": "1",
        "contract_digest": "sha256:" + "a" * 64,
        "generated_at": "2026-07-29T12:00:00Z",
        "tracked_contract_hashes": {},
        "action_inventory": [],
        "tool_inventory": [],
        "event_inventory": [],
        "dependency_readiness": {
            "db": {"required": True, "ready": True, "env_vars": [], "missing_env": []}
        },
        "degraded_modes": [],
        "policy_mode": "enforced",
    }
    report = {
        "schema": "l9.evidence-report/v1",
        "report_id": "r",
        "producer": {"id": "p"},
        "subject": {},
        "operation": {},
        "outcome": {"status": "pass"},
        "evidence_refs": [],
        "diagnostics": [],
        "limitations": [],
        "provenance": {},
    }
    Draft202012Validator(
        load("attestation-envelope.schema.json"), format_checker=FormatChecker()
    ).validate(attestation)
    Draft202012Validator(load("evidence-report.schema.json")).validate(report)
    with pytest.raises(ValidationError):
        Draft202012Validator(load("attestation-envelope.schema.json")).validate(
            {**attestation, "dependency_readiness": {"db": {"ready": True}}}
        )
    with pytest.raises(ValidationError):
        Draft202012Validator(load("evidence-report.schema.json")).validate(
            {**report, "producer": {}}
        )
