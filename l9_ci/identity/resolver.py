"""Explicit canonical rule identity resolution."""

from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping
import yaml


class IdentityResolutionStatus(StrEnum):
    TRUSTED_METADATA = "trusted_metadata"
    EXPLICIT_MAPPING = "explicit_mapping"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    """Result of canonical rule identity resolution."""

    provider_id: str
    provider_rule_id: str
    canonical_rule_id: str | None
    status: IdentityResolutionStatus
    mapping_version: str | None = None

    @property
    def resolved(self) -> bool:
        return self.canonical_rule_id is not None


@dataclass(frozen=True, slots=True)
class RuleIdentityMap:
    """Versioned provider-rule to canonical-rule mapping."""

    provider_id: str
    version: str
    rules: Mapping[str, str]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RuleIdentityMap":
        if payload.get("schema") != "l9.identity-map/v1":
            raise ValueError("unsupported identity map schema")
        metadata = payload.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ValueError("identity map metadata must be an object")
        provider_id = metadata.get("provider_id")
        version = metadata.get("version")
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("identity map provider_id must be non-empty")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("identity map version must be non-empty")
        raw_rules = payload.get("rules", {})
        if not isinstance(raw_rules, Mapping):
            raise ValueError("identity map rules must be an object")
        rules: dict[str, str] = {}
        for provider_rule_id, entry in raw_rules.items():
            if not isinstance(provider_rule_id, str) or not provider_rule_id:
                raise ValueError("identity-map rule IDs must be strings")
            if not isinstance(entry, Mapping):
                raise ValueError(
                    f"identity-map entry {provider_rule_id!r} must be an object"
                )
            canonical_rule_id = entry.get("canonical_rule_id")
            if not isinstance(canonical_rule_id, str) or not canonical_rule_id:
                raise ValueError(
                    f"identity-map entry {provider_rule_id!r} requires "
                    "canonical_rule_id"
                )
            rules[provider_rule_id] = canonical_rule_id
        return cls(
            provider_id=provider_id,
            version=version,
            rules=rules,
        )

    @classmethod
    def load(cls, path: Path) -> "RuleIdentityMap":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("identity map root must be an object")
        return cls.from_dict(payload)


def resolve_rule_identity(
    *,
    provider_id: str,
    provider_rule_id: str,
    trusted_canonical_rule_id: str | None,
    identity_map: RuleIdentityMap | None,
) -> IdentityResolution:
    """Resolve identity without synthesizing a canonical rule ID.
    Trusted provider metadata has priority over an external versioned map.
    """
    if trusted_canonical_rule_id:
        return IdentityResolution(
            provider_id=provider_id,
            provider_rule_id=provider_rule_id,
            canonical_rule_id=trusted_canonical_rule_id,
            status=IdentityResolutionStatus.TRUSTED_METADATA,
        )
    if identity_map is not None:
        if identity_map.provider_id != provider_id:
            raise ValueError("identity map provider does not match finding provider")
        mapped = identity_map.rules.get(provider_rule_id)
        if mapped:
            return IdentityResolution(
                provider_id=provider_id,
                provider_rule_id=provider_rule_id,
                canonical_rule_id=mapped,
                status=IdentityResolutionStatus.EXPLICIT_MAPPING,
                mapping_version=identity_map.version,
            )
    return IdentityResolution(
        provider_id=provider_id,
        provider_rule_id=provider_rule_id,
        canonical_rule_id=None,
        status=IdentityResolutionStatus.UNRESOLVED,
    )
