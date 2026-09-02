from pathlib import Path
from l9_ci.repository import enumerate_repository_files


def test_excludes_cache(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x=1")
    cache = tmp_path / ".ruff_cache"
    cache.mkdir()
    (cache / "x").write_text("x")
    assert enumerate_repository_files(tmp_path) == ("a.py",)


def test_excludes_provisioned_l9_runtime(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x=1\n")
    runtime = tmp_path / ".l9" / "runtime" / "sdk"
    runtime.mkdir(parents=True)
    (runtime / "shim.ts").write_text("export {}\n")
    (runtime / "extra.py").write_text("x=1\n")
    assert enumerate_repository_files(tmp_path) == ("app.py",)


def test_detect_ignores_l9_runtime_languages(tmp_path: Path) -> None:
    from l9_ci.capabilities import detect_repository_capabilities

    (tmp_path / "app.py").write_text("x=1\n")
    runtime = tmp_path / ".l9" / "runtime" / "sdk"
    runtime.mkdir(parents=True)
    (runtime / "shim.ts").write_text("export {}\n")
    caps = detect_repository_capabilities(tmp_path)
    assert caps.languages == ("python",)
