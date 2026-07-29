"""Compare declared constitutional state with supplied runtime attestation evidence."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from .models import Diagnostic, EvaluationResult, EvaluationStatus

_REQUIRED = {
    "node_id", "node_version", "contract_version", "contract_digest", "generated_at",
    "tracked_contract_hashes", "action_inventory", "tool_inventory", "event_inventory",
    "dependency_readiness", "degraded_modes", "policy_mode",
}
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_contract_path(value: str) -> bool:
    if not _non_empty_string(value) or "\x00" in value:
        return False
    posix = PurePosixPath(value.replace("\\", "/"))
    windows = PureWindowsPath(value)
    return not posix.is_absolute() and not windows.is_absolute() and not windows.drive and ".." not in posix.parts


def _string_set(value: Any, path: str, diagnostics: list[Diagnostic], *, allow_empty_items: bool = False) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or (not allow_empty_items and not item.strip()) for item in value):
        diagnostics.append(Diagnostic("attestation.inventory_invalid", f"{path} must be an array of non-empty strings", path))
        return set()
    if len(value) != len(set(value)):
        diagnostics.append(Diagnostic("attestation.inventory_duplicate", f"{path} must contain unique values", path))
    return set(value)


def _validate_timestamp(value: Any, diagnostics: list[Diagnostic]) -> None:
    if not isinstance(value, str):
        diagnostics.append(Diagnostic("attestation.generated_at_invalid", "generated_at must be an ISO-8601 timestamp", "generated_at"))
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        diagnostics.append(Diagnostic("attestation.generated_at_invalid", "generated_at must be an ISO-8601 timestamp", "generated_at"))
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        diagnostics.append(Diagnostic("attestation.generated_at_invalid", "generated_at must include a timezone", "generated_at"))


def _validate_hashes(value: Any, diagnostics: list[Diagnostic]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        diagnostics.append(Diagnostic("attestation.contract_hashes_invalid", "tracked_contract_hashes must be a mapping", "tracked_contract_hashes"))
        return {}
    result: dict[str, str] = {}
    for path, digest in value.items():
        if not isinstance(path, str) or not _safe_contract_path(path):
            diagnostics.append(Diagnostic("attestation.contract_hash_path_invalid", "tracked contract hash paths must be safe relative paths", f"tracked_contract_hashes.{path}"))
            continue
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            diagnostics.append(Diagnostic("attestation.contract_hash_digest_invalid", "tracked contract hashes must be lowercase sha256 digests", f"tracked_contract_hashes.{path}"))
            continue
        result[path.replace("\\", "/")] = digest
    return result


def _validate_readiness(value: Any, diagnostics: list[Diagnostic]) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        diagnostics.append(Diagnostic("attestation.readiness_invalid", "dependency_readiness must be a mapping", "dependency_readiness"))
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    required_fields = {"required", "ready", "env_vars", "missing_env"}
    for dependency, entry in value.items():
        path = f"dependency_readiness.{dependency}"
        if not _non_empty_string(dependency):
            diagnostics.append(Diagnostic("attestation.dependency_name_invalid", "dependency names must be non-empty strings", "dependency_readiness"))
            continue
        if not isinstance(entry, Mapping):
            diagnostics.append(Diagnostic("attestation.dependency_readiness_invalid", f"readiness for {dependency!r} must be a mapping", path))
            continue
        missing = sorted(required_fields - set(entry))
        if missing:
            diagnostics.extend(Diagnostic("attestation.dependency_field_missing", f"required readiness field {name!r} is missing", f"{path}.{name}") for name in missing)
            continue
        if not isinstance(entry.get("required"), bool) or not isinstance(entry.get("ready"), bool):
            diagnostics.append(Diagnostic("attestation.dependency_readiness_invalid", "required and ready must be booleans", path))
        env_vars = _string_set(entry.get("env_vars"), f"{path}.env_vars", diagnostics)
        missing_env = _string_set(entry.get("missing_env"), f"{path}.missing_env", diagnostics)
        if not missing_env <= env_vars:
            diagnostics.append(Diagnostic("attestation.missing_env_not_declared", "missing_env must be a subset of env_vars", f"{path}.missing_env"))
        if entry.get("ready") is True and missing_env:
            diagnostics.append(Diagnostic("attestation.ready_with_missing_env", "ready cannot be true when missing_env is non-empty", path))
        result[str(dependency)] = entry
    return result


def compare_attestation(
    constitution: Mapping[str, Any],
    attestation: Mapping[str, Any],
    *,
    expected_contract_digest: str | None = None,
    expected_tracked_contract_hashes: Mapping[str, str] | None = None,
    expected_policy_mode: str | None = None,
) -> EvaluationResult:
    if not isinstance(constitution, Mapping) or not isinstance(attestation, Mapping):
        return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic("attestation.input_invalid", "constitution and attestation must be mappings"),))
    missing = sorted(_REQUIRED - set(attestation))
    if missing:
        return EvaluationResult(EvaluationStatus.INVALID, tuple(Diagnostic("attestation.required_missing", f"required attestation field {name!r} is missing", name) for name in missing))

    invalid: list[Diagnostic] = []
    drift: list[Diagnostic] = []
    incomplete: list[Diagnostic] = []
    node = constitution.get("node")
    if not isinstance(node, Mapping):
        invalid.append(Diagnostic("constitution.node_invalid", "constitution.node must be a mapping", "node"))
        node = {}
    for field in ("node_id", "node_version", "contract_version", "policy_mode"):
        if not _non_empty_string(attestation.get(field)):
            invalid.append(Diagnostic("attestation.field_invalid", f"{field} must be a non-empty string", field))
    contract_digest = attestation.get("contract_digest")
    if not isinstance(contract_digest, str) or _SHA256.fullmatch(contract_digest) is None:
        invalid.append(Diagnostic("attestation.contract_digest_invalid", "contract_digest must be a lowercase sha256 digest", "contract_digest"))
    _validate_timestamp(attestation.get("generated_at"), invalid)

    inventories: dict[str, set[str]] = {}
    for kind in ("action", "tool", "event"):
        inventories[kind] = _string_set(attestation.get(f"{kind}_inventory"), f"{kind}_inventory", invalid)
    hashes = _validate_hashes(attestation.get("tracked_contract_hashes"), invalid)
    degraded_modes = _string_set(attestation.get("degraded_modes"), "degraded_modes", invalid)
    readiness = _validate_readiness(attestation.get("dependency_readiness"), invalid)
    if invalid:
        return EvaluationResult(EvaluationStatus.INVALID, tuple(invalid))

    if node.get("id") != attestation.get("node_id"):
        drift.append(Diagnostic("attestation.node_mismatch", "attested node_id does not match constitution", "node_id"))
    if node.get("version") is not None and str(node.get("version")) != attestation.get("node_version"):
        drift.append(Diagnostic("attestation.node_version_mismatch", "attested node_version does not match constitution", "node_version"))
    if node.get("contract_version") is not None and str(node.get("contract_version")) != attestation.get("contract_version"):
        drift.append(Diagnostic("attestation.contract_version_mismatch", "attested contract_version does not match constitution", "contract_version"))
    if expected_contract_digest is not None:
        if _SHA256.fullmatch(expected_contract_digest) is None:
            return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic("attestation.expected_digest_invalid", "expected_contract_digest must be a lowercase sha256 digest", "expected_contract_digest"),))
        if contract_digest != expected_contract_digest:
            drift.append(Diagnostic("attestation.contract_digest_mismatch", "attested contract_digest does not match expected digest", "contract_digest", details={"expected": expected_contract_digest, "observed": contract_digest}))
    if expected_policy_mode is not None and attestation.get("policy_mode") != expected_policy_mode:
        drift.append(Diagnostic("attestation.policy_mode_mismatch", "attested policy_mode does not match expected mode", "policy_mode", details={"expected": expected_policy_mode, "observed": attestation.get("policy_mode")}))
    if expected_tracked_contract_hashes is not None:
        expected_hashes = _validate_hashes(expected_tracked_contract_hashes, invalid)
        if invalid:
            return EvaluationResult(EvaluationStatus.INVALID, tuple(invalid))
        for path in sorted(set(expected_hashes) | set(hashes)):
            expected = expected_hashes.get(path)
            observed = hashes.get(path)
            if expected != observed:
                drift.append(Diagnostic("attestation.contract_hash_mismatch", f"tracked contract hash differs for {path!r}", f"tracked_contract_hashes.{path}", details={"expected": expected, "observed": observed}))

    declared: dict[str, set[str]] = {}
    for kind, field in (("action", "actions"), ("tool", "tools"), ("event", "events")):
        value = constitution.get(field, {})
        if not isinstance(value, Mapping):
            return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic(f"constitution.{field}_invalid", f"constitution.{field} must be a mapping", field),))
        if any(not _non_empty_string(name) for name in value):
            return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic(f"constitution.{field}_name_invalid", f"constitution.{field} names must be non-empty strings", field),))
        declared[kind] = set(value)
        for name in sorted(declared[kind] - inventories[kind]):
            drift.append(Diagnostic(f"attestation.{kind}_missing", f"declared {kind} {name!r} is absent", f"{kind}_inventory"))
        for name in sorted(inventories[kind] - declared[kind]):
            drift.append(Diagnostic(f"attestation.{kind}_undeclared", f"undeclared {kind} {name!r} is present", f"{kind}_inventory"))

    dependencies = constitution.get("dependencies", {})
    if not isinstance(dependencies, Mapping):
        return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic("constitution.dependencies_invalid", "constitution.dependencies must be a mapping", "dependencies"),))
    for dependency, declaration in dependencies.items():
        if not _non_empty_string(dependency) or not isinstance(declaration, Mapping) or not isinstance(declaration.get("required"), bool):
            return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic("constitution.dependency_invalid", f"dependency {dependency!r} must declare boolean required", f"dependencies.{dependency}"),))
        observed = readiness.get(dependency)
        if observed is None:
            if declaration["required"]:
                incomplete.append(Diagnostic("attestation.required_dependency_missing", f"required dependency {dependency!r} has no readiness evidence", f"dependency_readiness.{dependency}"))
            continue
        if observed.get("required") != declaration["required"]:
            drift.append(Diagnostic("attestation.dependency_required_mismatch", f"dependency {dependency!r} required flag differs", f"dependency_readiness.{dependency}.required"))
        if declaration["required"] and observed.get("ready") is not True:
            incomplete.append(Diagnostic("attestation.required_dependency_unready", f"required dependency {dependency!r} is not ready", f"dependency_readiness.{dependency}"))
    for dependency in sorted(set(readiness) - set(dependencies)):
        drift.append(Diagnostic("attestation.dependency_undeclared", f"undeclared dependency {dependency!r} is present", f"dependency_readiness.{dependency}"))

    declared_degraded: set[str] = set()
    for declaration in dependencies.values():
        modes = declaration.get("degraded_modes", [])
        if isinstance(modes, list):
            declared_degraded.update(item for item in modes if isinstance(item, str))
    for mode in sorted(degraded_modes - declared_degraded):
        drift.append(Diagnostic("attestation.degraded_mode_undeclared", f"undeclared degraded mode {mode!r} is present", "degraded_modes"))

    diagnostics = tuple(drift + incomplete)
    if drift:
        status = EvaluationStatus.FAIL
    elif incomplete:
        status = EvaluationStatus.INCOMPLETE
    else:
        status = EvaluationStatus.PASS
    return EvaluationResult(status, diagnostics, {"drift_count": len(drift), "incomplete_count": len(incomplete)})
