from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

import l9_ci

ROOT = Path(__file__).resolve().parents[2]


def test_source_package_and_integration_contract_versions_match() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    integration = yaml.safe_load(
        (ROOT / ".l9/integration-contract.yaml").read_text(encoding="utf-8")
    )
    expected = l9_ci.__version__
    assert expected == "2.0.0"
    assert pyproject["project"]["version"] == expected
    assert integration["metadata"]["version"] == expected
