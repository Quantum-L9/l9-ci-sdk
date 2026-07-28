"""Artifact compatibility rules."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from l9_ci.contracts import (
    FINDING_BUNDLE_PROTOCOL,
    FINDING_BUNDLE_SCHEMA_VERSION,
)


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    compatible: bool
    errors: tuple[str, ...]


def _major(version: str) -> int:
    try:
        return int(version.split(".", maxsplit=1)[0])
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"invalid semantic version: {version!r}") from exc


def check_bundle_compatibility(
    payload: Mapping[str, Any],
) -> CompatibilityResult:
    """Check protocol and schema-major compatibility."""
    errors: list[str] = []
    protocol = payload.get("schema")
    if protocol != FINDING_BUNDLE_PROTOCOL:
        errors.append(
            f"unsupported artifact protocol: {protocol!r}; "
            f"expected {FINDING_BUNDLE_PROTOCOL!r}"
        )
    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, str):
        errors.append("schema_version must be a string")
    else:
        try:
            current_major = _major(FINDING_BUNDLE_SCHEMA_VERSION)
            incoming_major = _major(schema_version)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if incoming_major != current_major:
                errors.append(f"unsupported schema major version: {schema_version!r}")
    return CompatibilityResult(
        compatible=not errors,
        errors=tuple(errors),
    )
