from pathlib import Path
from l9_ci.capabilities import detect_repository_capabilities


def test_detects_python(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    caps = detect_repository_capabilities(tmp_path)
    assert caps.languages == ("python",)
    assert caps.provider_candidates == ("semgrep",)
