import json
from pathlib import Path
import pytest
from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.integration import negotiate_versions

FIXTURE_ROOT = Path("tests/compatibility/fixtures")


def test_minimal_v1_fixture_loads() -> None:
    bundle = load_and_validate_bundle(FIXTURE_ROOT / "finding-bundle-v1-minimal.json")
    assert bundle.schema == "l9.finding-bundle/v1"
    assert bundle.schema_version == "1.0.0"


def test_v2_fixture_is_rejected() -> None:
    payload = json.loads(
        (FIXTURE_ROOT / "unsupported-bundle-v2.json").read_text(encoding="utf-8")
    )
    result = negotiate_versions(payload)
    assert not result.compatible
    with pytest.raises(ValueError):
        load_and_validate_bundle(FIXTURE_ROOT / "unsupported-bundle-v2.json")


def test_bad_summary_is_rejected() -> None:
    import pytest
    from l9_ci.artifacts import load_and_validate_bundle

    with pytest.raises(ValueError, match="summary"):
        load_and_validate_bundle(FIXTURE_ROOT / "finding-bundle-v1-bad-summary.json")
