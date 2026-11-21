"""Scope evidence of a required run travels inside the finding bundle.

CTO decision 4 (lane L1-CANARY-FIXES B1+B2, 2026-11-20): the evidence of what a
required Semgrep run was given to scan, and what it reports having scanned,
lives in the finding bundle, so a consumer of the bundle never has to find a
side file to judge coverage. ``coverage[].scan_scope`` carries the declared
``l9.semgrep-scan-scope/v1`` record and a digest of the provider's own
``paths.scanned``; the ``<stem>.scope.json`` side file stays, because it is
written before Semgrep starts and survives a run that never produces a bundle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.contracts import FINDING_BUNDLE_SCHEMA_VERSION
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline
from l9_ci.pipeline.semgrep import _paths_scanned
from l9_ci.rulesets.semgrep.scope import ScanScope, packaged_scan_scope_policy

FIXTURE = Path("tests/fixtures/semgrep/results.json")


def _declared() -> dict[str, object]:
    return ScanScope(
        policy=packaged_scan_scope_policy(),
        targets=("src/app.py", "tests/test_app.py"),
        files_tracked=3,
        excluded=(("directory_names:vendor", ("vendor/dep.py",)),),
        consumer_semgrepignore_files=(),
    ).to_dict()


def _run(tmp_path: Path, *, scan_scope: dict[str, object] | None, report: Path):  # type: ignore[no-untyped-def]
    output = tmp_path / "bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=report,
            repository_root=Path(".").resolve(),
            snapshot_id="snapshot-1",
            SDK_version="2.0.0-test",
            output_path=output,
            provider_version="1.100.0",
            required=True,
            generated_at="2026-11-20T00:00:00Z",
            scan_scope=scan_scope,
        )
    )
    return output


def test_required_bundle_carries_declared_scope_and_paths_scanned(
    tmp_path: Path,
) -> None:
    declared = _declared()
    output = _run(tmp_path, scan_scope=declared, report=FIXTURE)
    bundle = load_and_validate_bundle(output)
    assert bundle.schema_version == FINDING_BUNDLE_SCHEMA_VERSION == "1.1.0"
    (coverage,) = bundle.coverage
    assert coverage.scan_scope is not None
    assert coverage.scan_scope["declared"] == declared
    scanned = sorted(json.loads(FIXTURE.read_text("utf-8"))["paths"]["scanned"])
    assert coverage.scan_scope["paths_scanned"] == {
        "count": len(scanned),
        "sha256": hashlib.sha256("\n".join(scanned).encode("utf-8")).hexdigest(),
    }


def test_bundle_without_a_declared_scope_is_unchanged(tmp_path: Path) -> None:
    output = _run(tmp_path, scan_scope=None, report=FIXTURE)
    payload = json.loads(output.read_text("utf-8"))
    assert "scan_scope" not in payload["coverage"][0]


def test_unreadable_scanned_inventory_is_recorded_as_unknown(tmp_path: Path) -> None:
    """Known-bad: no report, or no paths.scanned list, is never an inventory."""
    assert _paths_scanned(tmp_path / "missing.json") is None
    for payload in ("[]", '{"paths": {}}', '{"paths": {"scanned": [1]}}', "{"):
        report = tmp_path / "report.json"
        report.write_text(payload, encoding="utf-8")
        assert _paths_scanned(report) is None


def test_scanned_digest_is_order_and_prefix_independent(tmp_path: Path) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text('{"paths": {"scanned": ["b.py", "a.py"]}}', encoding="utf-8")
    second.write_text('{"paths": {"scanned": ["./a.py", "b.py"]}}', encoding="utf-8")
    assert _paths_scanned(first) == _paths_scanned(second)
    assert _paths_scanned(first) == {
        "count": 2,
        "sha256": hashlib.sha256(b"a.py\nb.py").hexdigest(),
    }
