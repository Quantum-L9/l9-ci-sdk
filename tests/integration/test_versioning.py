import pytest
from l9_ci.integration import (
    SemanticVersion,
    negotiate_versions,
)


def test_semantic_version_parses_prerelease_suffix() -> None:
    assert SemanticVersion.parse("1.2.3-dev+abc") == SemanticVersion(
        1,
        2,
        3,
    )


def test_current_bundle_is_compatible() -> None:
    result = negotiate_versions(
        {
            "SDK_version": "1.2.0",
            "schema_version": "1.4.0",
        },
        minimum_SDK_version="1.1.0",
    )
    assert result.compatible


def test_old_SDK_is_rejected() -> None:
    result = negotiate_versions(
        {
            "SDK_version": "1.0.0",
            "schema_version": "1.0.0",
        },
        minimum_SDK_version="1.1.0",
    )
    assert not result.compatible


def test_future_artifact_major_is_rejected() -> None:
    result = negotiate_versions(
        {
            "SDK_version": "2.0.0",
            "schema_version": "2.0.0",
        }
    )
    assert not result.compatible


def test_invalid_version_is_rejected() -> None:
    with pytest.raises(ValueError):
        SemanticVersion.parse("one.two.three")
