"""
L9_META
l9_schema: 1
origin: l9-ci-universal-base
layer: [sdk, governance, rule-modes]
tags: [L9_TEMPLATE, rule-modes, shadow-mode, advisory, blocking]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

RuleMode = Literal["blocking", "advisory", "shadow", "disabled"]
VALID_RULE_MODES: set[str] = {"blocking", "advisory", "shadow", "disabled"}
DEFAULT_POLICY_PATH = Path(".github/governance/rule-modes.yaml")


class RuleModePolicyError(ValueError):
    """Raised when rule-mode policy cannot be trusted."""


@dataclass(frozen=True)
class RuleModePolicy:
    version: int
    default_mode: RuleMode
    rules: dict[str, RuleMode]
    promotion: dict[str, Any]
    source: Path

    def mode_for(self, rule_id: str, *, fallback: RuleMode | None = None) -> RuleMode:
        candidates = [rule_id, rule_id.lower(), rule_id.replace("-", "_"), rule_id.upper()]
        for candidate in candidates:
            if candidate in self.rules:
                return self.rules[candidate]
        return fallback or self.default_mode


def _as_mapping(payload: Any, path: Path) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuleModePolicyError(f"Rule-mode policy must be a mapping: {path}")
    return payload


def _parse_mode(value: Any, *, path: Path, key: str) -> RuleMode:
    mode = str(value).strip().lower()
    if mode not in VALID_RULE_MODES:
        raise RuleModePolicyError(f"Invalid rule mode for {key!r} in {path}: {value!r}")
    return mode  # type: ignore[return-value]


def load_rule_mode_policy(path: Path = DEFAULT_POLICY_PATH) -> RuleModePolicy:
    path = path.resolve()
    if not path.exists():
        raise RuleModePolicyError(f"Missing rule-mode policy: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuleModePolicyError(f"Malformed rule-mode policy YAML: {path}: {exc}") from exc
    data = _as_mapping(payload, path)
    version = data.get("version")
    if not isinstance(version, int) or version < 1:
        raise RuleModePolicyError(f"Rule-mode policy requires integer version >= 1: {path}")
    default_mode = _parse_mode(data.get("default_mode", "blocking"), path=path, key="default_mode")
    raw_rules = data.get("rules")
    if not isinstance(raw_rules, dict) or not raw_rules:
        raise RuleModePolicyError(f"Rule-mode policy requires non-empty rules mapping: {path}")
    rules: dict[str, RuleMode] = {}
    for key, value in raw_rules.items():
        if not isinstance(key, str) or not key.strip():
            raise RuleModePolicyError(f"Rule-mode policy contains invalid rule id: {key!r}")
        rules[key.strip()] = _parse_mode(value, path=path, key=key)
    promotion = data.get("promotion")
    if promotion is None:
        promotion = {}
    if not isinstance(promotion, dict):
        raise RuleModePolicyError(f"Rule-mode promotion block must be a mapping: {path}")
    return RuleModePolicy(version=version, default_mode=default_mode, rules=rules, promotion=promotion, source=path)


def apply_rule_modes_to_findings(findings: list[dict[str, Any]], policy: RuleModePolicy) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for finding in findings:
        copy = dict(finding)
        rule_id = str(copy.get("rule_id") or copy.get("rule") or "UNKNOWN")
        existing = copy.get("mode")
        fallback: RuleMode | None = None
        if isinstance(existing, str) and existing.lower() in VALID_RULE_MODES:
            fallback = existing.lower()  # type: ignore[assignment]
        copy["mode"] = policy.mode_for(rule_id, fallback=fallback)
        normalized.append(copy)
    return normalized


def finding_blocks(finding: dict[str, Any]) -> bool:
    return str(finding.get("mode") or "blocking").lower() == "blocking"


def format_rule_mode_policy(policy: RuleModePolicy) -> str:
    lines = [f"Rule-mode policy: {policy.source}", f"version: {policy.version}", f"default_mode: {policy.default_mode}"]
    for rule_id in sorted(policy.rules):
        lines.append(f"  {rule_id}: {policy.rules[rule_id]}")
    return "\n".join(lines)
