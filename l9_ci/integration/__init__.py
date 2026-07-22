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
    VersionNegotiationResult,
    negotiate_versions,
)

# Deprecated compatibility re-export (AUD-001). SemanticVersion's canonical
# public home is l9_ci.contracts; it originally shipped here and was moved in
# 65715d0 without an alias, silently breaking existing importers. The alias is
# registered in .l9/public-api.yaml compatibility_allowlist and is removed via
# the versioned process in .l9/compatibility.yaml — import from
# l9_ci.contracts instead.
from l9_ci.contracts import SemanticVersion

__all__ = [
    "AGENT_REVIEW_PAYLOAD_PROTOCOL",
    "AGENT_REVIEW_PAYLOAD_SCHEMA_VERSION",
    "AgentFinding",
    "AgentReviewPayload",
    "OperationalLimits",
    "RedactionResult",
    "SemanticVersion",  # deprecated alias — see compatibility_allowlist
    "VersionNegotiationResult",
    "negotiate_versions",
    "project_agent_review_payload",
    "validate_record_counts",
    "validate_redaction",
    "validate_report_size",
]
