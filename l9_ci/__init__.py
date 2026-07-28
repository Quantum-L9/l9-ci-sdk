"""Quantum-L9 CI SDK."""

# Canonical SDK version. In production this package runs from source via
# PYTHONPATH (l9-ci-core's provision-sdk), where no distribution is installed
# and importlib.metadata cannot resolve a version at runtime — this constant
# is the source-run fallback and MUST match `.l9/integration-contract.yaml`
# metadata.version (and pyproject.toml's `[project] version`, for local
# `pip install -e .` installs).
__version__ = "1.0.0"

from . import capabilities, cli, execution, gates, repository

__all__ = ["capabilities", "cli", "execution", "gates", "repository"]
