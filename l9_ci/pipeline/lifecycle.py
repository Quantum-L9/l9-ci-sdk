"""Registry-backed provider lifecycle resolution for import and execution."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from l9_ci.capabilities import detect_repository_capabilities
from l9_ci.execution import (
    ExecutionProfile,
    ExecutionProfileName,
    get_execution_profile,
    select_providers,
)
from l9_ci.identity import RuleIdentityMap
from l9_ci.providers import Provider, ProviderRegistry
from l9_ci.providers.semgrep import SemgrepProvider


class ProviderAcquisitionMode(StrEnum):
    IMPORT = "import"
    EXECUTE = "execute"


def _build_provider(
    provider_id: str,
    *,
    identity_map: RuleIdentityMap | None,
) -> Provider:
    if provider_id == "semgrep":
        return SemgrepProvider(identity_map=identity_map)
    raise ValueError(f"unknown provider_id: {provider_id!r}")


def _profile(mode: ProviderAcquisitionMode) -> ExecutionProfile:
    if mode is ProviderAcquisitionMode.IMPORT:
        return get_execution_profile(ExecutionProfileName.IMPORT_ONLY)
    # Execution is explicitly requested by the caller. Experimental adapters are
    # allowed here because provider promotion and organization rollout remain a
    # Core/governance decision; the runner still validates availability, version,
    # configuration, bounds, and structured failure behavior.
    return ExecutionProfile(
        name=ExecutionProfileName.ALL_SUPPORTED,
        execute_providers=True,
        import_reports=True,
        supported_only=False,
    )


def resolve_provider(
    provider_id: str,
    *,
    mode: ProviderAcquisitionMode,
    repository_root: Path,
    identity_map: RuleIdentityMap | None = None,
) -> Provider:
    """Resolve an explicitly requested provider through registry/profile selection.

    Capability and installation selection are exercised for both acquisition
    modes. When selection returns nothing, the configured provider is returned so
    the canonical runner can emit a structured NOT_INSTALLED or configuration
    failure instead of losing the provider request before artifact construction.
    """
    provider = _build_provider(provider_id, identity_map=identity_map)
    registry = ProviderRegistry()
    registry.register(provider)
    selected = select_providers(
        registry=registry,
        capabilities=detect_repository_capabilities(repository_root),
        profile=_profile(mode),
        repository_root=repository_root,
    )
    for candidate in selected:
        if candidate.metadata.provider_id == provider_id:
            return candidate
    return provider


def resolve_import_provider(
    provider_id: str,
    *,
    repository_root: Path,
    identity_map: RuleIdentityMap | None = None,
) -> Provider:
    """Backward-compatible import-mode resolver."""
    return resolve_provider(
        provider_id,
        mode=ProviderAcquisitionMode.IMPORT,
        repository_root=repository_root,
        identity_map=identity_map,
    )
