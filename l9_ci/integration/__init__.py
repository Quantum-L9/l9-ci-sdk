"""Public Core-integration surface."""

from .agent_payload import (
    AGENT_REVIEW_PAYLOAD_PROTOCOL,
    AGENT_REVIEW_PAYLOAD_SCHEMA_VERSION,
    AgentFinding,
    AgentReviewPayload,
)
from .limits import (
    OperationalLimits,
    validate_record_counts,
    validate_report_size,
)
from .projection import project_agent_review_payload
from .redaction import RedactionResult, validate_redaction
from .versioning import (
    SemanticVersion,
    VersionNegotiationResult,
    negotiate_versions,
)

__all__ = [
    "AGENT_REVIEW_PAYLOAD_PROTOCOL",
    "AGENT_REVIEW_PAYLOAD_SCHEMA_VERSION",
    "AgentFinding",
    "AgentReviewPayload",
    "OperationalLimits",
    "RedactionResult",
    "SemanticVersion",
    "VersionNegotiationResult",
    "negotiate_versions",
    "project_agent_review_payload",
    "validate_record_counts",
    "validate_redaction",
    "validate_report_size",
]
