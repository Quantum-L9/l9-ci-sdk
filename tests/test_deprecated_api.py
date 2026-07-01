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


def test_domain_spec_loader_in_comment_is_not_flagged(tmp_path: Path) -> None:
    f = tmp_path / "c.py"
    f.write_text("# DomainSpecLoader is deprecated, use DomainPackLoader\nx = 1\n", encoding="utf-8")
    assert check([tmp_path], root=tmp_path) == []


def test_domain_spec_loader_in_string_is_not_flagged(tmp_path: Path) -> None:
    f = tmp_path / "s.py"
    f.write_text('MSG = "please migrate off DomainSpecLoader"\n', encoding="utf-8")
    assert check([tmp_path], root=tmp_path) == []


def test_real_domain_spec_loader_usage_is_still_flagged(tmp_path: Path) -> None:
    f = tmp_path / "u.py"
    f.write_text("from engine.config.loader import DomainSpecLoader\n", encoding="utf-8")
    assert len(check([tmp_path], root=tmp_path)) == 1
