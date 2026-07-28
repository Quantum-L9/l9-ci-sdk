import pytest
from l9_ci.providers.semgrep.versioning import (
    SemgrepVersionPolicy,
    parse_semgrep_version,
    require_supported_semgrep_version,
)
from l9_ci.integration import SemanticVersion


def test_parse_semgrep_version() -> None:
    assert parse_semgrep_version("1.100.0") == SemanticVersion(
        1,
        100,
        0,
    )


def test_version_with_prefix_is_parsed() -> None:
    assert parse_semgrep_version("semgrep 1.101.2") == SemanticVersion(1, 101, 2)


def test_old_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        require_supported_semgrep_version("1.99.0")


def test_maximum_exclusive_is_enforced() -> None:
    policy = SemgrepVersionPolicy(
        minimum=SemanticVersion.parse("1.100.0"),
        maximum_exclusive=SemanticVersion.parse("2.0.0"),
    )
    with pytest.raises(ValueError):
        require_supported_semgrep_version(
            "2.0.0",
            policy=policy,
        )
