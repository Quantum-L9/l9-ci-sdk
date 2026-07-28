from pathlib import Path

from l9_ci.repository.manifest import build_repository_manifest, write_repository_manifest


def test_manifest_is_sorted_and_excludes_itself(tmp_path: Path) -> None:
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "MANIFEST.md").write_text("stale", encoding="utf-8")

    manifest = build_repository_manifest(tmp_path)

    assert manifest.files == ("a.txt", "z.txt")
    assert manifest.file_count == 2


def test_write_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")

    first, first_changed = write_repository_manifest(tmp_path)
    second, second_changed = write_repository_manifest(tmp_path)

    assert first == second
    assert first_changed is True
    assert second_changed is False
    assert (tmp_path / "MANIFEST.md").read_text(encoding="utf-8") == (
        "# Consolidated Manifest\n\nFiles: 1\n\n## Contents\n\n- `a.txt`\n"
    )


def test_excludes_explicit_paths_and_directories(tmp_path: Path) -> None:
    (tmp_path / "keep.py").write_text("", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("", encoding="utf-8")
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "artifact.json").write_text("{}", encoding="utf-8")

    manifest = build_repository_manifest(
        tmp_path,
        excluded_paths=("ignore.txt",),
        excluded_directories=("generated",),
    )

    assert manifest.files == ("keep.py",)
