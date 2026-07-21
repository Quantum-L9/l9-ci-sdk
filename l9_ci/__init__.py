"""Quantum-L9 CI SDK."""

# Canonical SDK version — the single source of truth. `pyproject.toml` derives
# its build-manifest version from this constant (tool.setuptools.dynamic), so an
# installed package (`importlib.metadata.version("l9-ci-sdk")`) and a source run
# (via PYTHONPATH, l9-ci-core's provision-sdk) report the same value. This
# constant MUST match `.l9/integration-contract.yaml` metadata.version.>>>>>>> 1c74931 (build(ci): add self-validation CI, type/coverage gates, packaging, and commit-bound evidence (AUD-009, QA-007, QA-008, AUD-008, AUD-007, AUD-002))
__version__ = "1.0.0"

from . import capabilities, cli, execution, gates, repository

__all__ = ["capabilities", "cli", "execution", "gates", "repository"]
