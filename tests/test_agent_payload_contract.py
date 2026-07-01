"""Verifies the l9-ci CLI emitter contract that l9-ci-core and PR_Repair depend on.

The contract: ``l9-ci run-pipeline --stage <s> --ci github --emit-dir <dir>``
writes per-stage ``*_ci_summary.json``, and ``l9-ci gate --input-dir <dir>
--emit-agent-payload <path>`` aggregates them into an ``agent_review_payload.json``
carrying the fields required by the payload schema in Quantum-L9/l9-ci-core.
"""

from __future__ import annotations

import json
from pathlib import Path

from l9_ci.cli import main

# Top-level keys required by
# Quantum-L9/l9-ci-core :: schemas/agent-review-payload.schema.json
REQUIRED_KEYS = {
    "repo",
    "commit",
    "branch",
    "pr_class",
    "gate_status",
    "blocking_findings",
    "advisory_findings",
    "failed_checks",
    "skipped_checks",
    "autofix_candidates",
    "manual_review_required",
    "matrix_runs",
    "artifact_provenance",
    "provenance",
}


def test_run_pipeline_emits_stage_summary(tmp_path: Path) -> None:
    emit = tmp_path / "ci"
    rc = main(["run-pipeline", "--stage", "validate", "--ci", "github", "--emit-dir", str(emit)])
    # A stage may pass (0) or fail (1); the contract is that it emits a summary.
    assert rc in (0, 1)
    assert list(emit.glob("*_ci_summary.json")), "run-pipeline --emit-dir must write a summary"


def test_gate_emits_agent_payload_with_contract_keys(tmp_path: Path) -> None:
    emit = tmp_path / "ci"
    for stage in ("validate", "lint", "security"):
        main(["run-pipeline", "--stage", stage, "--ci", "github", "--emit-dir", str(emit)])

    payload_path = tmp_path / "agent_review_payload.json"
    main(
        [
            "gate",
            "--input-dir",
            str(emit),
            "--required",
            "validate,lint,security",
            "--emit-agent-payload",
            str(payload_path),
        ]
    )

    assert payload_path.is_file(), "gate --emit-agent-payload must write the payload"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    missing = REQUIRED_KEYS - set(payload)
    assert not missing, f"payload missing contract keys: {sorted(missing)}"
