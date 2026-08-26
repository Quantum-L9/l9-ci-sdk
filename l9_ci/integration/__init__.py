"""Public Core and Assurance integration surface."""

from .agent_payload import (
    AGENT_REVIEW_PAYLOAD_PROTOCOL,
    AGENT_REVIEW_PAYLOAD_SCHEMA_VERSION,
    AgentFinding,
    AgentReviewPayload,
)
from .limits import OperationalLimits, validate_record_counts, validate_report_size
from .observation import (
    EXECUTION_STATUSES,
    OBSERVATION_PROTOCOL,
    OBSERVATION_SCHEMA_VERSION,
    SUPPORTED_OBSERVATION_CHECKS,
    build_observation,
    project_mandatory_findings_observation,
    validate_observation,
)
from .projection import project_agent_review_payload
from .redaction import RedactionResult, validate_redaction
from .sarif import (
    SARIF_LOG_SUBSET_SCHEMA,
    SARIF_SCHEMA_URI,
    SARIF_VERSION,
    project_sarif_log,
)
from .versioning import VersionNegotiationResult, negotiate_versions

from l9_ci.contracts import SemanticVersion

__all__ = [
    "AGENT_REVIEW_PAYLOAD_PROTOCOL",
    "AGENT_REVIEW_PAYLOAD_SCHEMA_VERSION",
    "AgentFinding",
    "AgentReviewPayload",
    "EXECUTION_STATUSES",
    "OBSERVATION_PROTOCOL",
    "OBSERVATION_SCHEMA_VERSION",
    "OperationalLimits",
    "RedactionResult",
    "SARIF_LOG_SUBSET_SCHEMA",
    "SARIF_SCHEMA_URI",
    "SARIF_VERSION",
    "SUPPORTED_OBSERVATION_CHECKS",
    "SemanticVersion",
    "VersionNegotiationResult",
    "build_observation",
    "negotiate_versions",
    "project_agent_review_payload",
    "project_mandatory_findings_observation",
    "project_sarif_log",
    "validate_observation",
    "validate_record_counts",
    "validate_redaction",
    "validate_report_size",
]
