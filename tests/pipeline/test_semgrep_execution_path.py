from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from l9_ci.contracts import CoverageStatus, ProviderFailureType
from l9_ci.gates import GateStatus, evaluate_gate
from l9_ci.pipeline import (
    SemgrepPipelineRequest,
    UnsupportedProviderVersionError,
    run_semgrep_pipeline,
)


def write_fake_semgrep(path: Path, version: str = "1.170.0") -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"VERSION={version!r}\n"
        "if '--version' in sys.argv:\n"
        "    print(VERSION); raise SystemExit(0)\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--json-output') + 1])\n"
        "root = pathlib.Path(sys.argv[-1])\n"
        "out.parent.mkdir(parents=True, exist_ok=True)\n"
        "out.write_text(json.dumps({'version':VERSION,'results':[],'errors':[],"
        "'paths':{'scanned':[str((root/'sample.py').relative_to(root))],'skipped':[]}}))\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def request(tmp_path: Path, *, required: bool = True) -> SemgrepPipelineRequest:
    repository = tmp_path / "repo"
    repository.mkdir(exist_ok=True)
    (repository / "sample.py").write_text("x = 1\n", encoding="utf-8")
    return SemgrepPipelineRequest(
        report_path=tmp_path / "raw/report.json",
        repository_root=repository,
        snapshot_id="snapshot-1",
        SDK_version="1.0.0",
        output_path=tmp_path / "bundle.json",
        required=required,
        generated_at="2026-07-21T13:46:27Z",
        execute=True,
        execution_arguments=("--config", "p/python"),
    )


def test_execute_path_detects_version_and_writes_complete_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_semgrep(bin_dir / "semgrep")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    result = run_semgrep_pipeline(request(tmp_path))
    assert result.bundle.providers[0].mode == "execute"
    assert result.bundle.providers[0].provider_version == "1.170.0"
    assert result.bundle.coverage[0].status is CoverageStatus.COMPLETE
    assert (tmp_path / "raw/report.json").is_file()


def test_execute_path_rejects_unsupported_detected_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_semgrep(bin_dir / "semgrep", version="2.0.0")
    monkeypatch.setenv("PATH", str(bin_dir))
    with pytest.raises(UnsupportedProviderVersionError):
        run_semgrep_pipeline(request(tmp_path))
    assert not (tmp_path / "bundle.json").exists()


def test_missing_executable_becomes_structured_required_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    result = run_semgrep_pipeline(request(tmp_path))
    assert result.bundle.coverage[0].status is CoverageStatus.FAILED
    assert result.bundle.provider_failures[0].failure_type is ProviderFailureType.NOT_INSTALLED
    assert evaluate_gate(result.bundle).status is GateStatus.INCOMPLETE


def test_import_requires_explicit_version(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"results": [], "errors": [], "paths": {"scanned": ["x.py"], "skipped": []}}))
    base = dict(
        report_path=report,
        repository_root=tmp_path,
        snapshot_id="snapshot-1",
        SDK_version="1.0.0",
        output_path=tmp_path / "bundle.json",
    )
    with pytest.raises(ValueError, match="provider_version"):
        run_semgrep_pipeline(SemgrepPipelineRequest(**base, generated_at="2026-01-01T00:00:00Z"))
