"""Registry-backed provider lifecycle seam for the import pipeline.

This routes the canonical import path through the reusable provider machinery
(registry + capability detection + execution-profile selection) instead of
constructing a provider ad hoc. It activates ``select_providers`` and
``get_execution_profile`` on a real runtime entrypoint so every future provider
reuses one lifecycle rather than requiring a bespoke pipeline.

The seam is deliberately non-disruptive: it registers the concrete provider
(configured with the caller's identity map) and returns that same instance,
falling back to it when capability detection does not surface the provider as a
candidate. The pipeline still normalizes an explicitly supplied report, so
output bytes are unchanged while the selection plane is genuinely exercised.
"""

from __future__ import annotations
from pathlib import Path
from l9_ci.capabilities import detect_repository_capabilities
from l9_ci.execution import get_execution_profile, select_providers
from l9_ci.identity import RuleIdentityMap
from l9_ci.providers import Provider, ProviderRegistry
from l9_ci.providers.semgrep import SemgrepProvider

IMPORT_PROFILE = "import_only"


def resolve_import_provider(
    provider_id: str,
    *,
    repository_root: Path,
    identity_map: RuleIdentityMap | None = None,
) -> Provider:
    """Resolve the provider to use for an import-only normalization.

    Builds a registry containing the configured provider, detects repository
    capabilities, and selects providers under the import-only execution
    profile. Returns the selected provider instance for ``provider_id`` when
    selection surfaces it, otherwise the configured provider (so an explicitly
    supplied report is still normalized).
    """
    provider = _build_provider(provider_id, identity_map=identity_map)
    registry = ProviderRegistry()
    registry.register(provider)
    capabilities = detect_repository_capabilities(repository_root)
    profile = get_execution_profile(IMPORT_PROFILE)
    selected = select_providers(
        registry=registry,
        capabilities=capabilities,
        profile=profile,
        repository_root=repository_root,
    )
    for candidate in selected:
        if candidate.metadata.provider_id == provider_id:
            return candidate
    return provider


def _build_provider(
    provider_id: str,
    *,
    identity_map: RuleIdentityMap | None,
) -> Provider:
    if provider_id == "semgrep":
        return SemgrepProvider(identity_map=identity_map)
    raise ValueError(f"unknown provider_id: {provider_id!r}")
