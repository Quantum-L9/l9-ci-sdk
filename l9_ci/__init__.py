"""Quantum-L9 CI SDK."""

# Canonical SDK version. This package ships no build manifest and runs from
# source via PYTHONPATH (l9-ci-core's provision-sdk), so importlib.metadata
# cannot resolve a version at runtime — this constant is the source-run fallback
# and MUST match `.l9/integration-contract.yaml` metadata.version.
__version__ = "1.0.0"

from . import capabilities, cli, execution, gates, repository

__all__ = ["capabilities", "cli", "execution", "gates", "repository"]
