"""Quantum-L9 CI SDK."""

# Canonical SDK version. Keep pyproject.toml synchronized; architecture tests
# enforce exact equality so source execution and installed wheels cannot report
# different producer identities.
__version__ = "2.0.0"

from . import (
    artifacts,
    capabilities,
    cli,
    contracts,
    execution,
    gates,
    identity,
    integration,
    policy,
    providers,
    repository,
    rulesets,
)

__all__ = [
    "artifacts",
    "capabilities",
    "cli",
    "contracts",
    "execution",
    "gates",
    "identity",
    "integration",
    "policy",
    "providers",
    "repository",
    "rulesets",
]
