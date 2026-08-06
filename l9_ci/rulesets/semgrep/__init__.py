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

import functools
import importlib.resources
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_LANGUAGES: tuple[str, ...] = ("python", "typescript")

PROFILES_SCHEMA: str = "l9.semgrep-profiles/v1"


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


@dataclass(frozen=True)
class SemgrepProfile:
    """A named, deterministic selection over the packaged Semgrep configs.

    A profile chooses *which* already-packaged config sources one
    ``l9-ci semgrep run`` execution composes for a language; it never adds a
    second scanner, SARIF projection, or GitHub upload, and never promotes a
    rule to blocking. ``include_registry_ruleset`` toggles the community
    registry ruleset (``p/python`` / ``p/typescript``); ``include_l9_ruleset``
    toggles the SDK-packaged L9 baseline ruleset directory for the language.
    """

    name: str
    description: str
    include_registry_ruleset: bool
    include_l9_ruleset: bool


def profiles_path() -> Path:
    """Return the packaged Semgrep profile registry shipped with the SDK.

    Raises ``FileNotFoundError`` if the packaged registry is missing -- callers
    must fail closed rather than silently scanning with no profile.
    """
    traversable = importlib.resources.files(__package__) / "profiles.yaml"
    resolved = Path(str(traversable))
    if not resolved.is_file():
        raise FileNotFoundError(
            f"packaged Semgrep profile registry not found: {resolved}"
        )
    return resolved


def _require_mapping(value: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Semgrep profile registry: {context} must be a mapping")
    return value


def _require_bool(value: Any, *, context: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Semgrep profile registry: {context} must be a boolean")
    return value


@functools.lru_cache(maxsize=1)
def _load_profile_registry() -> tuple[str, dict[str, SemgrepProfile]]:
    """Parse and validate the packaged ``profiles.yaml`` (cached).

    Fails closed on any structural defect: a missing/empty registry, an
    unexpected schema, an unknown ``default_profile``, or a profile lacking its
    two required boolean selectors. Deterministic: profiles are returned keyed
    by name with no dependence on mapping iteration order at the call site.
    """
    document = _require_mapping(
        yaml.safe_load(profiles_path().read_text(encoding="utf-8")),
        context="document root",
    )
    schema = document.get("schema")
    if schema != PROFILES_SCHEMA:
        raise ValueError(
            f"Semgrep profile registry: unexpected schema {schema!r}; "
            f"expected {PROFILES_SCHEMA!r}"
        )
    raw_profiles = _require_mapping(document.get("profiles"), context="'profiles'")
    if not raw_profiles:
        raise ValueError("Semgrep profile registry: 'profiles' must be non-empty")

    profiles: dict[str, SemgrepProfile] = {}
    for name, raw_profile in raw_profiles.items():
        profile_body = _require_mapping(raw_profile, context=f"profile {name!r}")
        description = profile_body.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(
                f"Semgrep profile registry: profile {name!r} must carry a "
                "non-empty 'description'"
            )
        profiles[name] = SemgrepProfile(
            name=name,
            description=" ".join(description.split()),
            include_registry_ruleset=_require_bool(
                profile_body.get("include_registry_ruleset"),
                context=f"profile {name!r} 'include_registry_ruleset'",
            ),
            include_l9_ruleset=_require_bool(
                profile_body.get("include_l9_ruleset"),
                context=f"profile {name!r} 'include_l9_ruleset'",
            ),
        )

    default_profile = document.get("default_profile")
    if default_profile not in profiles:
        raise ValueError(
            f"Semgrep profile registry: default_profile {default_profile!r} "
            f"is not a defined profile ({sorted(profiles)})"
        )
    return default_profile, profiles


def default_profile_name() -> str:
    """Return the profile name applied when ``--profile`` is omitted."""
    default_profile, _ = _load_profile_registry()
    return default_profile


def profile_names() -> tuple[str, ...]:
    """Return the deterministically sorted names of the packaged profiles."""
    _, profiles = _load_profile_registry()
    return tuple(sorted(profiles))


def resolve_profile(name: str) -> SemgrepProfile:
    """Resolve ``name`` to its packaged :class:`SemgrepProfile`.

    Raises ``ValueError`` for an unknown profile so a typo fails closed rather
    than silently scanning with an unintended config composition.
    """
    _, profiles = _load_profile_registry()
    try:
        return profiles[name]
    except KeyError:
        raise ValueError(
            f"unknown Semgrep profile {name!r}; expected one of {sorted(profiles)}"
        ) from None


__all__ = [
    "PROFILES_SCHEMA",
    "SUPPORTED_LANGUAGES",
    "SemgrepProfile",
    "default_identity_map_path",
    "default_profile_name",
    "profile_names",
    "profiles_path",
    "resolve_profile",
    "ruleset_dir",
]
