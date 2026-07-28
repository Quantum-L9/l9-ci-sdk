"""Provider failure contracts."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class ProviderFailureType(StrEnum):
    NOT_INSTALLED = "not_installed"
    UNSUPPORTED_VERSION = "unsupported_version"
    CONFIGURATION_ERROR = "configuration_error"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    REPORT_MISSING = "report_missing"
    REPORT_MALFORMED = "report_malformed"
    REPORT_UNSUPPORTED = "report_unsupported"
    NORMALIZATION_ERROR = "normalization_error"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    """A structured provider acquisition or normalization failure."""

    provider_id: str
    failure_type: ProviderFailureType
    message: str
    required: bool
    fatal: bool
    provider_version: str | None = None
    report_path: str | None = None
    exit_code: int | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must be non-empty")
        if not self.message.strip():
            raise ValueError("message must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "provider_id": self.provider_id,
            "failure_type": self.failure_type.value,
            "message": self.message,
            "required": self.required,
            "fatal": self.fatal,
            "diagnostics": dict(self.diagnostics),
        }
        optional_values = {
            "provider_version": self.provider_version,
            "report_path": self.report_path,
            "exit_code": self.exit_code,
        }
        for key, value in optional_values.items():
            if value is not None:
                payload[key] = value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ProviderFailure":
        return cls(
            provider_id=str(payload["provider_id"]),
            failure_type=ProviderFailureType(str(payload["failure_type"])),
            message=str(payload["message"]),
            required=bool(payload["required"]),
            fatal=bool(payload["fatal"]),
            provider_version=payload.get("provider_version"),
            report_path=payload.get("report_path"),
            exit_code=payload.get("exit_code"),
            diagnostics=dict(payload.get("diagnostics", {})),
        )
