"""
L9_META
l9_schema: 1
origin: l9-ci-universal-base
layer: [sdk, agent-payload]
tags: [L9_TEMPLATE, ci-summary, agent-payload, matrix-safe]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from l9_ci import __version__
from l9_ci.agent_payload.schema import AgentReviewPayload, ArtifactProvenance, MatrixRun, NormalizedFinding

PASSING = {"success", "skipped", "neutral"}
AUTOFIX_SAFE_RULES = {"DEPRECATED-API", "FORMAT", "RUFF-FORMAT", "CONFIG-KEY-RENAME"}


class AgentPayloadError(ValueError):
    """Raised when CI summary aggregation cannot produce trustworthy evidence."""


def _read_summary(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AgentPayloadError(f"Malformed CI summary JSON: {path}: {exc}") from exc
    for key in ("stage", "status", "matrix_id"):
        if key not in payload:
            raise AgentPayloadError(f"CI summary missing required key {key!r}: {path}")
    return payload


def _summary_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise AgentPayloadError(f"CI summary input directory does not exist: {input_dir}")
    files = sorted(input_dir.rglob("*_ci_summary.json"))
    if not files:
        raise AgentPayloadError(f"No CI summary files found in: {input_dir}")
    return files


def _stable_hash(paths: list[Path], base: Path) -> str:
    # Hash paths RELATIVE to a stable base (the summary input dir), not their
    # absolute location. Absolute paths embed the runner's working directory,
    # which makes the digest vary across runners/checkouts even when the CI
    # summaries are byte-identical.
    digest = hashlib.sha256()
    base = base.resolve()
    for path in paths:
        try:
            rel = path.resolve().relative_to(base).as_posix()
        except ValueError:
            rel = path.name
        digest.update(rel.encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"unreadable")
    return digest.hexdigest()


def _normalize_finding(raw: dict[str, Any], *, stage: str, matrix_id: str, status: str) -> NormalizedFinding:
    rule_id = str(raw.get("rule_id") or raw.get("rule") or "UNKNOWN")
    mode = str(raw.get("mode") or ("blocking" if status not in PASSING else "advisory"))
    if mode not in {"blocking", "advisory", "shadow", "disabled"}:
        mode = "blocking"
    autofix_safe = bool(raw.get("autofix_safe") or raw.get("autofix")) or rule_id in AUTOFIX_SAFE_RULES
    line_raw = raw.get("line")
    try:
        line = int(line_raw) if line_raw not in (None, "") else None
    except (TypeError, ValueError):
        line = None
    return NormalizedFinding(
        rule_id=rule_id,
        message=str(raw.get("message") or raw.get("text") or ""),
        file=str(raw.get("file") or ""),
        line=line,
        severity=str(raw.get("severity") or ("high" if mode == "blocking" else "medium")),
        mode=mode,  # type: ignore[arg-type]
        stage=stage,
        matrix_id=matrix_id,
        autofix_safe=autofix_safe,
        recommended_action=str(raw.get("recommended_action") or raw.get("action") or ""),
    )


def _repo_context(repo_root: Path) -> dict[str, str | None]:
    return {
        "repo": os.environ.get("GITHUB_REPOSITORY") or repo_root.name,
        "commit": os.environ.get("GITHUB_SHA") or "Unknown",
        "branch": os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or "Unknown",
        "pr_number": os.environ.get("GITHUB_PR_NUMBER"),
    }


def render_agent_payload(
    *,
    input_dir: Path,
    output: Path | None = None,
    repo_root: Path | None = None,
    required_stages: list[str] | None = None,
    optional_stages: list[str] | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    input_dir = input_dir.resolve()
    files = _summary_files(input_dir)
    seen_keys: set[tuple[str, str]] = set()
    duplicate_keys: list[str] = []
    summaries: list[tuple[Path, dict[str, Any]]] = []
    for path in files:
        summary = _read_summary(path)
        key = (str(summary["stage"]), str(summary["matrix_id"] or "default"))
        if key in seen_keys:
            duplicate_keys.append(f"{key[0]}:{key[1]}")
        seen_keys.add(key)
        summaries.append((path, summary))
    if duplicate_keys:
        raise AgentPayloadError("Duplicate stage/matrix CI summaries found: " + ", ".join(sorted(duplicate_keys)))

    required = set(required_stages or [])
    optional = set(optional_stages or [])
    observed_stages = {str(summary["stage"]) for _, summary in summaries}
    missing_required = sorted(required - observed_stages)
    missing_optional = sorted(optional - observed_stages)
    if missing_required:
        raise AgentPayloadError("Missing required CI summary stages: " + ", ".join(missing_required))

    blocking: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    failed_checks: list[dict[str, Any]] = []
    skipped_checks: list[dict[str, Any]] = []
    infra_failures: list[dict[str, Any]] = []
    autofix_candidates: list[dict[str, Any]] = []
    manual_review_required: list[dict[str, Any]] = []
    matrix_runs: list[dict[str, Any]] = []

    for path, summary in summaries:
        stage = str(summary["stage"])
        matrix_id = str(summary.get("matrix_id") or "default")
        status = str(summary["status"])
        findings_raw = list(summary.get("findings") or [])
        matrix_runs.append(
            MatrixRun(
                stage=stage,
                matrix_id=matrix_id,
                matrix=dict(summary.get("matrix") or {}),
                status=status,
                summary_path=str(path.relative_to(input_dir)),
                duration_seconds=float(summary.get("duration_seconds") or 0.0),
                findings_count=len(findings_raw),
            ).to_dict()
        )
        if status not in PASSING:
            failed_checks.append({"stage": stage, "matrix_id": matrix_id, "status": status, "summary_path": str(path.relative_to(input_dir))})
        if status == "skipped":
            skipped_checks.append({"stage": stage, "matrix_id": matrix_id, "summary_path": str(path.relative_to(input_dir))})
        for raw in findings_raw:
            finding = _normalize_finding(raw, stage=stage, matrix_id=matrix_id, status=status).to_dict()
            if finding["mode"] == "blocking":
                blocking.append(finding)
            elif finding["mode"] in {"advisory", "shadow"}:
                advisory.append(finding)
            if finding["autofix_safe"] and finding["mode"] != "disabled":
                autofix_candidates.append(finding)
            elif finding["mode"] == "blocking":
                manual_review_required.append(finding)

    for stage in missing_optional:
        advisory.append(
            NormalizedFinding(
                rule_id="OPTIONAL-STAGE-MISSING",
                message=f"Optional CI summary stage missing: {stage}",
                severity="low",
                mode="advisory",
                stage=stage,
            ).to_dict()
        )

    context = _repo_context(root)
    gate_status = "fail" if blocking or failed_checks else "pass"
    next_actions = []
    if blocking:
        next_actions.append("Fix blocking findings before merge.")
    if failed_checks:
        next_actions.append("Inspect failed stage summaries and rerun the failed stage locally.")
    if not next_actions:
        next_actions.append("No blocking CI action required.")
    provenance = ArtifactProvenance(
        input_dir=str(input_dir),
        consumed_files=[str(path.relative_to(input_dir)) for path, _ in summaries],
        missing_expected_files=missing_optional,
        duplicate_matrix_ids=[],
    )
    payload = AgentReviewPayload(
        repo=str(context["repo"]),
        commit=str(context["commit"]),
        branch=str(context["branch"]),
        pr_number=context["pr_number"],
        pr_class="unknown_diff" if any(item.get("stage") == "classify" and item.get("status") != "success" for item in matrix_runs) else "Unknown",
        gate_status=gate_status,  # type: ignore[arg-type]
        rule_modes_hash="Unknown",
        policy_hash=_stable_hash(files, input_dir),
        blocking_findings=blocking,
        advisory_findings=advisory,
        failed_checks=failed_checks,
        skipped_checks=skipped_checks,
        infrastructure_failures=infra_failures,
        autofix_candidates=autofix_candidates,
        manual_review_required=manual_review_required,
        next_actions=next_actions,
        matrix_runs=matrix_runs,
        artifact_provenance=provenance.to_dict(),
        provenance={
            "l9_ci_version": __version__,
            "generated_at": datetime.now(UTC).isoformat(),
            "source_policy_files": [],
        },
    ).to_dict()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
