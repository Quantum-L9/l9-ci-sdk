from pathlib import Path
import pytest
from l9_ci.integration import (
    OperationalLimits,
    validate_record_counts,
    validate_report_size,
)


def test_report_size_limit(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_bytes(b"x" * 11)
    limits = OperationalLimits(
        report_size_limit_bytes=10,
    )
    with pytest.raises(ValueError, match="size limit"):
        validate_report_size(report, limits)


def test_finding_count_limit() -> None:
    limits = OperationalLimits(
        finding_count_limit=1,
    )
    with pytest.raises(ValueError, match="finding count"):
        validate_record_counts(
            finding_count=2,
            evidence_count=1,
            limits=limits,
        )


def test_evidence_count_limit() -> None:
    limits = OperationalLimits(
        evidence_count_limit=1,
    )
    with pytest.raises(ValueError, match="evidence count"):
        validate_record_counts(
            finding_count=1,
            evidence_count=2,
            limits=limits,
        )
