"""Canonical semantic-version value type.

``SemanticVersion`` lives in the contracts layer because it is a low-level
value object shared by both the integration layer (SDK/artifact version
negotiation) and the providers layer (provider version policy). Placing it here
keeps the providers layer from depending upward on integration, which the
architecture forbids (see .l9/architecture.yaml layers.providers).
"""

from __future__ import annotations
from dataclasses import dataclass


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
