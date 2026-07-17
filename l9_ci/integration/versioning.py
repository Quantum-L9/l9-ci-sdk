"""SDK and artifact version negotiation."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True, order=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "SemanticVersion":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("version must be a non-empty string")
        normalized = value.strip().split("+", maxsplit=1)[0]
        normalized = normalized.split("-", maxsplit=1)[0]
        parts = normalized.split(".")
        if len(parts) != 3:
            raise ValueError(f"version must use major.minor.patch format: {value!r}")
        try:
            major, minor, patch = (int(part) for part in parts)
        except ValueError as exc:
            raise ValueError(f"invalid semantic version: {value!r}") from exc
        if min(major, minor, patch) < 0:
            raise ValueError("semantic version components must be non-negative")
        return cls(major=major, minor=minor, patch=patch)


@dataclass(frozen=True, slots=True)
class VersionNegotiationResult:
    compatible: bool
    SDK_version: str
    artifact_schema_version: str
    errors: tuple[str, ...]

    def require_compatible(self) -> None:
        if self.errors:
            joined = "\n".join(f"- {error}" for error in self.errors)
            raise ValueError(f"version negotiation failed:\n{joined}")


def negotiate_versions(
    payload: Mapping[str, Any],
    *,
    supported_artifact_major: int = 1,
    minimum_SDK_version: str | None = None,
) -> VersionNegotiationResult:
    errors: list[str] = []
    SDK_version_raw = payload.get("SDK_version")
    schema_version_raw = payload.get("schema_version")
    if not isinstance(SDK_version_raw, str):
        errors.append("SDK_version must be a string")
        SDK_version_raw = "0.0.0"
    if not isinstance(schema_version_raw, str):
        errors.append("schema_version must be a string")
        schema_version_raw = "0.0.0"
    try:
        SDK_version = SemanticVersion.parse(SDK_version_raw)
    except ValueError as exc:
        errors.append(str(exc))
        SDK_version = SemanticVersion(0, 0, 0)
    try:
        artifact_version = SemanticVersion.parse(schema_version_raw)
    except ValueError as exc:
        errors.append(str(exc))
        artifact_version = SemanticVersion(0, 0, 0)
    if artifact_version.major != supported_artifact_major:
        errors.append(
            f"unsupported artifact schema major version: {artifact_version.major}"
        )
    if minimum_SDK_version is not None:
        minimum = SemanticVersion.parse(minimum_SDK_version)
        if SDK_version < minimum:
            errors.append(
                f"SDK version {SDK_version_raw} is older than required "
                f"{minimum_SDK_version}"
            )
    return VersionNegotiationResult(
        compatible=not errors,
        SDK_version=SDK_version_raw,
        artifact_schema_version=schema_version_raw,
        errors=tuple(errors),
    )
