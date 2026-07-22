"""Supported Semgrep version checks."""

from __future__ import annotations
import re
from dataclasses import dataclass
from l9_ci.contracts import SemanticVersion

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


# Closed supported range (DWA-004/QA-004): versions validated against this SDK.
# The upper bound is exclusive at the next major: Semgrep 2.x output has not
# been validated against the normalization contract, so it must be rejected
# (fail-closed) rather than silently accepted. Raise the bound only after the
# new major's JSON output is verified against the provider tests.
DEFAULT_SEMGREP_VERSION_POLICY = SemgrepVersionPolicy(
    minimum=SemanticVersion.parse("1.100.0"),
    maximum_exclusive=SemanticVersion.parse("2.0.0"),
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
        minimum = (
            f"{policy.minimum.major}.{policy.minimum.minor}.{policy.minimum.patch}"
        )
        if policy.maximum_exclusive is not None:
            bound = policy.maximum_exclusive
            supported = f">={minimum},<{bound.major}.{bound.minor}.{bound.patch}"
        else:
            supported = f">={minimum}"
        raise ValueError(
            f"unsupported Semgrep version: {raw!r}; supported range is {supported}"
        )
    return version
