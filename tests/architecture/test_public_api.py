"""Exact-equality enforcement of the canonical public API surface.

AUD-005 / QA-009: the public surface previously disagreed four ways
(architecture.yaml 11 packages, root __all__ 5, docs 3, subset-only tests that
never checked identity/policy/integration). This test derives the authoritative
surface from a single manifest (.l9/public-api.yaml) and asserts each package's
``__all__`` equals it exactly, so accidental exports or silent removals fail CI
rather than passing under a subset check.
"""

from __future__ import annotations
import importlib
from pathlib import Path
from typing import Any
import pytest
import yaml

import l9_ci

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / ".l9" / "public-api.yaml"
ARCHITECTURE = REPO_ROOT / ".l9" / "architecture.yaml"


def _manifest() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    return data


MANIFEST_DATA = _manifest()
PACKAGES: dict[str, list[str]] = MANIFEST_DATA["packages"]
ALLOWLIST: dict[str, list[str]] = MANIFEST_DATA.get("compatibility_allowlist", {})


@pytest.mark.parametrize("package_name", sorted(PACKAGES))
def test_public_surface_is_exact(package_name: str) -> None:
    module = importlib.import_module(package_name)
    actual = set(getattr(module, "__all__", []))
    expected = set(PACKAGES[package_name]) | set(ALLOWLIST.get(package_name, []))
    assert actual == expected, (
        f"{package_name}.__all__ diverges from .l9/public-api.yaml: "
        f"unexpected={sorted(actual - expected)} missing={sorted(expected - actual)}"
    )


def test_manifest_matches_architecture_public_surface() -> None:
    # The manifest's package set must equal architecture.yaml's public_surface.
    arch = yaml.safe_load(ARCHITECTURE.read_text(encoding="utf-8"))
    declared = set(arch["public_surface"]["packages"])
    assert set(PACKAGES) == declared


def test_root_exports_every_public_package() -> None:
    # l9_ci.__all__ must expose exactly the public packages (by short name).
    short_names = {name.split(".", 1)[1] for name in PACKAGES}
    assert set(l9_ci.__all__) == short_names
    for name in short_names:
        assert hasattr(l9_ci, name)


def test_every_exported_symbol_is_importable() -> None:
    # Guard against a manifest listing a name the module does not actually
    # provide (the surface must be real, not aspirational).
    for package_name, symbols in PACKAGES.items():
        module = importlib.import_module(package_name)
        for symbol in symbols:
            assert hasattr(module, symbol), f"{package_name} missing {symbol}"


def test_semantic_version_has_one_public_home() -> None:
    # Regression for the AUD-005 duplicate: SemanticVersion is public in
    # contracts only, not integration.
    assert "SemanticVersion" in PACKAGES["l9_ci.contracts"]
    assert "SemanticVersion" not in PACKAGES["l9_ci.integration"]
    import l9_ci.integration as integration

    assert "SemanticVersion" not in getattr(integration, "__all__", [])
