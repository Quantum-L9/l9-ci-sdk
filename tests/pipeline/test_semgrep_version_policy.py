"""Pipeline-level Semgrep version enforcement (DWA-004, QA-004).

The version policy previously existed only in a helper that the pipeline never
called, so an unsupported (or unparseable) provider version could be recorded in
a canonical bundle. These tests assert the pipeline rejects such versions before
any bundle is written, and accepts supported versions.
"""

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
    [
        "fixture-version",  # not a semantic version at all
        "1.99.0",  # below the 1.100.0 minimum
        "0.1.2",  # far below minimum
    ],
)
def test_pipeline_rejects_unsupported_version(tmp_path: Path, version: str) -> None:
    with pytest.raises(UnsupportedProviderVersionError):
        run_semgrep_pipeline(_request(tmp_path, version))
    # No canonical bundle may be produced from an unsupported report version.
    assert not (tmp_path / "bundle.json").exists()


@pytest.mark.parametrize("version", ["1.100.0", "1.101.2", "2.0.0"])
def test_pipeline_accepts_supported_version(tmp_path: Path, version: str) -> None:
    # Default policy has an open-ended upper bound, so any version >= 1.100.0 is
    # accepted; the pipeline proceeds past version enforcement and writes a
    # bundle. (Upper-bound enforcement is covered in tests/.../test_versioning.py.)
    result = run_semgrep_pipeline(_request(tmp_path, version))
    assert result.output_path.exists()


def test_missing_version_skips_enforcement(tmp_path: Path) -> None:
    result = run_semgrep_pipeline(_request(tmp_path, None))
    assert result.output_path.exists()
