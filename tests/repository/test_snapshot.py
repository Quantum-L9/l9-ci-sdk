from pathlib import Path
from l9_ci.repository import build_repository_snapshot


def test_filesystem_snapshot_is_deterministic(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("print('b')\n", encoding="utf-8")
    first = build_repository_snapshot(tmp_path)
    second = build_repository_snapshot(tmp_path)
    assert first.snapshot_id == second.snapshot_id
    assert first.files == ("a.py", "b.py")
