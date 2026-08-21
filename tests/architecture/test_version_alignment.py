from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

import l9_ci

ROOT = Path(__file__).resolve().parents[2]


def test_source_package_integration_and_lock_versions_match() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    integration = yaml.safe_load(
        (ROOT / ".l9/integration-contract.yaml").read_text(encoding="utf-8")
    )
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))

    editable_roots = [
        package
        for package in uv_lock["package"]
        if package.get("name") == "l9-ci"
        and package.get("source") == {"editable": "."}
    ]
    assert len(editable_roots) == 1

    expected = l9_ci.__version__
    assert expected == "2.0.0"
    assert pyproject["project"]["version"] == expected
    assert integration["metadata"]["version"] == expected
    assert editable_roots[0]["version"] == expected
