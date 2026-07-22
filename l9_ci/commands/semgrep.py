"""Semgrep CLI command handlers."""

from __future__ import annotations
import argparse
import importlib.metadata
from pathlib import Path
from l9_ci.pipeline import (
    SemgrepPipelineRequest,
    run_semgrep_pipeline,
)
from l9_ci.providers.semgrep import SemgrepProvider

from l9_ci.cli import ExitCode, OutputFormat, render_success
from l9_ci.commands.errors import emit_error


def SDK_version() -> str:
    try:
        return importlib.metadata.version("l9-ci-sdk")
    except importlib.metadata.PackageNotFoundError:
        # Running from source (no build metadata): fall back to the canonical
        # in-source version. Must be a valid major.minor.patch so downstream
        # `compatibility check` version negotiation succeeds.
        from l9_ci import __version__

        return __version__


def register_semgrep_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "semgrep",
        help="Semgrep provider operations",
    )
    semgrep_subparsers = parser.add_subparsers(
        dest="semgrep_command",
        required=True,
    )
    detect = semgrep_subparsers.add_parser(
        "detect",
        help="Detect Semgrep availability and version",
    )
    detect.add_argument("--format", choices=("text", "json"), default="text")
    detect.set_defaults(handler=handle_detect)
    normalize = semgrep_subparsers.add_parser(
        "normalize",
        help="Normalize a Semgrep JSON report",
    )
    normalize.add_argument("--input", required=True, type=Path)
    normalize.add_argument("--output", required=True, type=Path)
    normalize.add_argument("--root", type=Path, default=Path("."))
    normalize.add_argument("--snapshot-id")
    normalize.add_argument("--derive-snapshot", action="store_true")
    normalize.add_argument("--format", choices=("text", "json"), default="text")
    normalize.add_argument("--provider-version")
    normalize.add_argument("--identity-map", type=Path)
    normalize.add_argument("--policy", type=Path)
    normalize.add_argument("--strict", action="store_true")
    normalize.add_argument("--required", action="store_true")
    normalize.add_argument("--generated-at")
    normalize.add_argument("--revision")
    normalize.add_argument(
        "--dirty",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    normalize.set_defaults(handler=handle_normalize)
    # Production caller for SDK-owned bounded execution (DWA-002): runs the
    # provider through the generic runner (validate -> execute -> classify ->
    # import -> normalize) instead of importing a pre-produced report.
    run = semgrep_subparsers.add_parser(
        "run",
        help="Execute Semgrep (bounded) and normalize its report",
    )
    run.add_argument(
        "--report",
        required=True,
        type=Path,
        help="Path where the raw Semgrep JSON report is written",
    )
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--root", type=Path, default=Path("."))
    run.add_argument("--snapshot-id")
    run.add_argument("--derive-snapshot", action="store_true")
    run.add_argument("--format", choices=("text", "json"), default="text")
    run.add_argument("--identity-map", type=Path)
    run.add_argument("--policy", type=Path)
    run.add_argument("--strict", action="store_true")
    run.add_argument("--required", action="store_true")
    run.add_argument("--generated-at")
    run.add_argument("--revision")
    run.add_argument(
        "--dirty",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    run.add_argument("--timeout-seconds", type=int, default=300)
    run.add_argument(
        "--output-size-limit-bytes",
        type=int,
        default=50_000_000,
    )
    run.add_argument(
        "--execution-arg",
        action="append",
        default=[],
        dest="execution_args",
        help="Extra argument passed to the provider (repeatable)",
    )
    run.set_defaults(handler=handle_run)


def handle_detect(args: argparse.Namespace) -> int:
    provider = SemgrepProvider()
    available = provider.detect(Path("."))
    version = provider.detect_version()
    print(
        render_success(
            {
                "provider_id": provider.metadata.provider_id,
                "available": available,
                "version": version or "unknown",
            },
            output_format=OutputFormat(args.format),
        )
    )
    return int(ExitCode.SUCCESS if available else ExitCode.PROVIDER_EXECUTION_FAILURE)


def handle_run(args: argparse.Namespace) -> int:
    try:
        result = run_semgrep_pipeline(
            SemgrepPipelineRequest(
                report_path=args.report,
                repository_root=args.root.resolve(),
                snapshot_id=args.snapshot_id,
                SDK_version=SDK_version(),
                output_path=args.output,
                identity_map_path=args.identity_map,
                policy_path=args.policy,
                strict=args.strict,
                required=args.required,
                generated_at=args.generated_at,
                revision=args.revision,
                dirty=args.dirty,
                derive_snapshot=args.derive_snapshot,
                execute=True,
                timeout_seconds=args.timeout_seconds,
                output_size_limit_bytes=args.output_size_limit_bytes,
                execution_arguments=tuple(args.execution_args),
            )
        )
    except Exception as exc:
        return emit_error(
            exc,
            output_format=OutputFormat(args.format),
            default=ExitCode.PROVIDER_EXECUTION_FAILURE,
        )
    print(
        render_success(
            {
                "output_path": str(result.output_path),
                "report_path": str(args.report),
            },
            output_format=OutputFormat(args.format),
        )
    )
    return int(ExitCode.SUCCESS)


def handle_normalize(args: argparse.Namespace) -> int:
    try:
        result = run_semgrep_pipeline(
            SemgrepPipelineRequest(
                report_path=args.input,
                repository_root=args.root.resolve(),
                snapshot_id=args.snapshot_id,
                SDK_version=SDK_version(),
                output_path=args.output,
                provider_version=args.provider_version,
                identity_map_path=args.identity_map,
                policy_path=args.policy,
                strict=args.strict,
                required=args.required,
                generated_at=args.generated_at,
                revision=args.revision,
                dirty=args.dirty,
                derive_snapshot=args.derive_snapshot,
            )
        )
    except Exception as exc:
        return emit_error(
            exc,
            output_format=OutputFormat(args.format),
            default=ExitCode.PROVIDER_REPORT_FAILURE,
        )
    print(
        render_success(
            {"output_path": str(result.output_path)},
            output_format=OutputFormat(args.format),
        )
    )
    return int(ExitCode.SUCCESS)
