"""Public provider extension surface."""

from .metadata import (
    NetworkRequirement,
    ProviderMetadata,
    ProviderState,
)
from .registry import ProviderRegistry
from .spi import (
    Provider,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderNormalizationContext,
    ProviderNormalizationResult,
)
from .semgrep import SemgrepProvider
from .defaults import build_default_registry

__all__ = [
    "NetworkRequirement",
    "Provider",
    "ProviderExecutionRequest",
    "ProviderExecutionResult",
    "ProviderMetadata",
    "ProviderNormalizationContext",
    "ProviderNormalizationResult",
    "ProviderRegistry",
    "ProviderState",
    "SemgrepProvider",
    "build_default_registry",
]
