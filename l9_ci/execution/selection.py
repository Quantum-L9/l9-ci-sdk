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
        # Honor both acquisition controls. A provider is selected for execution
        # only when the profile requests execution and the provider supports it
        # (and is detected on disk); for import only when the profile requests
        # import (import_reports) and the provider supports import. A profile
        # that requests neither for this provider selects nothing — previously
        # import_reports was ignored, so a native profile could silently select
        # an import-capable provider.
        if profile.execute_providers:
            if not metadata.execution_support:
                continue
            if not provider.detect(repository_root):
                continue
        elif profile.import_reports:
            if not metadata.import_support:
                continue
        else:
            continue
        selected.append(provider)
    return tuple(
        sorted(
            selected,
            key=lambda provider: provider.metadata.provider_id,
        )
    )
