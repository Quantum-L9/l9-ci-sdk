"""Validation for governed evidence reports from untrusted producers."""
from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Iterator, Mapping
from urllib.parse import unquote, urlparse

from .models import Diagnostic, EvaluationResult, EvaluationStatus

_SECRET = re.compile(r"(?i)\b(api[_-]?key|client[_-]?secret|secret|access[_-]?token|password)\b\s*[:=]\s*([^\s,;]+)")
_REDACTED = {"[redacted]", "<redacted>", "redacted", "***", "xxxxx"}
_REQUIRED_TYPES: dict[str, type | tuple[type, ...]] = {
    "schema": str,
    "report_id": str,
    "producer": Mapping,
    "subject": Mapping,
    "operation": Mapping,
    "outcome": Mapping,
    "evidence_refs": list,
    "diagnostics": list,
    "limitations": list,
    "provenance": Mapping,
}


def _walk(value: Any, path: str = "", seen: set[int] | None = None) -> Iterator[tuple[str, Any]]:
    if seen is None:
        seen = set()
    if isinstance(value, (Mapping, list, tuple)):
        identity = id(value)
        if identity in seen:
            return
        seen.add(identity)
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from _walk(child, child_path, seen)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]", seen)


def _contains_secret(value: str) -> bool:
    for match in _SECRET.finditer(value):
        if match.group(2).strip().lower() not in _REDACTED:
            return True
    return False


def _looks_absolute_path(value: str) -> bool:
    stripped = value.strip()
    if PureWindowsPath(stripped).is_absolute() or PurePosixPath(stripped).is_absolute():
        return True
    parsed = urlparse(stripped)
    if parsed.scheme.lower() == "file":
        decoded = unquote(parsed.path)
        return bool(parsed.netloc) or PurePosixPath(decoded).is_absolute() or PureWindowsPath(decoded.lstrip("/")) .is_absolute()
    if parsed.scheme:
        return False
    return False


def validate_governed_report(report: Mapping[str, Any]) -> EvaluationResult:
    if not isinstance(report, Mapping):
        return EvaluationResult(EvaluationStatus.INVALID, (Diagnostic("report.input_invalid", "report must be a mapping"),))
    diagnostics: list[Diagnostic] = []
    for name, expected_type in _REQUIRED_TYPES.items():
        if name not in report:
            diagnostics.append(Diagnostic("report.required_missing", f"required report field {name!r} is missing", name))
        elif not isinstance(report[name], expected_type):
            diagnostics.append(Diagnostic("report.field_type_invalid", f"{name} has an invalid type", name))
    if report.get("schema") != "l9.evidence-report/v1":
        diagnostics.append(Diagnostic("report.schema_unsupported", "schema must be l9.evidence-report/v1", "schema"))
    if isinstance(report.get("report_id"), str) and not report["report_id"].strip():
        diagnostics.append(Diagnostic("report.report_id_invalid", "report_id must be non-empty", "report_id"))
    producer = report.get("producer")
    if isinstance(producer, Mapping) and (not isinstance(producer.get("id"), str) or not producer.get("id", "").strip()):
        diagnostics.append(Diagnostic("report.producer_invalid", "producer.id must be a non-empty string", "producer.id"))
    outcome = report.get("outcome")
    if isinstance(outcome, Mapping) and outcome.get("status") not in {"pass", "fail", "incomplete", "invalid"}:
        diagnostics.append(Diagnostic("report.outcome_invalid", "outcome.status is invalid", "outcome.status"))
    evidence_refs = report.get("evidence_refs")
    if isinstance(evidence_refs, list):
        if any(not isinstance(item, str) or not item.strip() for item in evidence_refs):
            diagnostics.append(Diagnostic("report.evidence_ref_invalid", "evidence_refs must contain non-empty strings", "evidence_refs"))
        elif len(evidence_refs) != len(set(evidence_refs)):
            diagnostics.append(Diagnostic("report.evidence_ref_duplicate", "evidence_refs must contain unique values", "evidence_refs"))
    for collection in ("diagnostics", "limitations"):
        value = report.get(collection)
        if isinstance(value, list) and collection == "limitations" and any(not isinstance(item, str) or not item.strip() for item in value):
            diagnostics.append(Diagnostic("report.limitation_invalid", "limitations must contain non-empty strings", collection))

    for path, value in _walk(report):
        if not isinstance(value, str):
            continue
        if _contains_secret(value):
            diagnostics.append(Diagnostic("report.secret_material_detected", "secret-like material is forbidden", path))
        if _looks_absolute_path(value):
            diagnostics.append(Diagnostic("report.absolute_path_detected", "absolute paths are forbidden", path))
    return EvaluationResult(EvaluationStatus.INVALID if diagnostics else EvaluationStatus.PASS, tuple(diagnostics))
