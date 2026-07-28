"""Agent-review payload contracts."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

AGENT_REVIEW_PAYLOAD_PROTOCOL = "l9.agent-review-projection/v1"
AGENT_REVIEW_PAYLOAD_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class AgentFinding:
    finding_id: str
    provider_id: str
    provider_rule_id: str
    canonical_rule_id: str | None
    policy_key: str | None
    severity: str | None
    category: str
    message: str
    fingerprint: str
    locations: tuple[Mapping[str, Any], ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "finding_id": self.finding_id,
            "provider_id": self.provider_id,
            "provider_rule_id": self.provider_rule_id,
            "category": self.category,
            "message": self.message,
            "fingerprint": self.fingerprint,
            "locations": [dict(location) for location in self.locations],
            "limitations": list(self.limitations),
        }
        if self.canonical_rule_id is not None:
            payload["canonical_rule_id"] = self.canonical_rule_id
        if self.policy_key is not None:
            payload["policy_key"] = self.policy_key
        if self.severity is not None:
            payload["severity"] = self.severity
        return payload


@dataclass(frozen=True, slots=True)
class AgentReviewPayload:
    SDK_version: str
    source_bundle_schema: str
    source_bundle_schema_version: str
    snapshot_id: str
    blocking_findings: tuple[AgentFinding, ...]
    advisory_findings: tuple[AgentFinding, ...]
    shadow_findings: tuple[AgentFinding, ...]
    unresolved_findings: tuple[AgentFinding, ...]
    disabled_findings: tuple[AgentFinding, ...]
    autofix_candidates: tuple[AgentFinding, ...]
    provider_failures: tuple[Mapping[str, Any], ...]
    coverage: tuple[Mapping[str, Any], ...]
    limitations: tuple[str, ...]
    schema: str = AGENT_REVIEW_PAYLOAD_PROTOCOL
    schema_version: str = AGENT_REVIEW_PAYLOAD_SCHEMA_VERSION

    def summary(self) -> dict[str, int]:
        return {
            "blocking_count": len(self.blocking_findings),
            "advisory_count": len(self.advisory_findings),
            "shadow_count": len(self.shadow_findings),
            "unresolved_count": len(self.unresolved_findings),
            "disabled_count": len(self.disabled_findings),
            "autofix_candidate_count": len(self.autofix_candidates),
            "provider_failure_count": len(self.provider_failures),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "SDK_version": self.SDK_version,
            "source_bundle_schema": self.source_bundle_schema,
            "source_bundle_schema_version": self.source_bundle_schema_version,
            "snapshot_id": self.snapshot_id,
            "blocking_findings": [item.to_dict() for item in self.blocking_findings],
            "advisory_findings": [item.to_dict() for item in self.advisory_findings],
            "shadow_findings": [item.to_dict() for item in self.shadow_findings],
            "unresolved_findings": [
                item.to_dict() for item in self.unresolved_findings
            ],
            "disabled_findings": [item.to_dict() for item in self.disabled_findings],
            "autofix_candidates": [item.to_dict() for item in self.autofix_candidates],
            "provider_failures": [dict(item) for item in self.provider_failures],
            "coverage": [dict(item) for item in self.coverage],
            "limitations": list(self.limitations),
            "summary": self.summary(),
        }
