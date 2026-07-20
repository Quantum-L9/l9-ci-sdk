"""Provider lifecycle seam (DWA-001).

The registry-backed selection plane was unreachable from any runtime entrypoint.
``resolve_import_provider`` now exercises capability detection + execution-profile
selection on the canonical import path. These tests confirm it resolves the
provider and falls back safely when the repository surfaces no candidate.
"""

from __future__ import annotations
from pathlib import Path
import pytest
from l9_ci.pipeline import resolve_import_provider
from l9_ci.providers.semgrep import SemgrepProvider


def test_resolve_returns_semgrep_provider(tmp_path: Path) -> None:
    provider = resolve_import_provider("semgrep", repository_root=tmp_path)
    assert provider.metadata.provider_id == "semgrep"
    assert isinstance(provider, SemgrepProvider)


def test_resolve_falls_back_when_not_a_candidate(tmp_path: Path) -> None:
    # An empty repository surfaces no provider candidates, so selection returns
    # nothing; the seam must still return the configured provider so an
    # explicitly supplied report is normalized.
    provider = resolve_import_provider("semgrep", repository_root=tmp_path)
    assert provider.metadata.provider_id == "semgrep"


def test_unknown_provider_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_import_provider("nonexistent", repository_root=tmp_path)
