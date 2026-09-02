"""Public rule identity resolution API."""

from .diagnostics import describe_unresolved_identity
from .resolver import (
    IdentityResolution,
    IdentityResolutionStatus,
    RuleIdentityMap,
    resolve_rule_identity,
)

__all__ = [
    "IdentityResolution",
    "IdentityResolutionStatus",
    "RuleIdentityMap",
    "describe_unresolved_identity",
    "resolve_rule_identity",
]
