import json
from pathlib import Path
from l9_ci.providers.semgrep import validate_semgrep_report

FIXTURE_ROOT = Path("tests/fixtures/semgrep")


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_representative_report_is_valid() -> None:
    result = validate_semgrep_report(load_fixture("results.json"))
    assert result.valid
    assert result.errors == ()


def test_malformed_report_is_rejected() -> None:
    result = validate_semgrep_report(load_fixture("malformed.json"))
    assert not result.valid
    assert any("check_id" in error for error in result.errors)
    assert any("end" in error for error in result.errors)
    assert any("errors must be an array" in error for error in result.errors)


def test_wrong_root_shapes_are_rejected() -> None:
    result = validate_semgrep_report(
        {
            "results": {},
            "errors": [],
        }
    )
    assert not result.valid
    assert "results must be an array" in result.errors
