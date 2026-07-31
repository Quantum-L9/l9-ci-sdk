"""Pure promotion-transition and evidence-eligibility evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .models import Diagnostic, EvaluationResult, EvaluationStatus

_POLICY_SCHEMA = "l9.promotion-policy/v1"
_OBSERVATION_SCHEMA = "l9.policy-observation/v1"


def _parse_timestamp(
    value: Any, path: str, diagnostics: list[Diagnostic]
) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(
            Diagnostic("promotion.timestamp_missing", f"{path} is required", path)
        )
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        diagnostics.append(
            Diagnostic("promotion.timestamp_invalid", f"{path} is not ISO-8601", path)
        )
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        diagnostics.append(
            Diagnostic(
                "promotion.timestamp_timezone_missing",
                f"{path} must include a timezone",
                path,
            )
        )
        return None
    return parsed.astimezone(timezone.utc)


def _non_negative_int(
    value: Any, path: str, diagnostics: list[Diagnostic]
) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        diagnostics.append(
            Diagnostic(
                "promotion.metric_invalid",
                f"{path} must be a non-negative integer",
                path,
            )
        )
        return None
    return value


def _requirement_int(
    requirements: Mapping[str, Any], name: str, diagnostics: list[Diagnostic]
) -> int | None:
    value = requirements.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        diagnostics.append(
            Diagnostic(
                "promotion.requirement_invalid",
                f"{name} must be a non-negative integer",
                f"requirements.{name}",
            )
        )
        return None
    return value


def _validate_transitions(
    transitions: Mapping[str, Any], diagnostics: list[Diagnostic]
) -> None:
    if not transitions:
        diagnostics.append(
            Diagnostic(
                "promotion.transitions_empty",
                "transitions must not be empty",
                "transitions",
            )
        )
        return
    for source, targets in transitions.items():
        path = f"transitions.{source}"
        if not isinstance(source, str) or not source.strip():
            diagnostics.append(
                Diagnostic(
                    "promotion.transition_source_invalid",
                    "transition source must be a non-empty string",
                    "transitions",
                )
            )
            continue
        if not isinstance(targets, list) or any(
            not isinstance(item, str) or not item.strip() for item in targets
        ):
            diagnostics.append(
                Diagnostic(
                    "promotion.transition_targets_invalid",
                    "transition targets must be an array of non-empty strings",
                    path,
                )
            )
        elif len(targets) != len(set(targets)):
            diagnostics.append(
                Diagnostic(
                    "promotion.transition_targets_duplicate",
                    "transition targets must be unique",
                    path,
                )
            )


def evaluate_promotion(
    policy: Mapping[str, Any],
    current_mode: str,
    requested_mode: str,
    observation: Mapping[str, Any],
    *,
    approval_present: bool = False,
) -> EvaluationResult:
    diagnostics: list[Diagnostic] = []
    if not isinstance(policy, Mapping) or not isinstance(observation, Mapping):
        return EvaluationResult(
            EvaluationStatus.INVALID,
            (
                Diagnostic(
                    "promotion.input_invalid", "policy and observation must be mappings"
                ),
            ),
        )
    if policy.get("schema") != _POLICY_SCHEMA:
        diagnostics.append(
            Diagnostic(
                "promotion.policy_schema_unsupported",
                f"policy.schema must be {_POLICY_SCHEMA}",
                "schema",
            )
        )
    if observation.get("schema") != _OBSERVATION_SCHEMA:
        diagnostics.append(
            Diagnostic(
                "promotion.observation_schema_unsupported",
                f"observation.schema must be {_OBSERVATION_SCHEMA}",
                "observation.schema",
            )
        )
    if not isinstance(current_mode, str) or not current_mode.strip():
        diagnostics.append(
            Diagnostic(
                "promotion.current_mode_invalid",
                "current_mode must be a non-empty string",
                "current_mode",
            )
        )
    if not isinstance(requested_mode, str) or not requested_mode.strip():
        diagnostics.append(
            Diagnostic(
                "promotion.requested_mode_invalid",
                "requested_mode must be a non-empty string",
                "requested_mode",
            )
        )
    if not isinstance(approval_present, bool):
        diagnostics.append(
            Diagnostic(
                "promotion.approval_flag_invalid",
                "approval_present must be boolean",
                "approval_present",
            )
        )
    transitions = policy.get("transitions")
    requirements = policy.get("requirements")
    if not isinstance(transitions, Mapping) or not isinstance(requirements, Mapping):
        diagnostics.append(
            Diagnostic(
                "promotion.policy_invalid",
                "policy requires transitions and requirements mappings",
            )
        )
        return EvaluationResult(EvaluationStatus.INVALID, tuple(diagnostics))
    _validate_transitions(transitions, diagnostics)

    required_names = {
        "minimum_observation_runs",
        "minimum_observation_days",
        "maximum_contract_failures",
        "maximum_artifact_validation_failures",
        "approval_required",
    }
    missing_requirements = sorted(required_names - set(requirements))
    diagnostics.extend(
        Diagnostic(
            "promotion.requirement_missing",
            f"required policy field {name!r} is missing",
            f"requirements.{name}",
        )
        for name in missing_requirements
    )
    unexpected_requirements = sorted(set(requirements) - required_names)
    diagnostics.extend(
        Diagnostic(
            "promotion.requirement_unknown",
            f"unknown policy requirement {name!r}",
            f"requirements.{name}",
        )
        for name in unexpected_requirements
    )

    allowed = transitions.get(current_mode) if isinstance(current_mode, str) else None
    if isinstance(allowed, list) and requested_mode not in allowed:
        diagnostics.append(
            Diagnostic(
                "promotion.transition_illegal",
                f"transition {current_mode!r} -> {requested_mode!r} is not permitted",
                "transitions",
            )
        )
    elif not isinstance(allowed, list):
        diagnostics.append(
            Diagnostic(
                "promotion.transition_source_unknown",
                f"current mode {current_mode!r} has no transition declaration",
                "current_mode",
            )
        )

    first = _parse_timestamp(
        observation.get("first_observed_at"), "first_observed_at", diagnostics
    )
    last = _parse_timestamp(
        observation.get("last_observed_at"), "last_observed_at", diagnostics
    )
    completed_runs = _non_negative_int(
        observation.get("completed_runs"), "completed_runs", diagnostics
    )
    contract_failures = _non_negative_int(
        observation.get("contract_failures"), "contract_failures", diagnostics
    )
    artifact_failures = _non_negative_int(
        observation.get("artifact_validation_failures"),
        "artifact_validation_failures",
        diagnostics,
    )
    minimum_runs = _requirement_int(
        requirements, "minimum_observation_runs", diagnostics
    )
    minimum_days = _requirement_int(
        requirements, "minimum_observation_days", diagnostics
    )
    maximum_contract_failures = _requirement_int(
        requirements, "maximum_contract_failures", diagnostics
    )
    maximum_artifact_failures = _requirement_int(
        requirements, "maximum_artifact_validation_failures", diagnostics
    )
    approval_required = requirements.get("approval_required")
    if not isinstance(approval_required, bool):
        diagnostics.append(
            Diagnostic(
                "promotion.requirement_invalid",
                "approval_required must be boolean",
                "requirements.approval_required",
            )
        )
    if first is not None and last is not None and last < first:
        diagnostics.append(
            Diagnostic(
                "promotion.observation_window_invalid",
                "last_observed_at precedes first_observed_at",
                "last_observed_at",
            )
        )
    if diagnostics:
        return EvaluationResult(EvaluationStatus.INVALID, tuple(diagnostics))

    assert first is not None and last is not None
    assert (
        completed_runs is not None
        and contract_failures is not None
        and artifact_failures is not None
    )
    assert minimum_runs is not None and minimum_days is not None
    assert (
        maximum_contract_failures is not None and maximum_artifact_failures is not None
    )
    assert isinstance(approval_required, bool)
    unmet: list[Diagnostic] = []
    if completed_runs < minimum_runs:
        unmet.append(
            Diagnostic(
                "promotion.observation_runs_insufficient",
                f"requires at least {minimum_runs} completed runs",
                "completed_runs",
                details={"observed": completed_runs, "required": minimum_runs},
            )
        )
    elapsed_seconds = (last - first).total_seconds()
    elapsed_days = int(elapsed_seconds // 86400)
    if elapsed_days < minimum_days:
        unmet.append(
            Diagnostic(
                "promotion.observation_days_insufficient",
                f"requires at least {minimum_days} full observation days",
                "last_observed_at",
                details={"observed": elapsed_days, "required": minimum_days},
            )
        )
    if contract_failures > maximum_contract_failures:
        unmet.append(
            Diagnostic(
                "promotion.contract_failure_budget_exceeded",
                "contract_failures exceeds allowed maximum",
                "contract_failures",
                details={
                    "observed": contract_failures,
                    "allowed": maximum_contract_failures,
                },
            )
        )
    if artifact_failures > maximum_artifact_failures:
        unmet.append(
            Diagnostic(
                "promotion.artifact_failure_budget_exceeded",
                "artifact_validation_failures exceeds allowed maximum",
                "artifact_validation_failures",
                details={
                    "observed": artifact_failures,
                    "allowed": maximum_artifact_failures,
                },
            )
        )
    if approval_required and not approval_present:
        unmet.append(
            Diagnostic(
                "promotion.approval_absent",
                "required approval evidence is absent",
                "approval",
            )
        )
    evidence = {
        "current_mode": current_mode,
        "requested_mode": requested_mode,
        "elapsed_days": elapsed_days,
    }
    if unmet:
        return EvaluationResult(EvaluationStatus.INELIGIBLE, tuple(unmet), evidence)
    return EvaluationResult(EvaluationStatus.ELIGIBLE, evidence=evidence)
