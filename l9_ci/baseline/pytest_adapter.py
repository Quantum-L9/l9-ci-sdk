"""Pytest result adapter.

Consumes the JSON report produced by ``pytest --report-log`` (the
built-in report-log plugin writes one JSON object per line) and
normalizes every test node into observed findings.

Outcomes are distinguished as:

- ``failed`` call phase        -> failure finding
- ``failed`` setup/teardown    -> error finding
- collection error             -> collection-failure finding
- ``skipped`` / xfail          -> recorded, never a finding
- ``passed``                   -> recorded as passing identity

Only deterministic string processing is used; no LLM participates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from .comparison import ObservedFinding
from .fingerprint import normalize_failure_text, fingerprint_for_test_failure

PYTEST_GATE = "tests/pytest"

_RULE_BY_KIND = {
    "failure": "pytest-failure",
    "error": "pytest-error",
    "collection": "pytest-collection-failure",
}


@dataclass(frozen=True, slots=True)
class PytestRunResult:
    """Normalized outcome of one full pytest run."""

    findings: tuple[ObservedFinding, ...]
    passing_node_ids: tuple[str, ...]
    skipped_node_ids: tuple[str, ...]
    xfailed_node_ids: tuple[str, ...]
    total_collected: int


def _iter_report_lines(path: Path) -> Iterator[Mapping[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"report log {path} contains invalid JSON: {exc}"
                    ) from exc
                if isinstance(record, Mapping):
                    yield record
    except OSError as exc:
        raise ValueError(f"cannot read pytest report log {path}: {exc}") from exc


def _extract_exception_type(longrepr: Any, crash: Mapping[str, Any] | None) -> str:
    if crash and isinstance(crash.get("message"), str):
        message = crash["message"]
        head = message.split(":", 1)[0].strip()
        if head and " " not in head and head[0].isalpha():
            return head
    if isinstance(longrepr, str):
        for line in reversed(longrepr.splitlines()):
            line = line.strip()
            if line.startswith("E "):
                candidate = line[2:].strip().split(":", 1)[0].strip()
                if candidate and " " not in candidate:
                    return candidate
    return "UnknownError"


def _extract_signature(longrepr: Any, crash: Mapping[str, Any] | None) -> str:
    if crash and isinstance(crash.get("message"), str):
        return crash["message"]
    if isinstance(longrepr, str):
        error_lines = [
            line.strip()[2:].strip()
            for line in longrepr.splitlines()
            if line.strip().startswith("E ")
        ]
        if error_lines:
            return " | ".join(error_lines[:3])
        tail = longrepr.strip().splitlines()
        if tail:
            return tail[-1].strip()
    return "no-failure-signature"


def _node_path(node_id: str) -> str:
    return node_id.split("::", 1)[0] or node_id


def _finding_from_report(
    node_id: str,
    kind: str,
    longrepr: Any,
    crash: Mapping[str, Any] | None,
) -> ObservedFinding:
    exception_type = _extract_exception_type(longrepr, crash)
    signature = normalize_failure_text(_extract_signature(longrepr, crash))
    fingerprint = fingerprint_for_test_failure(node_id, exception_type, signature)
    return ObservedFinding(
        gate=PYTEST_GATE,
        rule=_RULE_BY_KIND[kind],
        fingerprint=fingerprint,
        path=_node_path(node_id),
        identity=node_id,
        message=signature,
        exception_type=exception_type,
        attributes={"kind": kind},
    )


def parse_report_log(path: Path) -> PytestRunResult:
    """Parse a ``pytest --report-log`` JSONL file into normalized results."""
    findings: dict[str, ObservedFinding] = {}
    passing: set[str] = set()
    skipped: set[str] = set()
    xfailed: set[str] = set()
    collected = 0

    for record in _iter_report_lines(path):
        record_type = record.get("$report_type")
        if record_type == "CollectReport":
            if record.get("outcome") == "failed":
                node_id = str(record.get("nodeid") or "collection-root")
                if not node_id:
                    node_id = "collection-root"
                longrepr = record.get("longrepr")
                finding = _finding_from_report(
                    node_id, "collection", _flatten_longrepr(longrepr), None
                )
                findings[finding.identity] = finding
            continue
        if record_type != "TestReport":
            continue
        node_id = str(record.get("nodeid", ""))
        if not node_id:
            continue
        when = record.get("when")
        outcome = record.get("outcome")
        keywords = record.get("keywords", {})
        wasxfail = isinstance(keywords, Mapping) and "xfail" in keywords

        if when == "call" and outcome == "passed":
            if node_id not in findings:
                passing.add(node_id)
            collected += 1
            continue
        if outcome == "skipped":
            longrepr = record.get("longrepr")
            if _is_xfail(record):
                xfailed.add(node_id)
            else:
                skipped.add(node_id)
            if when == "call" or when == "setup":
                collected += 1
            continue
        if outcome == "failed":
            longrepr = _flatten_longrepr(record.get("longrepr"))
            crash = _extract_crash(record.get("longrepr"))
            kind = "failure" if when == "call" else "error"
            if wasxfail and when == "call":
                # xpass(strict) reports as failed; treat as failure.
                kind = "failure"
            finding = _finding_from_report(node_id, kind, longrepr, crash)
            findings[node_id] = finding
            passing.discard(node_id)
            if when == "call" or when == "setup":
                collected += 1
            continue

    ordered = tuple(findings[key] for key in sorted(findings))
    return PytestRunResult(
        findings=ordered,
        passing_node_ids=tuple(sorted(passing - set(findings))),
        skipped_node_ids=tuple(sorted(skipped)),
        xfailed_node_ids=tuple(sorted(xfailed)),
        total_collected=collected,
    )


def _is_xfail(record: Mapping[str, Any]) -> bool:
    if record.get("wasxfail") is not None:
        return True
    longrepr = record.get("longrepr")
    if isinstance(longrepr, (list, tuple)) and len(longrepr) == 3:
        reason = str(longrepr[2])
        return reason.lower().startswith(("xfail", "expected fail"))
    return False


def _flatten_longrepr(longrepr: Any) -> str:
    if longrepr is None:
        return ""
    if isinstance(longrepr, str):
        return longrepr
    if isinstance(longrepr, (list, tuple)):
        return "\n".join(str(part) for part in longrepr)
    if isinstance(longrepr, Mapping):
        chunks: list[str] = []
        reprcrash = longrepr.get("reprcrash")
        if isinstance(reprcrash, Mapping) and reprcrash.get("message"):
            chunks.append(str(reprcrash["message"]))
        reprtraceback = longrepr.get("reprtraceback")
        if isinstance(reprtraceback, Mapping):
            for entry in reprtraceback.get("reprentries", []) or []:
                if isinstance(entry, Mapping):
                    data = entry.get("data")
                    if isinstance(data, Mapping):
                        lines = data.get("lines")
                        if isinstance(lines, list):
                            chunks.extend(str(line) for line in lines)
        return "\n".join(chunks)
    return str(longrepr)


def _extract_crash(longrepr: Any) -> Mapping[str, Any] | None:
    if isinstance(longrepr, Mapping):
        reprcrash = longrepr.get("reprcrash")
        if isinstance(reprcrash, Mapping):
            return reprcrash
    return None
