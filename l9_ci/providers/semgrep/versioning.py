"""Supported Semgrep version checks."""

from __future__ import annotations
import re
from dataclasses import dataclass
from l9_ci.integration import SemanticVersion

_VERSION_PATTERN = re.compile(r"(?P<version>[0-9]+\.[0-9]+\.[0-9]+)")


@dataclass(frozen=True, slots=True)
class SemgrepVersionPolicy:
    minimum: SemanticVersion
    maximum_exclusive: SemanticVersion | None = None

    def supports(self, version: SemanticVersion) -> bool:
        if version < self.minimum:
            return False
        if self.maximum_exclusive is not None and version >= self.maximum_exclusive:
            return False
        return True


DEFAULT_SEMGREP_VERSION_POLICY = SemgrepVersionPolicy(
    minimum=SemanticVersion.parse("1.100.0"),
    maximum_exclusive=None,
)


def parse_semgrep_version(raw: str) -> SemanticVersion:
    match = _VERSION_PATTERN.search(raw)
    if not match:
        raise ValueError(f"unable to parse Semgrep version from {raw!r}")
    return SemanticVersion.parse(match.group("version"))


def require_supported_semgrep_version(
    raw: str,
    *,
    policy: SemgrepVersionPolicy = DEFAULT_SEMGREP_VERSION_POLICY,
) -> SemanticVersion:
    version = parse_semgrep_version(raw)
    if not policy.supports(version):
        raise ValueError(
            f"unsupported Semgrep version: {raw!r}; "
            f"minimum is "
            f"{policy.minimum.major}."
            f"{policy.minimum.minor}."
            f"{policy.minimum.patch}"
        )
    return version
