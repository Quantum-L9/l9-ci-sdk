"""Provider selection from registry, capabilities, and execution profile."""

from __future__ import annotations
from pathlib import Path
from l9_ci.capabilities import RepositoryCapabilities
from l9_ci.providers import Provider, ProviderRegistry, ProviderState
from .profiles import ExecutionProfile


def select_providers(
    *,
    registry: ProviderRegistry,
    capabilities: RepositoryCapabilities,
    profile: ExecutionProfile,
    repository_root: Path,
) -> tuple[Provider, ...]:
    selected: list[Provider] = []
    candidate_ids = set(capabilities.provider_candidates)
    for provider in registry.providers():
        metadata = provider.metadata
        if metadata.provider_id not in candidate_ids:
            continue
        if profile.supported_only:
            if metadata.state is not ProviderState.SUPPORTED:
                continue
        if profile.execute_providers and not metadata.execution_support:
            continue
        if not profile.execute_providers and not metadata.import_support:
            continue
        if not provider.detect(repository_root) and profile.execute_providers:
            continue
        selected.append(provider)
    return tuple(
        sorted(
            selected,
            key=lambda provider: provider.metadata.provider_id,
        )
    )
