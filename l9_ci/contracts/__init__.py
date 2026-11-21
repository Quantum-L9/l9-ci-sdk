"""Public canonical contract surface for l9-ci-sdk."""

from .bundle import (
    FINDING_BUNDLE_PROTOCOL,
    FINDING_BUNDLE_SCHEMA_VERSION,
    FindingBundle,
    ProviderRun,
    SnapshotDescriptor,
)
from .classification import (
    BaselineStatus,
    FindingClassification,
    ResolutionStatus,
    RuleMode,
)
from .coverage import Coverage, CoverageStatus
from .evidence import Confidence, EvidenceRecord, Severity
from .failure import ProviderFailure, ProviderFailureType
from .finding import Finding
from .source import SourceLocation, normalize_repository_path
from .subjects import SUBJECT_CAP, cap_subjects, format_subjects, subject_reason
from .version import SemanticVersion

__all__ = [
    "BaselineStatus",
    "Confidence",
    "Coverage",
    "CoverageStatus",
    "EvidenceRecord",
    "FINDING_BUNDLE_PROTOCOL",
    "FINDING_BUNDLE_SCHEMA_VERSION",
    "Finding",
    "FindingBundle",
    "FindingClassification",
    "ProviderFailure",
    "ProviderFailureType",
    "ProviderRun",
    "ResolutionStatus",
    "RuleMode",
    "SemanticVersion",
    "Severity",
    "SnapshotDescriptor",
    "SourceLocation",
    "SUBJECT_CAP",
    "cap_subjects",
    "format_subjects",
    "normalize_repository_path",
    "subject_reason",
]
