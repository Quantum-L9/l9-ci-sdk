"""Provider lifecycle resolution is active for import and execute acquisition."""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_ci.pipeline.lifecycle import (
    ProviderAcquisitionMode,
    resolve_import_provider,
    resolve_provider,
)
from l9_ci.providers.semgrep import SemgrepProvider


def test_import_resolver_remains_compatible(tmp_path: Path) -> None:
    provider = resolve_import_provider("semgrep", repository_root=tmp_path)
    assert isinstance(provider, SemgrepProvider)


def test_execute_resolver_returns_requested_provider_for_structured_preflight(
    tmp_path: Path,
) -> None:
    # Even when capability/detection selection returns nothing, the explicit
    # request reaches the bounded runner, which emits NOT_INSTALLED/configuration
    # failure rather than silently dropping the provider.
    provider = resolve_provider(
        "semgrep",
        mode=ProviderAcquisitionMode.EXECUTE,
        repository_root=tmp_path,
    )
    assert isinstance(provider, SemgrepProvider)


def test_unknown_provider_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown provider_id"):
        resolve_provider(
            "unknown",
            mode=ProviderAcquisitionMode.IMPORT,
            repository_root=tmp_path,
        )
