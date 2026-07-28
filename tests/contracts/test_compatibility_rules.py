from l9_ci.artifacts import check_bundle_compatibility


def test_current_protocol_is_compatible() -> None:
    result = check_bundle_compatibility(
        {
            "schema": "l9.finding-bundle/v1",
            "schema_version": "1.3.0",
        }
    )
    assert result.compatible
    assert result.errors == ()


def test_future_major_version_is_rejected() -> None:
    result = check_bundle_compatibility(
        {
            "schema": "l9.finding-bundle/v1",
            "schema_version": "2.0.0",
        }
    )
    assert not result.compatible


def test_wrong_protocol_is_rejected() -> None:
    result = check_bundle_compatibility(
        {
            "schema": "other.protocol/v1",
            "schema_version": "1.0.0",
        }
    )
    assert not result.compatible
