"""Structured CLI diagnostics."""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Mapping
from .output import OutputFormat


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    details: Mapping[str, Any]

    def render(self, output_format: OutputFormat) -> str:
        if output_format is OutputFormat.JSON:
            return json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": self.code,
                        "message": self.message,
                        "details": dict(self.details),
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        return f"error[{self.code}]: {self.message}"
