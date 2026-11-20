"""The seven repository shapes the capability inventory must tell apart.

Each tree is a mapping of repository-relative path to file content, written
into a temporary directory by :func:`materialize`. They live in code rather
than as checked-in files on purpose: two of them are deliberately malformed
manifests, which the repository's own format and lint hooks would otherwise
either reject or silently repair.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from l9_ci.capabilities import (
    AnalysisTarget,
    CapabilityInventory,
    build_capability_inventory,
)

SDK_VERSION = "2.0.0"

PYTHON_ONLY: Mapping[str, str] = {
    "pyproject.toml": '[project]\nname = "svc"\nversion = "0.1.0"\n',
    "svc/__init__.py": "",
    "svc/app.py": "def handler() -> int:\n    return 1\n",
    "README.md": "# svc\n",
}

TYPESCRIPT_ONLY: Mapping[str, str] = {
    "package.json": '{"name": "web", "version": "0.1.0"}\n',
    "src/index.ts": "export const value = 1;\n",
    "src/view.tsx": "export const View = () => null;\n",
}

MIXED: Mapping[str, str] = {
    "pyproject.toml": '[project]\nname = "svc"\nversion = "0.1.0"\n',
    "api/app.py": "x = 1\n",
    "api/models.py": "y = 2\n",
    "web/package.json": '{"name": "web"}\n',
    "web/src/index.ts": "export const value = 1;\n",
}

ODOO_PYTHON_XML: Mapping[str, str] = {
    "addons/stock_ext/__manifest__.py": (
        '{\n    "name": "Stock Ext",\n    "version": "19.0.1.0.0",\n'
        '    "depends": ["stock"],\n    "data": ["views/stock_view.xml"],\n}\n'
    ),
    "addons/stock_ext/__init__.py": "from . import models\n",
    "addons/stock_ext/models/__init__.py": "from . import stock\n",
    "addons/stock_ext/models/stock.py": "class Stock:\n    pass\n",
    "addons/stock_ext/views/stock_view.xml": "<odoo></odoo>\n",
    "addons/stock_ext/security/ir.model.access.csv": "id,name\n",
    "tools/release.py": "print('release')\n",
    "docs/diagram.xml": "<diagram/>\n",
}

JAVASCRIPT_ONLY: Mapping[str, str] = {
    "package.json": '{"name": "tool", "version": "0.1.0"}\n',
    "bin/cli.js": "module.exports = 1;\n",
    "lib/index.mjs": "export const value = 1;\n",
    "lib/legacy.cjs": "module.exports = 2;\n",
    "ui/view.jsx": "export const View = () => null;\n",
}

TYPESCRIPT_UNSCANNED_SUFFIXES: Mapping[str, str] = {
    "package.json": '{"name": "web"}\n',
    "src/index.ts": "export const value = 1;\n",
    "src/worker.mts": "export const worker = 1;\n",
    "src/config.cts": "export const config = 1;\n",
}

NO_SUPPORTED_CODE: Mapping[str, str] = {
    "README.md": "# documentation only\n",
    "data/table.csv": "a,b\n1,2\n",
    "LICENSE": "MIT\n",
}

MALFORMED_MANIFEST: Mapping[str, str] = {
    "pyproject.toml": "[project\nname = \n",
    "svc/app.py": "x = 1\n",
    "web/package.json": '{"name": "web",\n',
    "web/src/index.ts": "export const value = 1;\n",
}

UNSUPPORTED_LANGUAGE: Mapping[str, str] = {
    "build.gradle": "plugins { }\n",
    "app/src/Main.kt": "fun main() {}\n",
    "app/src/Util.kt": "fun util() {}\n",
}


def materialize(root: Path, tree: Mapping[str, str]) -> Path:
    for relative, content in tree.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def semgrep_targets(
    *,
    executable: str = "not_probed",
    executable_version: str | None = None,
    resolved: bool = True,
) -> tuple[AnalysisTarget, ...]:
    """The two language targets the SDK ships, declared without the CLI."""
    return tuple(
        AnalysisTarget(
            provider_id="semgrep",
            scope="language",
            name=language,
            languages=(language,),
            rulepack=f"l9_ci/rulesets/semgrep/{language}",
            rulepack_resolved=resolved,
            executable=executable,
            executable_version=executable_version,
        )
        for language in ("python", "typescript")
    )


def inventory(
    root: Path,
    targets: Sequence[AnalysisTarget],
) -> CapabilityInventory:
    """Build an inventory the way a caller does, with a fixed SDK version."""
    return build_capability_inventory(root, targets=targets, SDK_version=SDK_VERSION)
