"""``l9-ci baseline`` command group.

Subcommands:

- ``baseline compare-tests``: compare a pytest report-log against a
  test-quarantine ledger.
- ``baseline scan-packet-envelope``: scan a repository tree for
  deprecated PacketEnvelope references and emit observed findings.
- ``baseline compare-scan``: compare observed scanner findings (JSON)
  against a baseline ledger.
- ``baseline validate-ledger``: validate a ledger file in isolation.

All subcommands are fail-closed: any internal error exits non-zero,
malformed ledgers exit non-zero, and the gate passes only when the
comparator reports zero violations.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from l9_ci.baseline import (
    BaselineComparison,
    ObservedFinding,
    compare,
    load_ledger,
    parse_report_log,
    scan_repository,
    sort_violations,
    utc_today,
)
from l9_ci.baseline.packet_envelope import (
    PACKET_ENVELOPE_GATE,
)
from l9_ci.baseline.pytest_adapter import PYTEST_GATE
from l9_ci.cli.exit_codes import ExitCode


def _emit(payload: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def _parse_evaluated_on(value: str | None) -> date:
    if value is None:
        return utc_today()
    return date.fromisoformat(value)


def _comparison_payload(comparison: BaselineComparison) -> dict[str, Any]:
    return comparison.to_dict()


def _finish(comparison: BaselineComparison, output: str | None) -> int:
    _emit(_comparison_payload(comparison), output)
    if comparison.passed:
        return int(ExitCode.SUCCESS)
    return int(ExitCode.GATE_FAILURE)


def _handle_compare_tests(args: argparse.Namespace) -> int:
    try:
        evaluated_on = _parse_evaluated_on(args.evaluated_on)
    except ValueError as exc:
        print(f"error: invalid --evaluated-on: {exc}", file=sys.stderr)
        return int(ExitCode.INVALID_ARGUMENTS)
    try:
        run_result = parse_report_log(Path(args.report_log))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.PROVIDER_REPORT_FAILURE)
    try:
        ledger = load_ledger(Path(args.ledger), entry_kind="test-quarantine")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.INVALID_ARGUMENTS)

    comparison = compare(
        PYTEST_GATE,
        run_result.findings,
        ledger.entries,
        evaluated_on=evaluated_on,
        passing_identities=run_result.passing_node_ids,
    )
    if ledger.violations:
        merged = sort_violations(tuple(comparison.violations) + ledger.violations)
        comparison = BaselineComparison(
            schema_version=comparison.schema_version,
            gate=comparison.gate,
            evaluated_on=comparison.evaluated_on,
            passed=False,
            summary=comparison.summary,
            violations=merged,
            known=comparison.known,
            new=comparison.new,
            resolved_entry_ids=comparison.resolved_entry_ids,
            suggested_removals=comparison.suggested_removals,
        )
    return _finish(comparison, args.output)


def _handle_scan_packet_envelope(args: argparse.Namespace) -> int:
    root = Path(args.repository_root)
    if not root.is_dir():
        print(f"error: repository root {root} is not a directory", file=sys.stderr)
        return int(ExitCode.INVALID_ARGUMENTS)
    findings = scan_repository(
        root,
        declaration_paths=args.declaration_path or (),
        excluded_dirs=args.exclude_dir or (),
    )
    payload = {
        "gate": PACKET_ENVELOPE_GATE,
        "findings": [finding.to_dict() for finding in findings],
        "total": len(findings),
    }
    _emit(payload, args.output)
    return int(ExitCode.SUCCESS)


def _load_observed(path: Path) -> tuple[ObservedFinding, ...]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(document, dict):
        raw_findings = document.get("findings", [])
    elif isinstance(document, list):
        raw_findings = document
    else:
        raise ValueError("observed findings document must be a list or mapping")
    findings: list[ObservedFinding] = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            raise ValueError("each observed finding must be a mapping")
        findings.append(
            ObservedFinding(
                gate=str(raw.get("gate", "")),
                rule=str(raw.get("rule", "")),
                fingerprint=str(raw.get("fingerprint", "")),
                path=str(raw.get("path", "")),
                identity=str(raw.get("identity", "")),
                message=str(raw.get("message", "")),
                exception_type=(
                    str(raw["exception_type"])
                    if raw.get("exception_type") is not None
                    else None
                ),
                attributes=dict(raw.get("attributes", {}) or {}),
            )
        )
    return tuple(findings)


def _handle_compare_scan(args: argparse.Namespace) -> int:
    try:
        evaluated_on = _parse_evaluated_on(args.evaluated_on)
    except ValueError as exc:
        print(f"error: invalid --evaluated-on: {exc}", file=sys.stderr)
        return int(ExitCode.INVALID_ARGUMENTS)
    try:
        observed = _load_observed(Path(args.findings))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: cannot load observed findings: {exc}", file=sys.stderr)
        return int(ExitCode.PROVIDER_REPORT_FAILURE)
    try:
        ledger = load_ledger(Path(args.ledger), entry_kind="baseline")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.INVALID_ARGUMENTS)

    comparison = compare(
        args.gate,
        observed,
        ledger.entries,
        evaluated_on=evaluated_on,
    )
    if ledger.violations:
        merged = sort_violations(tuple(comparison.violations) + ledger.violations)
        comparison = BaselineComparison(
            schema_version=comparison.schema_version,
            gate=comparison.gate,
            evaluated_on=comparison.evaluated_on,
            passed=False,
            summary=comparison.summary,
            violations=merged,
            known=comparison.known,
            new=comparison.new,
            resolved_entry_ids=comparison.resolved_entry_ids,
            suggested_removals=comparison.suggested_removals,
        )
    return _finish(comparison, args.output)


def _handle_validate_ledger(args: argparse.Namespace) -> int:
    try:
        ledger = load_ledger(Path(args.ledger), entry_kind=args.kind)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.INVALID_ARGUMENTS)
    payload = {
        "ledger": str(args.ledger),
        "schema_version": ledger.schema_version,
        "gate": ledger.gate,
        "entries_total": len(ledger.entries),
        "violations": [violation.to_dict() for violation in ledger.violations],
        "valid": not ledger.violations,
    }
    _emit(payload, args.output)
    if ledger.violations:
        return int(ExitCode.GATE_FAILURE)
    return int(ExitCode.SUCCESS)


def register_baseline_commands(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    parser = subparsers.add_parser(
        "baseline",
        help="baseline-ratchet debt governance (deterministic, fail-closed)",
    )
    baseline_subparsers = parser.add_subparsers(dest="baseline_command", required=True)

    compare_tests = baseline_subparsers.add_parser(
        "compare-tests",
        help="compare a pytest report-log against a test-quarantine ledger",
    )
    compare_tests.add_argument("--report-log", required=True)
    compare_tests.add_argument("--ledger", required=True)
    compare_tests.add_argument("--evaluated-on", default=None)
    compare_tests.add_argument("--output", default=None)
    compare_tests.set_defaults(handler=_handle_compare_tests)

    scan_pe = baseline_subparsers.add_parser(
        "scan-packet-envelope",
        help="scan a repository for deprecated PacketEnvelope references",
    )
    scan_pe.add_argument("--repository-root", required=True)
    scan_pe.add_argument(
        "--declaration-path",
        action="append",
        help="repository-relative path whose declaration-site usages are excluded",
    )
    scan_pe.add_argument("--exclude-dir", action="append")
    scan_pe.add_argument("--output", default=None)
    scan_pe.set_defaults(handler=_handle_scan_packet_envelope)

    compare_scan = baseline_subparsers.add_parser(
        "compare-scan",
        help="compare observed scanner findings against a baseline ledger",
    )
    compare_scan.add_argument("--gate", required=True)
    compare_scan.add_argument("--findings", required=True)
    compare_scan.add_argument("--ledger", required=True)
    compare_scan.add_argument("--evaluated-on", default=None)
    compare_scan.add_argument("--output", default=None)
    compare_scan.set_defaults(handler=_handle_compare_scan)

    validate = baseline_subparsers.add_parser(
        "validate-ledger", help="validate a ledger file in isolation"
    )
    validate.add_argument("--ledger", required=True)
    validate.add_argument(
        "--kind", choices=["baseline", "test-quarantine"], default="baseline"
    )
    validate.add_argument("--output", default=None)
    validate.set_defaults(handler=_handle_validate_ledger)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="l9-ci-baseline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_baseline_commands(subparsers)
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
