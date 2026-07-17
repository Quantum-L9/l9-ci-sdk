import ast
from pathlib import Path

FORBIDDEN_IMPORTS = {
    "l9_ci/contracts": {
        "l9_ci.providers",
        "l9_ci.artifacts",
    },
    "l9_ci/providers": {
        "l9_ci.artifacts",
    },
    "l9_ci/artifacts": {
        "l9_ci.providers",
    },
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_dependency_boundaries() -> None:
    violations: list[str] = []
    for package, forbidden_modules in FORBIDDEN_IMPORTS.items():
        for path in Path(package).glob("*.py"):
            for imported in imported_modules(path):
                if any(
                    imported == forbidden or imported.startswith(f"{forbidden}.")
                    for forbidden in forbidden_modules
                ):
                    violations.append(f"{path}: forbidden import {imported}")
    assert violations == []
