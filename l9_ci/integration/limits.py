"""Operational execution and artifact limits."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OperationalLimits:
    timeout_seconds: int = 900
    process_output_limit_bytes: int = 10 * 1024 * 1024
    report_size_limit_bytes: int = 100 * 1024 * 1024
    finding_count_limit: int = 100_000
    evidence_count_limit: int = 200_000

    def __post_init__(self) -> None:
        for field_name in (
            "timeout_seconds",
            "process_output_limit_bytes",
            "report_size_limit_bytes",
            "finding_count_limit",
            "evidence_count_limit",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive")


def validate_report_size(
    report_path: Path,
    limits: OperationalLimits,
) -> None:
    try:
        size = report_path.stat().st_size
    except FileNotFoundError as exc:
        raise ValueError(f"report not found: {report_path}") from exc
    if size > limits.report_size_limit_bytes:
        raise ValueError(
            f"report exceeds size limit: {size} > {limits.report_size_limit_bytes}"
        )


def validate_record_counts(
    *,
    finding_count: int,
    evidence_count: int,
    limits: OperationalLimits,
) -> None:
    if finding_count > limits.finding_count_limit:
        raise ValueError(
            f"finding count exceeds limit: {finding_count} > "
            f"{limits.finding_count_limit}"
        )
    if evidence_count > limits.evidence_count_limit:
        raise ValueError(
            f"evidence count exceeds limit: {evidence_count} > "
            f"{limits.evidence_count_limit}"
        )
