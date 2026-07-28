from l9_ci.integration import validate_redaction


def test_safe_payload_passes() -> None:
    result = validate_redaction(
        {
            "path": "src/example.py",
            "message": "Example finding",
        }
    )
    assert result.valid


def test_absolute_path_is_rejected() -> None:
    result = validate_redaction(
        {
            "path": "/home/runner/work/repo/example.py",
        }
    )
    assert not result.valid


def test_source_lines_are_rejected() -> None:
    result = validate_redaction(
        {
            "lines": "secret = 'value'",
        }
    )
    assert not result.valid


def test_secret_like_field_is_rejected() -> None:
    result = validate_redaction(
        {
            "api_token": "redacted",
        }
    )
    assert not result.valid
