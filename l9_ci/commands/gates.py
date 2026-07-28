"""Gate evaluation commands."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from l9_ci.artifacts import (
    canonical_json_bytes,
    load_and_validate_bundle,
)
from l9_ci.cli import ExitCode
from l9_ci.gates import GateStatus, evaluate_gate


def register_gate_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    gate = subparsers.add_parser("gate")
    gate_subparsers = gate.add_subparsers(
        dest="gate_command",
        required=True,
    )
    evaluate = gate_subparsers.add_parser("evaluate")
    evaluate.add_argument("--bundle", required=True, type=Path)
    evaluate.add_argument("--output", type=Path)
    evaluate.add_argument(
        "--strict-unresolved",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    evaluate.set_defaults(handler=handle_evaluate)


def handle_evaluate(args: argparse.Namespace) -> int:
    try:
        bundle = load_and_validate_bundle(args.bundle)
        result = evaluate_gate(
            bundle,
            strict_unresolved=args.strict_unresolved,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.ARTIFACT_VALIDATION_FAILURE)
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)
    content = canonical_json_bytes(result.to_dict())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(content)
    else:
        sys.stdout.buffer.write(content)
    if result.status is GateStatus.PASS:
        return int(ExitCode.SUCCESS)
    if result.status is GateStatus.FAIL:
        return int(ExitCode.GATE_FAILURE)
    if result.status is GateStatus.INCOMPLETE:
        return int(ExitCode.UNRESOLVED_STRICT_CONTRACT)
    return int(ExitCode.ARTIFACT_VALIDATION_FAILURE)
