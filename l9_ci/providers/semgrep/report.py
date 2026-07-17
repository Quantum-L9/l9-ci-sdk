"""Semgrep JSON report shape validation."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class SemgrepReportValidation:
    valid: bool
    errors: tuple[str, ...]

    def require_valid(self) -> None:
        if self.errors:
            joined = "\n".join(f"- {error}" for error in self.errors)
            raise ValueError(f"invalid Semgrep report:\n{joined}")


def _validate_position(
    value: Any,
    *,
    path: str,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping):
        errors.append(f"{path} must be an object")
        return
    line = value.get("line")
    column = value.get("col")
    if not isinstance(line, int) or line < 1:
        errors.append(f"{path}.line must be a positive integer")
    if not isinstance(column, int) or column < 1:
        errors.append(f"{path}.col must be a positive integer")


def validate_semgrep_report(
    payload: Mapping[str, Any],
) -> SemgrepReportValidation:
    errors: list[str] = []
    results = payload.get("results")
    if not isinstance(results, Sequence) or isinstance(results, str | bytes):
        errors.append("results must be an array")
        results = []
    report_errors = payload.get("errors", [])
    if not isinstance(report_errors, Sequence) or isinstance(
        report_errors,
        str | bytes,
    ):
        errors.append("errors must be an array when present")
    for index, result in enumerate(results):
        prefix = f"results[{index}]"
        if not isinstance(result, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        check_id = result.get("check_id")
        if not isinstance(check_id, str) or not check_id.strip():
            errors.append(f"{prefix}.check_id must be a non-empty string")
        path = result.get("path")
        if not isinstance(path, str) or not path.strip():
            errors.append(f"{prefix}.path must be a non-empty string")
        _validate_position(
            result.get("start"),
            path=f"{prefix}.start",
            errors=errors,
        )
        _validate_position(
            result.get("end"),
            path=f"{prefix}.end",
            errors=errors,
        )
        extra = result.get("extra")
        if not isinstance(extra, Mapping):
            errors.append(f"{prefix}.extra must be an object")
            continue
        message = extra.get("message")
        if not isinstance(message, str) or not message.strip():
            errors.append(f"{prefix}.extra.message must be non-empty")
        severity = extra.get("severity")
        if severity is not None and not isinstance(severity, str):
            errors.append(f"{prefix}.extra.severity must be a string")
        metadata = extra.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            errors.append(f"{prefix}.extra.metadata must be an object")
    return SemgrepReportValidation(
        valid=not errors,
        errors=tuple(errors),
    )
