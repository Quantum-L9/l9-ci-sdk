"""Packaged Semgrep ruleset and identity-map resolution.

The Semgrep rule files and the identity map under this package are shipped
as SDK data so every downstream consumer inherits one global, versioned
ruleset per language via ``l9-ci semgrep run --language {python,typescript}``
with no per-repository ``--config`` authoring. Paths are resolved through
:mod:`importlib.resources` so lookup is identical whether the SDK is running
from an editable source checkout or from a ``pip install``-ed wheel with no
source tree present.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

SUPPORTED_LANGUAGES: tuple[str, ...] = ("python", "typescript")


def ruleset_dir(language: str) -> Path:
    """Return the packaged Semgrep ruleset directory for ``language``.

    Raises ``ValueError`` for an unsupported language and
    ``FileNotFoundError`` if the packaged directory is missing -- callers
    must fail closed rather than silently falling back to an empty config.
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"unsupported ruleset language {language!r}; "
            f"expected one of {SUPPORTED_LANGUAGES}"
        )
    traversable = importlib.resources.files(__package__) / language
    resolved = Path(str(traversable))
    if not resolved.is_dir():
        raise FileNotFoundError(
            f"packaged Semgrep ruleset directory not found: {resolved}"
        )
    return resolved


def default_identity_map_path() -> Path:
    """Return the packaged Semgrep identity map shipped with the SDK.

    This is the mirror of ``.l9/semgrep-identity-map.yaml``; a dedicated
    parity test keeps the two byte-identical.
    """
    traversable = importlib.resources.files(__package__) / "identity-map.yaml"
    resolved = Path(str(traversable))
    if not resolved.is_file():
        raise FileNotFoundError(f"packaged Semgrep identity map not found: {resolved}")
    return resolved


__all__ = [
    "SUPPORTED_LANGUAGES",
    "ruleset_dir",
    "default_identity_map_path",
]
