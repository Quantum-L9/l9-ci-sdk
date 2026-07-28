"""Provider promotion gate (AUD-010).

The pipeline enforces version *support*, but nothing tied the Semgrep provider's
ProviderState to the declared promotion blockers. These guards make a premature
promotion fail CI: the provider must stay EXPERIMENTAL while
`.l9/release-policy.yaml` still lists blockers, and its coded state must match
the policy's declared current_state.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
from l9_ci.providers import ProviderState
from l9_ci.providers.semgrep import SemgrepProvider

RELEASE_POLICY = Path(".l9/release-policy.yaml")


def _policy() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(RELEASE_POLICY.read_text(encoding="utf-8"))
    return data


def test_provider_state_matches_release_policy_current_state() -> None:
    declared = _policy()["Semgrep"]["current_state"]
    actual = SemgrepProvider().metadata.state.value
    assert actual == declared, (
        f"provider state {actual!r} disagrees with release-policy "
        f"current_state {declared!r}"
    )


def test_provider_stays_experimental_while_blockers_remain() -> None:
    blockers = _policy()["Semgrep"].get("blockers", [])
    state = SemgrepProvider().metadata.state
    if blockers:
        assert state is not ProviderState.SUPPORTED, (
            "Semgrep must not be promoted to SUPPORTED while release-policy "
            f"blockers remain: {blockers}"
        )
        assert state is ProviderState.EXPERIMENTAL
