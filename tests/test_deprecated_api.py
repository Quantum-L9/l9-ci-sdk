from pathlib import Path
from l9_ci.scanners.deprecated_api import check, fix


def test_deprecated_api_detected(tmp_path: Path) -> None:
    f = tmp_path / "bad.py"
    f.write_text("from engine.config.loader import DomainSpecLoader\nloader = DomainSpecLoader(SPEC_PATH)\n", encoding="utf-8")
    assert len(check([tmp_path], root=tmp_path)) == 2


def test_deprecated_api_fixed(tmp_path: Path) -> None:
    f = tmp_path / "bad.py"
    f.write_text("from engine.config.loader import DomainSpecLoader\nloader = DomainSpecLoader(SPEC_PATH)\n", encoding="utf-8")
    changed = fix([tmp_path])
    assert changed == [f]
    text = f.read_text(encoding="utf-8")
    assert "DomainPackLoader" in text
    assert "DomainSpecLoader" not in text
    assert "config_path=str(SPEC_PATH)" in text


def test_deprecated_checker_supports_exclude_suffix(tmp_path: Path) -> None:
    f = tmp_path / "generated" / "bad.py"
    f.parent.mkdir()
    f.write_text("from engine.config.loader import DomainSpecLoader\n", encoding="utf-8")
    assert check([tmp_path], root=tmp_path, exclude=["generated/bad.py"]) == []
