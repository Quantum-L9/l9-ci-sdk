from pathlib import Path
from l9_ci.repository import enumerate_repository_files


def test_excludes_cache(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x=1")
    cache = tmp_path / ".ruff_cache"
    cache.mkdir()
    (cache / "x").write_text("x")
    assert enumerate_repository_files(tmp_path) == ("a.py",)
