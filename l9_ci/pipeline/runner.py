from __future__ import annotations

from pathlib import Path

from l9_ci.pipeline.context import PipelineContext, derive_matrix_id, parse_matrix_pairs
from l9_ci.pipeline.results import StageResult
from l9_ci.pipeline.stages import STAGES

DEFAULT_STAGE_ORDER = ["classify", "validate", "thresholds", "transport-contract", "deprecated-api", "lint", "test", "security", "gate"]


def build_context(
    *,
    root: Path,
    stage: str,
    ci: str | None = None,
    matrix_values: list[str] | None = None,
    matrix_id: str | None = None,
    emit_json: str | None = None,
    emit_dir: str | None = None,
) -> PipelineContext:
    matrix = parse_matrix_pairs(matrix_values or [])
    resolved_matrix_id = derive_matrix_id(matrix, matrix_id, ci=ci)
    return PipelineContext(
        root=root.resolve(),
        stage=stage,
        ci=ci,
        matrix=matrix,
        matrix_id=resolved_matrix_id,
        emit_json=Path(emit_json) if emit_json else None,
        emit_dir=Path(emit_dir) if emit_dir else None,
    )


def run_stage(ctx: PipelineContext) -> StageResult:
    if ctx.stage not in STAGES:
        raise ValueError(f"Unknown pipeline stage: {ctx.stage}")
    result = STAGES[ctx.stage](ctx)
    output = ctx.output_path()
    if output is not None:
        result.write_json(output)
    return result


def run_pipeline(
    *,
    root: Path,
    stage: str | None = None,
    ci: str | None = None,
    matrix_values: list[str] | None = None,
    matrix_id: str | None = None,
    emit_json: str | None = None,
    emit_dir: str | None = None,
) -> list[StageResult]:
    stages = [stage] if stage else DEFAULT_STAGE_ORDER
    if len(stages) > 1 and emit_json:
        raise ValueError("--emit-json can only be used with a single --stage. Use --emit-dir for full pipeline output.")
    results: list[StageResult] = []
    for stage_name in stages:
        ctx = build_context(root=root, stage=stage_name, ci=ci, matrix_values=matrix_values, matrix_id=matrix_id, emit_json=emit_json, emit_dir=emit_dir)
        results.append(run_stage(ctx))
    return results


def format_results(results: list[StageResult]) -> str:
    lines = ["L9 Pipeline Results"]
    for result in results:
        lines.append(f"  {result.stage}[{result.matrix_id}]: {result.status}")
        for finding in result.findings:
            location = finding.get("file", "<unknown>")
            rule = finding.get("rule_id", "UNKNOWN")
            message = finding.get("message", "")
            lines.append(f"    {location}: {rule}: {message}")
    return "\n".join(lines)


def results_exit_code(results: list[StageResult]) -> int:
    return 0 if all(result.passed for result in results) else 1
