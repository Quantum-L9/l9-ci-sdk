"""Canonical pipeline Semgrep provenance enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_ci.pipeline import (
    SemgrepPipelineRequest,
    UnsupportedProviderVersionError,
    run_semgrep_pipeline,
)

ZERO_FINDINGS = Path("tests/fixtures/semgrep/zero-findings-no-paths.json")


def _request(tmp_path: Path, version: str | None) -> SemgrepPipelineRequest:
    return SemgrepPipelineRequest(
        report_path=ZERO_FINDINGS,
        repository_root=Path(".").resolve(),
        snapshot_id="snapshot-1",
        SDK_version="1.0.0",
        output_path=tmp_path / "bundle.json",
        provider_version=version,
        generated_at="2026-07-17T00:00:00Z",
    )


@pytest.mark.parametrize(
    "version",
    ["fixture-version", "1.99.0", "0.1.2", "2.0.0", "2.1.3"],
)
def test_pipeline_rejects_unsupported_version(tmp_path: Path, version: str) -> None:
    with pytest.raises(UnsupportedProviderVersionError):
        run_semgrep_pipeline(_request(tmp_path, version))
    assert not (tmp_path / "bundle.json").exists()


@pytest.mark.parametrize("version", ["1.100.0", "1.170.0", "1.999.999"])
def test_pipeline_accepts_supported_version(tmp_path: Path, version: str) -> None:
    assert run_semgrep_pipeline(_request(tmp_path, version)).output_path.exists()


def test_import_rejects_missing_report_provenance(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="provider_version"):
        run_semgrep_pipeline(_request(tmp_path, None))
    assert not (tmp_path / "bundle.json").exists()
