"""Architecture dependency-boundary enforcement.

The forbidden-edge matrix is derived directly from the authoritative
``.l9/architecture.yaml`` (both each layer's ``must_not_depend_on`` rules and
the top-level ``forbidden_dependency_edges`` list), and every module under each
package is scanned recursively. This replaces the previous hand-written,
non-recursive check that enforced only a 4-edge subset and never visited
subpackages such as ``l9_ci/providers/semgrep/`` — where a real
``providers -> integration`` violation was hiding.

A mutation test proves the checker actually fails when a forbidden import is
injected, so the suite cannot silently pass on a broken checker.
"""

from __future__ import annotations
import ast
from collections import defaultdict
from pathlib import Path
from typing import Any
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE = REPO_ROOT / ".l9" / "architecture.yaml"


def _load_architecture() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(ARCHITECTURE.read_text(encoding="utf-8"))
    return data


def _build_forbidden_edges() -> dict[str, set[str]]:
    """Return {source_package: {forbidden_target_package, ...}} from the spec."""
    arch = _load_architecture()
    layers = arch["layers"]
    name_to_package = {
        name: spec["package"] for name, spec in layers.items() if "package" in spec
    }
    forbidden: dict[str, set[str]] = defaultdict(set)
    # 1. Per-layer must_not_depend_on rules.
    for spec in layers.values():
        source = spec.get("package")
        if source is None:
            continue
        for target_name in spec.get("must_not_depend_on", []):
            target = name_to_package.get(target_name)
            if target is not None:
                forbidden[source].add(target)
    # 2. Top-level forbidden_dependency_edges named "<layer>_to_<layer>".
    #    Edges referencing external repositories (SDK_to_Core, etc.) have no
    #    local package and are skipped.
    for edge in arch.get("forbidden_dependency_edges", []):
        if "_to_" not in edge:
            continue
        left, right = edge.split("_to_", 1)
        source = name_to_package.get(left)
        target = name_to_package.get(right)
        if source is not None and target is not None:
            forbidden[source].add(target)
    return dict(forbidden)


FORBIDDEN_EDGES = _build_forbidden_edges()


def _imports_in_source(source: str, module_parts: tuple[str, ...]) -> set[str]:
    """Absolute module names imported by ``source``.

    ``module_parts`` is the dotted path of the module being parsed (e.g.
    ``("l9_ci", "providers", "semgrep", "versioning")``) and is used to resolve
    relative imports to absolute module paths.
    """
    tree = ast.parse(source)
    imports: set[str] = set()
    package_parts = list(module_parts[:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    imports.add(node.module)
                continue
            if node.level - 1 > len(package_parts):
                base: list[str] = []
            else:
                base = package_parts[: len(package_parts) - (node.level - 1)]
            resolved = base + ([node.module] if node.module else [])
            if resolved:
                imports.add(".".join(resolved))
    return imports


def _matches(imported: str, target: str) -> bool:
    return imported == target or imported.startswith(f"{target}.")


def _violations(
    source_package: str, forbidden_targets: set[str]
) -> list[tuple[str, str]]:
    package_path = REPO_ROOT / source_package.replace(".", "/")
    found: list[tuple[str, str]] = []
    for module_file in sorted(package_path.rglob("*.py")):
        module_parts = module_file.relative_to(REPO_ROOT).with_suffix("").parts
        imported_modules = _imports_in_source(
            module_file.read_text(encoding="utf-8"),
            module_parts,
        )
        for imported in sorted(imported_modules):
            for target in sorted(forbidden_targets):
                if _matches(imported, target):
                    found.append((str(module_file.relative_to(REPO_ROOT)), imported))
    return found


@pytest.mark.parametrize("source_package", sorted(FORBIDDEN_EDGES))
def test_no_forbidden_imports(source_package: str) -> None:
    violations = _violations(source_package, FORBIDDEN_EDGES[source_package])
    assert violations == [], f"{source_package} imports a forbidden layer: {violations}"


def test_matrix_is_derived_and_covers_key_edges() -> None:
    # Guard that the spec-derived matrix actually includes the edge that the
    # previous hand-written test omitted (providers -> integration, AUD-001).
    assert "l9_ci.integration" in FORBIDDEN_EDGES.get("l9_ci.providers", set())
    # And that we derived more than the old 4-edge subset.
    total_edges = sum(len(targets) for targets in FORBIDDEN_EDGES.values())
    assert total_edges >= 10


_EDGE_CASES = [
    (source, target)
    for source, targets in sorted(FORBIDDEN_EDGES.items())
    for target in sorted(targets)
]


@pytest.mark.parametrize(
    "source_package,target_package",
    _EDGE_CASES,
    ids=[f"{s}->{t}" for s, t in _EDGE_CASES],
)
def test_checker_detects_injected_violation(
    source_package: str, target_package: str
) -> None:
    # Mutation proof: an injected forbidden import must be flagged, so a passing
    # suite genuinely means the code is clean rather than the checker being inert.
    injected = f"from {target_package} import _probe\n"
    module_parts = (*source_package.split("."), "_mutation_probe")
    imported = _imports_in_source(injected, module_parts)
    assert any(_matches(name, target_package) for name in imported)


# --- Positive allowlist enforcement (AUD-002) -------------------------------
# The forbidden-edge checks above enforce the *negative* half of the graph.
# These enforce the *positive* half: a layer may import only the peer layers in
# its `may_depend_on`. This closes the gap where an import that is neither
# forbidden nor allow-listed (e.g. capabilities -> gates) passed undetected, and
# where layers with no `must_not_depend_on` were entirely unconstrained.


def _layer_packages() -> set[str]:
    arch = _load_architecture()
    return {spec["package"] for spec in arch["layers"].values() if "package" in spec}


def _build_allowlist() -> dict[str, set[str]]:
    """Return {source_package: {allowed_peer_layer_package, ...}}."""
    arch = _load_architecture()
    layers = arch["layers"]
    name_to_package = {
        name: spec["package"] for name, spec in layers.items() if "package" in spec
    }
    allow: dict[str, set[str]] = {}
    for spec in layers.values():
        source = spec.get("package")
        if source is None:
            continue
        allow[source] = {
            name_to_package[dep]
            for dep in spec.get("may_depend_on", [])
            if dep in name_to_package
        }
    return allow


ALLOWLIST = _build_allowlist()
_LAYER_PACKAGES = _layer_packages()


def _layer_package_of(imported: str) -> str | None:
    """The layer package an imported module belongs to (longest-prefix), or None.

    Imports of the `l9_ci` root (e.g. `l9_ci.__version__`) or the stdlib map to
    no layer and are unconstrained.
    """
    best: str | None = None
    for package in _LAYER_PACKAGES:
        if imported == package or imported.startswith(f"{package}."):
            if best is None or len(package) > len(best):
                best = package
    return best


def _allowlist_violations(
    source_package: str, allowed_targets: set[str]
) -> list[tuple[str, str]]:
    package_path = REPO_ROOT / source_package.replace(".", "/")
    found: list[tuple[str, str]] = []
    for module_file in sorted(package_path.rglob("*.py")):
        module_parts = module_file.relative_to(REPO_ROOT).with_suffix("").parts
        for imported in sorted(
            _imports_in_source(module_file.read_text(encoding="utf-8"), module_parts)
        ):
            target = _layer_package_of(imported)
            if target is None or target == source_package:
                continue
            if target not in allowed_targets:
                found.append((str(module_file.relative_to(REPO_ROOT)), imported))
    return found


@pytest.mark.parametrize("source_package", sorted(ALLOWLIST))
def test_imports_within_allowlist(source_package: str) -> None:
    violations = _allowlist_violations(source_package, ALLOWLIST[source_package])
    assert violations == [], (
        f"{source_package} imports a layer not in its may_depend_on: {violations}"
    )


def test_allowlist_permits_a_declared_peer() -> None:
    # pipeline legitimately depends on contracts (reconciled in AUD-002).
    assert "l9_ci.contracts" in ALLOWLIST["l9_ci.pipeline"]


def test_allowlist_flags_a_non_listed_peer() -> None:
    # Mutation proof: contracts declares no dependencies, so an import to gates
    # must be caught by the allowlist checker.
    injected = "from l9_ci.gates import evaluate_gate\n"
    imported = _imports_in_source(injected, ("l9_ci", "contracts", "_probe"))
    target = _layer_package_of(next(iter(imported)))
    assert target == "l9_ci.gates"
    assert target not in ALLOWLIST["l9_ci.contracts"]
