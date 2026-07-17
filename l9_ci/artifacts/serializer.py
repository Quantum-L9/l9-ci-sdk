"""Deterministic canonical JSON serialization."""

from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping
from l9_ci.contracts import FindingBundle


def canonicalize(value: Any) -> Any:
    """Recursively produce a canonical JSON-compatible structure."""
    if isinstance(value, Mapping):
        return {str(key): canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, tuple | list):
        return [canonicalize(item) for item in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a value as canonical UTF-8 JSON.
    The output is deterministic for the same logical input.
    """
    canonical = canonicalize(value)
    return (
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def bundle_bytes(bundle: FindingBundle) -> bytes:
    """Serialize a finding bundle deterministically."""
    payload = bundle.to_dict()
    payload["providers"] = sorted(
        payload["providers"],
        key=lambda item: (
            item["provider_id"],
            item["adapter_version"],
            item["mode"],
        ),
    )
    payload["evidence"] = sorted(
        payload["evidence"],
        key=lambda item: item["evidence_id"],
    )
    payload["findings"] = sorted(
        payload["findings"],
        key=lambda item: item["finding_id"],
    )
    payload["classifications"] = sorted(
        payload["classifications"],
        key=lambda item: item["finding_id"],
    )
    payload["provider_failures"] = sorted(
        payload["provider_failures"],
        key=lambda item: (
            item["provider_id"],
            item["failure_type"],
            item["message"],
        ),
    )
    payload["coverage"] = sorted(
        payload["coverage"],
        key=lambda item: item["provider_id"],
    )
    payload["limitations"] = sorted(payload["limitations"])
    return canonical_json_bytes(payload)


def write_bundle_atomic(bundle: FindingBundle, destination: Path) -> None:
    """Write a bundle atomically."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = bundle_bytes(bundle)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
