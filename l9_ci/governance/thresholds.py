"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
layer: [governance, thresholds]
tags: [L9_CI, thresholds, policy, fail-closed]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BOOTSTRAP_DEFAULT_COVERAGE = 80
BOOTSTRAP_SDK_COVERAGE = 85
BOOTSTRAP_CORE_COVERAGE = 80


@dataclass(frozen=True)
class ThresholdPolicy:
    default_coverage: int
    package_coverage: dict[str, int]
    minimum_floor: int
    max_critical_findings: int
    max_high_findings: int
    rule_modes: dict[str, str]

    def coverage_for(self, package: str | None = None) -> int:
        if package and package in self.package_coverage:
            return self.package_coverage[package]
        return self.default_coverage


class ThresholdPolicyError(ValueError):
    """Raised when threshold policy is missing or malformed."""


VALID_RULE_MODES = {"blocking", "advisory", "shadow", "disabled"}


def bootstrap_policy() -> ThresholdPolicy:
    """Return rock-bottom policy for init-repo only, never normal CI."""
    return ThresholdPolicy(
        default_coverage=BOOTSTRAP_DEFAULT_COVERAGE,
        package_coverage={"l9_ci_sdk": BOOTSTRAP_SDK_COVERAGE, "l9_ci_core": BOOTSTRAP_CORE_COVERAGE},
        minimum_floor=BOOTSTRAP_DEFAULT_COVERAGE,
        max_critical_findings=0,
        max_high_findings=0,
        rule_modes={
            "transport_packet_contract": "blocking",
            "direct_node_dispatch": "advisory",
            "handler_signature": "advisory",
            "pii_logging": "advisory",
        },
    )


def load_threshold_policy(path: Path, *, bootstrap_mode: bool = False) -> ThresholdPolicy:
    if not path.exists():
        if bootstrap_mode:
            return bootstrap_policy()
        raise ThresholdPolicyError(f"threshold policy missing: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ThresholdPolicyError(f"threshold policy malformed YAML: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ThresholdPolicyError("threshold policy must be a YAML mapping")
    return parse_threshold_policy(raw)


def parse_threshold_policy(raw: dict[str, Any]) -> ThresholdPolicy:
    coverage = raw.get("coverage")
    security = raw.get("security")
    rule_modes = raw.get("rule_modes")
    if not isinstance(coverage, dict):
        raise ThresholdPolicyError("coverage must be a mapping")
    if not isinstance(security, dict):
        raise ThresholdPolicyError("security must be a mapping")
    if not isinstance(rule_modes, dict):
        raise ThresholdPolicyError("rule_modes must be a mapping")

    minimum_floor = _int_at_least(coverage, "minimum_floor", 80)
    default = _int_at_least(coverage, "default", minimum_floor)
    if default < minimum_floor:
        raise ThresholdPolicyError("coverage.default cannot be below coverage.minimum_floor")

    packages: dict[str, int] = {}
    for key, value in coverage.items():
        if key in {"default", "minimum_floor", "allow_repo_override", "override_requires"}:
            continue
        if isinstance(value, int):
            if value < minimum_floor:
                raise ThresholdPolicyError(f"coverage.{key} cannot be below coverage.minimum_floor")
            packages[key] = value

    max_critical = _int_at_least(security, "max_critical_findings", 0)
    max_high = _int_at_least(security, "max_high_findings", 0)
    modes: dict[str, str] = {}
    for rule_id, mode in rule_modes.items():
        if not isinstance(rule_id, str) or not isinstance(mode, str):
            raise ThresholdPolicyError("rule_modes keys and values must be strings")
        if mode not in VALID_RULE_MODES:
            raise ThresholdPolicyError(f"invalid rule mode for {rule_id}: {mode}")
        modes[rule_id] = mode

    return ThresholdPolicy(
        default_coverage=default,
        package_coverage=packages,
        minimum_floor=minimum_floor,
        max_critical_findings=max_critical,
        max_high_findings=max_high,
        rule_modes=modes,
    )


def _int_at_least(mapping: dict[str, Any], key: str, minimum: int) -> int:
    value = mapping.get(key)
    if not isinstance(value, int):
        raise ThresholdPolicyError(f"{key} must be an integer")
    if value < minimum:
        raise ThresholdPolicyError(f"{key} must be >= {minimum}")
    return value


def format_threshold_policy(policy: ThresholdPolicy) -> str:
    lines = [
        "L9 threshold policy valid",
        f"  default coverage: {policy.default_coverage}",
        f"  minimum floor: {policy.minimum_floor}",
        f"  max critical findings: {policy.max_critical_findings}",
        f"  max high findings: {policy.max_high_findings}",
    ]
    for package, threshold in sorted(policy.package_coverage.items()):
        lines.append(f"  coverage {package}: {threshold}")
    return "\n".join(lines)
