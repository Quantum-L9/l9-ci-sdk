"""Canonical default provider registry.

`select_providers` (l9_ci.execution) and the CLI both need a registry
pre-populated with the SDK's built-in providers. Before this module the only
factory lived inside the CLI command layer (`l9_ci.commands.providers`), which
left library consumers — l9-ci-core drives provider selection over PYTHONPATH —
without a public way to obtain it, and forced tests to re-register providers by
hand. This module is that factory, kept in the `providers` package so it does
not pull the CLI layer into the library import path.
"""

from __future__ import annotations

from .registry import ProviderRegistry
from .semgrep import SemgrepProvider


def build_default_registry() -> ProviderRegistry:
    """Return a registry populated with every built-in SDK provider."""
    registry = ProviderRegistry()
    registry.register(SemgrepProvider())
    return registry
