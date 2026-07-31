"""GIT_DIR from hooks must not hijack git -C inspection of other roots."""

from __future__ import annotations

import subprocess
from pathlib import Path

from l9_ci.repository.git import is_git_repository
from l9_ci.repository.manifest import build_repository_manifest


def test_is_git_repository_ignores_ambient_git_dir(tmp_path: Path, monkeypatch) -> None:
    git_dir = subprocess.check_output(
        ["git", "rev-parse", "--git-dir"], text=True
    ).strip()
    monkeypatch.setenv("GIT_DIR", git_dir)
    monkeypatch.setenv("GIT_WORK_TREE", str(Path.cwd()))

    assert is_git_repository(tmp_path) is False
    (tmp_path / "only.txt").write_text("x", encoding="utf-8")
    manifest = build_repository_manifest(tmp_path)
    assert manifest.files == ("only.txt",)
