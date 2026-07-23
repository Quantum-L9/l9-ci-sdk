"""Deterministic finding fingerprints.

Fingerprints are SHA-256 digests over canonical, volatile-free
components. They exclude timestamps, absolute paths, line numbers,
memory addresses, stack-frame offsets, and any environment-specific
value, so that the same logical finding produces the same fingerprint
on every machine and every run.
"""

from __future__ import annotations

import hashlib
import re

_FIELD_SEPARATOR = "\x1f"

_HEX_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")
_MEMORY_OBJECT = re.compile(r"<([\w.]+) object at 0x[0-9a-fA-F]+>")
_LINE_REFERENCE = re.compile(r"(?:, line |:)\d+")
_TMP_PATH = re.compile(r"/(?:tmp|var/folders|private/tmp)/[^\s'\"]+")
_HOME_PATH = re.compile(r"/(?:home|Users)/[\w.-]+")
_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_DURATION = re.compile(r"\b\d+(?:\.\d+)?\s*(?:s|ms|us|ns|seconds?|minutes?)\b")
_PORT_NUMBER = re.compile(r"(?:localhost|127\.0\.0\.1):\d+")
_WHITESPACE = re.compile(r"\s+")
_LONG_NUMBER = re.compile(r"\b\d{5,}\b")
# Bare hex tokens of 16+ chars (no dashes, no 0x prefix): run-random
# object IDs (e.g. ContractViolation[gs_<32hex>]), content hashes, and
# digests embedded in failure messages. Without this, fingerprints for
# such failures churn on every run.
_BARE_HEX_TOKEN = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{16,64}(?![0-9a-fA-F])"
)


def normalize_failure_text(text: str) -> str:
    """Strip volatile values from a failure message or signature."""
    value = text.strip()
    value = _MEMORY_OBJECT.sub(r"<\1 object at 0xADDR>", value)
    value = _HEX_ADDRESS.sub("0xADDR", value)
    value = _UUID.sub("UUID", value)
    value = _TIMESTAMP.sub("TIMESTAMP", value)
    value = _TMP_PATH.sub("/TMPPATH", value)
    value = _HOME_PATH.sub("/HOMEPATH", value)
    value = _PORT_NUMBER.sub("HOST:PORT", value)
    value = _DURATION.sub("DURATION", value)
    value = _LINE_REFERENCE.sub(":LINE", value)
    value = _BARE_HEX_TOKEN.sub("HEX", value)
    value = _LONG_NUMBER.sub("NUM", value)
    value = _WHITESPACE.sub(" ", value)
    return value.strip()


def compute_fingerprint(*components: str) -> str:
    """Compute a stable SHA-256 fingerprint over ordered components.

    Components are joined with an unambiguous separator so that
    ("ab", "c") and ("a", "bc") never collide.
    """
    if not components:
        raise ValueError("fingerprint requires at least one component")
    for component in components:
        if not isinstance(component, str):
            raise ValueError("fingerprint components must be strings")
    joined = _FIELD_SEPARATOR.join(components)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def fingerprint_for_test_failure(
    test_node_id: str,
    exception_type: str,
    failure_signature: str,
) -> str:
    """Fingerprint a failing test node.

    Components: test node ID + normalized exception type + normalized
    failure signature. Line numbers and volatile values are excluded
    by normalization.
    """
    if not test_node_id.strip():
        raise ValueError("test_node_id must not be empty")
    if not exception_type.strip():
        raise ValueError("exception_type must not be empty")
    return compute_fingerprint(
        "test",
        test_node_id.strip(),
        exception_type.strip(),
        normalize_failure_text(failure_signature),
    )


def scanner_finding_fingerprint(
    rule_id: str,
    repository_path: str,
    normalized_usage: str,
) -> str:
    """Fingerprint a scanner finding.

    Components: rule ID + repository-relative path + normalized
    AST-level usage. Line numbers are deliberately excluded so that
    unrelated edits to a file do not churn fingerprints.
    """
    if not rule_id.strip():
        raise ValueError("rule_id must not be empty")
    if not repository_path.strip():
        raise ValueError("repository_path must not be empty")
    if not normalized_usage.strip():
        raise ValueError("normalized_usage must not be empty")
    return compute_fingerprint(
        "scanner",
        rule_id.strip(),
        repository_path.strip(),
        normalize_failure_text(normalized_usage),
    )
