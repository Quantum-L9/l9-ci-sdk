"""Finding policy configuration models."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import yaml
from l9_ci.contracts import RuleMode


@dataclass(frozen=True, slots=True)
class PolicyRule:
    provider_rule_id: str
    policy_key: str
    mode: RuleMode


@dataclass(frozen=True, slots=True)
class FindingPolicy:
    version: str
    default_mode: RuleMode
    rules: Mapping[str, PolicyRule]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FindingPolicy":
        if payload.get("schema") != "l9.finding-policy/v1":
            raise ValueError("unsupported finding policy schema")
        metadata = payload.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ValueError("policy metadata must be an object")
        version = metadata.get("version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("policy version must be non-empty")
        defaults = payload.get("defaults", {})
        if not isinstance(defaults, Mapping):
            raise ValueError("policy defaults must be an object")
        default_mode = RuleMode(str(defaults.get("mode", RuleMode.UNRESOLVED.value)))
        raw_rules = payload.get("rules", {})
        if not isinstance(raw_rules, Mapping):
            raise ValueError("policy rules must be an object")
        rules: dict[str, PolicyRule] = {}
        for provider_rule_id, entry in raw_rules.items():
            if not isinstance(provider_rule_id, str) or not provider_rule_id:
                raise ValueError("policy rule IDs must be non-empty strings")
            if not isinstance(entry, Mapping):
                raise ValueError(f"policy rule {provider_rule_id!r} must be an object")
            policy_key = entry.get("policy_key")
            if not isinstance(policy_key, str) or not policy_key.strip():
                raise ValueError(
                    f"policy rule {provider_rule_id!r} requires policy_key"
                )
            mode_raw = entry.get("mode")
            if not isinstance(mode_raw, str):
                raise ValueError(f"policy rule {provider_rule_id!r} requires mode")
            rules[provider_rule_id] = PolicyRule(
                provider_rule_id=provider_rule_id,
                policy_key=policy_key,
                mode=RuleMode(mode_raw),
            )
        return cls(
            version=version,
            default_mode=default_mode,
            rules=rules,
        )

    @classmethod
    def load(cls, path: Path) -> "FindingPolicy":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("policy root must be an object")
        return cls.from_dict(payload)
