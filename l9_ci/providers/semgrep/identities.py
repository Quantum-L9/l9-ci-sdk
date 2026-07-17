"""Deterministic Semgrep evidence and finding identities."""

from __future__ import annotations
import hashlib
import json
from typing import Any, Mapping
from l9_ci.contracts import SourceLocation


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_evidence_id(
    *,
    snapshot_id: str,
    provider_rule_id: str,
    location: SourceLocation,
    provider_fingerprint: str | None,
    message: str,
) -> str:
    discriminator = provider_fingerprint or message
    digest = _digest(
        {
            "snapshot_id": snapshot_id,
            "provider_id": "semgrep",
            "provider_rule_id": provider_rule_id,
            "path": location.normalized_path,
            "start_line": location.start_line,
            "start_column": location.start_column,
            "end_line": location.end_line,
            "end_column": location.end_column,
            "discriminator": discriminator,
        }
    )
    return f"ev_semgrep_{digest}"


def build_finding_fingerprint(
    *,
    provider_rule_id: str,
    location: SourceLocation,
    provider_fingerprint: str | None,
    message: str,
) -> str:
    return _digest(
        {
            "provider_id": "semgrep",
            "provider_rule_id": provider_rule_id,
            "path": location.normalized_path,
            "start_line": location.start_line,
            "start_column": location.start_column,
            "end_line": location.end_line,
            "end_column": location.end_column,
            "discriminator": provider_fingerprint or message,
        }
    )


def build_finding_id(
    *,
    snapshot_id: str,
    fingerprint: str,
) -> str:
    digest = _digest(
        {
            "snapshot_id": snapshot_id,
            "fingerprint": fingerprint,
        }
    )
    return f"fn_semgrep_{digest}"
