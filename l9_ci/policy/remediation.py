"""Trusted canonical-rule → remediation-class producer (DWA-007).

The agent-review projection only emits autofix candidates for findings whose
``remediation_class`` is ``safe-autofix`` or ``mechanical``, but nothing ever
set that field on the active path, so ``autofix_candidates`` was always empty.

This adds a versioned, trusted mapping keyed by **canonical** rule identity, so a
remediation class is assigned only after canonical identity resolution — never
inferred from scanner metadata (AGENTS.md prohibits deriving autofix eligibility
from severity or scanner fields). The mapping is data supplied by a repository
policy file; the SDK ships no built-in classifications (populating real
safe-autofix rules is an explicit owner decision, like the runtime fixture).
"""

from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping
import yaml
from l9_ci.contracts import Finding

# The only remediation classes the projection treats as autofix-eligible. A
# mapping may only assign these values, so a typo cannot silently disable a fix
# or invent an unknown class.
ALLOWED_REMEDIATION_CLASSES = frozenset({"safe-autofix", "mechanical"})


@dataclass(frozen=True, slots=True)
class RemediationMap:
    """Versioned canonical-rule-id → remediation-class mapping."""

    version: str
    mappings: Mapping[str, str]

    def __post_init__(self) -> None:
        invalid = {
            value
            for value in self.mappings.values()
            if value not in ALLOWED_REMEDIATION_CLASSES
        }
        if invalid:
            raise ValueError(
                "remediation map contains classes outside "
                f"{sorted(ALLOWED_REMEDIATION_CLASSES)}: {sorted(invalid)}"
            )

    @classmethod
    def empty(cls) -> "RemediationMap":
        return cls(version="0", mappings={})

    @classmethod
    def load(cls, path: Path) -> "RemediationMap":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        metadata = data.get("metadata", {})
        rules = data.get("rules", {}) or {}
        mappings = {
            str(canonical_rule_id): str(entry["remediation_class"])
            for canonical_rule_id, entry in rules.items()
            if isinstance(entry, Mapping) and "remediation_class" in entry
        }
        return cls(version=str(metadata.get("version", "0")), mappings=mappings)

    def remediation_for(self, canonical_rule_id: str | None) -> str | None:
        if canonical_rule_id is None:
            return None
        return self.mappings.get(canonical_rule_id)


def apply_remediation_classes(
    findings: tuple[Finding, ...],
    remediation_map: RemediationMap,
) -> tuple[Finding, ...]:
    """Set remediation_class on findings whose canonical rule id is trusted-mapped."""
    result: list[Finding] = []
    for finding in findings:
        remediation_class = remediation_map.remediation_for(finding.canonical_rule_id)
        if remediation_class is not None:
            result.append(replace(finding, remediation_class=remediation_class))
        else:
            result.append(finding)
    return tuple(result)
