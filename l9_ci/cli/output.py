"""Machine-readable CLI output."""

from __future__ import annotations
import json
from enum import StrEnum
from typing import Any, Mapping


class OutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


def render_success(
    payload: Mapping[str, Any],
    *,
    output_format: OutputFormat,
) -> str:
    if output_format is OutputFormat.JSON:
        return json.dumps(
            {
                "ok": True,
                "result": dict(payload),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    return "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
