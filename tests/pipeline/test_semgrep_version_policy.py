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
        "2.0.0",  # at the exclusive 2.0.0 upper bound (unvalidated major)
        "2.1.3",  # above the upper bound
    ],
)
def test_pipeline_rejects_unsupported_version(tmp_path: Path, version: str) -> None:
    with pytest.raises(UnsupportedProviderVersionError):
        run_semgrep_pipeline(_request(tmp_path, version))
    # No canonical bundle may be produced from an unsupported report version.
    assert not (tmp_path / "bundle.json").exists()


@pytest.mark.parametrize("version", ["1.100.0", "1.101.2", "1.999.999"])
def test_pipeline_accepts_supported_version(tmp_path: Path, version: str) -> None:
    # Default policy is the closed range >=1.100.0,<2.0.0: both edges are
    # exercised here (lowest supported version and the highest version below
    # the exclusive 2.0.0 bound). Unvalidated majors are rejected above.
    result = run_semgrep_pipeline(_request(tmp_path, version))
    assert result.output_path.exists()


def test_missing_version_skips_enforcement(tmp_path: Path) -> None:
    result = run_semgrep_pipeline(_request(tmp_path, None))
    assert result.output_path.exists()
