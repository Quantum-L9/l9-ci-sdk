"""Baseline-ratchet kernel: contracts, fingerprints, comparator, adapters.

Deterministic, fail-closed debt governance. No LLM participates in any
decision path in this package.
"""

from .comparator import compare, load_entries_strict
from .comparison import (
    COMPARISON_SCHEMA_VERSION,
    BaselineComparison,
    BaselineSummary,
    BaselineViolation,
    FindingStatus,
    ObservedFinding,
    ViolationKind,
    sort_violations,
)
from .fingerprint import (
    compute_fingerprint,
    normalize_failure_text,
    scanner_finding_fingerprint,
    fingerprint_for_test_failure,
)
from .ledger import LoadedLedger, load_ledger, load_rule_waivers
from .packet_envelope import (
    PACKET_ENVELOPE_GATE,
    PACKET_ENVELOPE_RULE,
    PacketEnvelopeUsage,
    scan_file,
    scan_repository,
)
from .pytest_adapter import PYTEST_GATE, PytestRunResult, parse_report_log
from .schemas import (
    BASELINE_SCHEMA_VERSION,
    BaselineEntry,
    RemovalCondition,
    RuleWaiverEntry,
    TestQuarantineEntry,
    utc_today,
)

__all__ = [
    "BASELINE_SCHEMA_VERSION",
    "COMPARISON_SCHEMA_VERSION",
    "PACKET_ENVELOPE_GATE",
    "PACKET_ENVELOPE_RULE",
    "PYTEST_GATE",
    "BaselineComparison",
    "BaselineEntry",
    "BaselineSummary",
    "BaselineViolation",
    "FindingStatus",
    "LoadedLedger",
    "ObservedFinding",
    "PacketEnvelopeUsage",
    "PytestRunResult",
    "RemovalCondition",
    "RuleWaiverEntry",
    "TestQuarantineEntry",
    "ViolationKind",
    "compare",
    "compute_fingerprint",
    "load_entries_strict",
    "load_ledger",
    "load_rule_waivers",
    "normalize_failure_text",
    "parse_report_log",
    "scan_file",
    "scan_repository",
    "scanner_finding_fingerprint",
    "sort_violations",
    "fingerprint_for_test_failure",
    "utc_today",
]
