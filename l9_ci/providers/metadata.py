"""Provider metadata contracts."""

from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ProviderState(StrEnum):
    UNSUPPORTED = "unsupported"
    PROPOSED = "proposed"
    EXPERIMENTAL = "experimental"
    SHADOW = "shadow"
    SUPPORTED = "supported"
    DEPRECATED = "deprecated"


class NetworkRequirement(StrEnum):
    NEVER = "never"
    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    """Stable metadata describing an SDK provider adapter."""

    provider_id: str
    display_name: str
    adapter_version: str
    state: ProviderState
    supported_report_formats: tuple[str, ...]
    execution_support: bool
    import_support: bool
    network_requirement: NetworkRequirement
    default_required: bool

    def __post_init__(self) -> None:
        for field_name in ("provider_id", "display_name", "adapter_version"):
            value = getattr(self, field_name)
            if not value.strip():
                raise ValueError(f"{field_name} must be non-empty")
        if not self.execution_support and not self.import_support:
            raise ValueError("provider must support execution, import, or both")
        object.__setattr__(
            self,
            "supported_report_formats",
            tuple(self.supported_report_formats),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "adapter_version": self.adapter_version,
            "state": self.state.value,
            "supported_report_formats": list(self.supported_report_formats),
            "execution_support": self.execution_support,
            "import_support": self.import_support,
            "network_requirement": self.network_requirement.value,
            "default_required": self.default_required,
        }
