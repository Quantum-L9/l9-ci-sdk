from __future__ import annotations

from pathlib import Path

from l9_ci.bootstrap.new_repo import format_result, init_repo
from l9_ci.cli import main


def test_init_repo_creates_required_files(tmp_path: Path) -> None:
    result = init_repo(tmp_path)
    created = {str(path.relative_to(tmp_path)) for path in result.created}
    assert ".github/workflows/ci.yml" in created
    assert "requirements-ci.txt" in created
    assert ".pre-commit-config.yaml" in created
    assert "pyproject.toml" in created
    assert ".github/governance/quality-thresholds.yaml" in created
    assert ".github/governance/audit-baseline.json" in created
    assert ".github/governance/audit-policy.yml" in created
    workflow = (tmp_path / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Quantum-L9/l9-ci-core/.github/workflows/pr-pipeline.yml@v1" in workflow


def test_init_repo_does_not_overwrite_without_force(tmp_path: Path) -> None:
    existing = tmp_path / "pyproject.toml"
    existing.write_text("keep = true\n", encoding="utf-8")
    result = init_repo(tmp_path)
    assert existing in result.skipped
    assert existing.read_text(encoding="utf-8") == "keep = true\n"


def test_init_repo_force_overwrites(tmp_path: Path) -> None:
    existing = tmp_path / "pyproject.toml"
    existing.write_text("keep = true\n", encoding="utf-8")
    result = init_repo(tmp_path, force=True)
    assert existing in result.created
    assert "[tool.ruff]" in existing.read_text(encoding="utf-8")


def test_format_result_lists_created_and_skipped(tmp_path: Path) -> None:
    result = init_repo(tmp_path)
    text = format_result(result)
    assert "Initialized L9 repo CI" in text
    assert "created:" in text


def test_cli_init_repo(tmp_path: Path, capsys) -> None:
    code = main(["init-repo", str(tmp_path)])
    assert code == 0
    assert (tmp_path / ".github/workflows/ci.yml").exists()
    assert (tmp_path / ".github/governance/quality-thresholds.yaml").exists()
    assert "Initialized L9 repo CI" in capsys.readouterr().out
