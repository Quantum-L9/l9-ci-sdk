"""Quantum-L9 CI SDK."""

# Canonical SDK version — the single source of truth. `pyproject.toml` derives
# its build-manifest version from this constant (tool.setuptools.dynamic), so an
# installed package (`importlib.metadata.version("l9-ci-sdk")`) and a source run
# (via PYTHONPATH, l9-ci-core's provision-sdk) report the same value. This
# constant MUST match `.l9/integration-contract.yaml` metadata.version.
__version__ = "1.0.0"

# The 11 public packages, matching .l9/architecture.yaml public_surface and
# .l9/public-api.yaml (AUD-005: one canonical, test-enforced public surface).
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
]
