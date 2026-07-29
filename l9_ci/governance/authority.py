"""Observe authority-surface changes without approving or blocking them."""
from __future__ import annotations

from typing import Any, Mapping

from .models import Diagnostic, EvaluationResult, EvaluationStatus

_MUTATION_RANK = {"read_only": 0, "propose_only": 1, "enrich_only": 2, "internal_state": 3, "internal_plus_graph_sync": 4, "external_mutation": 5}
_APPROVAL_RANK = {"human": 0, "threshold_or_human": 1, "autonomous": 2}
_REPLAY_RANK = {False: 0, "conditional": 1, True: 2}
_RANKED_FIELDS = {"mutation_class": _MUTATION_RANK, "approval_mode": _APPROVAL_RANK, "replay_safe": _REPLAY_RANK}
_COLLECTION_FIELDS = {"required_provenance", "required_dependencies"}


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string_set(value: Any, path: str, invalid: list[Diagnostic]) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        invalid.append(Diagnostic("authority.collection_invalid", f"{path} must be an array of non-empty strings", path))
        return set()
    if len(value) != len(set(value)):
        invalid.append(Diagnostic("authority.collection_duplicate", f"{path} must contain unique values", path))
    return set(value)


def _validate_action(name: str, value: Any, side: str, invalid: list[Diagnostic]) -> Mapping[str, Any] | None:
    action = _mapping(value)
    path = f"{side}.actions.{name}"
    if action is None:
        invalid.append(Diagnostic("authority.action_invalid", f"action {name!r} must be a mapping", path))
        return None
    for field, ranks in _RANKED_FIELDS.items():
        field_value = action.get(field)
        if field_value is not None and field_value not in ranks:
            invalid.append(Diagnostic("authority.value_unrecognized", f"unrecognized {field} value {field_value!r}", f"{path}.{field}"))
    for field in _COLLECTION_FIELDS:
        _string_set(action.get(field), f"{path}.{field}", invalid)
    return action


def compare_authority(before: Mapping[str, Any], after: Mapping[str, Any]) -> EvaluationResult:
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic("authority.input_invalid", "before and after must be mappings"),))
    before_actions = _mapping(before.get("actions", {}))
    after_actions = _mapping(after.get("actions", {}))
    if before_actions is None or after_actions is None:
        return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic("authority.actions_invalid", "actions must be mappings", "actions"),))
    if any(not isinstance(name, str) or not name.strip() for name in set(before_actions) | set(after_actions)):
        return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic("authority.action_name_invalid", "action names must be non-empty strings", "actions"),))

    invalid: list[Diagnostic] = []
    validated_before = {name: _validate_action(name, value, "before", invalid) for name, value in before_actions.items()}
    validated_after = {name: _validate_action(name, value, "after", invalid) for name, value in after_actions.items()}
    if invalid:
        return EvaluationResult(EvaluationStatus.INVALID, tuple(invalid))

    changes: list[Diagnostic] = []
    for name in sorted(set(after_actions) - set(before_actions)):
        changes.append(Diagnostic("authority.action_added", f"action {name!r} was added", f"actions.{name}", "warning", {"after": dict(validated_after[name] or {})}))
    for name in sorted(set(before_actions) - set(after_actions)):
        changes.append(Diagnostic("authority.action_removed", f"action {name!r} was removed", f"actions.{name}", "warning", {"before": dict(validated_before[name] or {})}))

    for name in sorted(set(before_actions) & set(after_actions)):
        old = validated_before[name] or {}
        new = validated_after[name] or {}
        for field, ranks in _RANKED_FIELDS.items():
            old_present, new_present = field in old, field in new
            old_value, new_value = old.get(field), new.get(field)
            path = f"actions.{name}.{field}"
            if old_present != new_present:
                code = "authority.field_added" if new_present else "authority.field_removed"
                changes.append(Diagnostic(code, f"{name}: {field} was {'added' if new_present else 'removed'}", path, "warning", {"before": old_value, "after": new_value}))
                continue
            if not old_present or old_value == new_value:
                continue
            if field == "mutation_class":
                code = "authority.mutation_class_escalated" if ranks[new_value] > ranks[old_value] else "authority.mutation_class_reduced"
            elif field == "approval_mode":
                code = "authority.approval_mode_weakened" if ranks[new_value] > ranks[old_value] else "authority.approval_mode_strengthened"
            else:
                code = "authority.replay_safety_reduced" if ranks[new_value] < ranks[old_value] else "authority.replay_safety_increased"
            changes.append(Diagnostic(code, f"{name}: {field} changed {old_value!r} -> {new_value!r}", path, "warning", {"before": old_value, "after": new_value}))
        for field, removed_code, added_code in (
            ("required_provenance", "authority.required_provenance_removed", "authority.required_provenance_added"),
            ("required_dependencies", "authority.required_dependency_removed", "authority.required_dependency_added"),
        ):
            old_items = set(old.get(field) or [])
            new_items = set(new.get(field) or [])
            for removed in sorted(old_items - new_items):
                changes.append(Diagnostic(removed_code, f"{name}: required item {removed!r} was removed", f"actions.{name}.{field}", "warning"))
            for added in sorted(new_items - old_items):
                changes.append(Diagnostic(added_code, f"{name}: required item {added!r} was added", f"actions.{name}.{field}", "info"))
    return EvaluationResult(EvaluationStatus.PASS, tuple(changes), {"changed": bool(changes), "change_count": len(changes)})
