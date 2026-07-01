from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from l9_ci.utils.files import iter_files


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


pytestmark = pytest.mark.skipif(not _git_available(), reason="git executable is required")


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def test_git_tracked_mode_uses_tracked_files_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    tracked = tmp_path / "tracked.py"
    untracked = tmp_path / "untracked.py"
    tracked.write_text("x = 1\n", encoding="utf-8")
    untracked.write_text("y = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)

    files = iter_files([Path(".")], suffixes={".py"}, file_mode="git_tracked")

    assert tracked.resolve() in files
    assert untracked.resolve() not in files


def test_working_tree_mode_includes_untracked_non_ignored_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    tracked = tmp_path / "tracked.py"
    untracked = tmp_path / "untracked.py"
    ignored = tmp_path / "ignored.py"
    tracked.write_text("x = 1\n", encoding="utf-8")
    untracked.write_text("y = 2\n", encoding="utf-8")
    ignored.write_text("z = 3\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py", ".gitignore"], cwd=tmp_path, check=True)

    files = iter_files([Path(".")], suffixes={".py"}, file_mode="working_tree")

    assert tracked.resolve() in files
    assert untracked.resolve() in files
    assert ignored.resolve() not in files


def test_filesystem_mode_uses_gitignore_and_pyproject_excludes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    keep = tmp_path / "src" / "keep.py"
    ignored_by_gitignore = tmp_path / "generated" / "ignored.py"
    ignored_by_pyproject = tmp_path / "vendor" / "ignored.py"
    keep.parent.mkdir()
    ignored_by_gitignore.parent.mkdir()
    ignored_by_pyproject.parent.mkdir()
    keep.write_text("x = 1\n", encoding="utf-8")
    ignored_by_gitignore.write_text("x = 2\n", encoding="utf-8")
    ignored_by_pyproject.write_text("x = 3\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("generated/\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[tool.l9-ci]\nexclude = ["vendor/"]\n', encoding="utf-8")

    files = iter_files([tmp_path], suffixes={".py"}, file_mode="filesystem")

    assert keep.resolve() in files
    assert ignored_by_gitignore.resolve() not in files
    assert ignored_by_pyproject.resolve() not in files


def test_cli_exclude_is_applied_last(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "target.py"
    target.write_text("x = 1\n", encoding="utf-8")

    files = iter_files([tmp_path], suffixes={".py"}, exclude=["target.py"], file_mode="filesystem")

    assert files == []
