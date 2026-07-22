"""Semgrep CLI command handlers."""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path

from l9_ci.cli import ExitCode, OutputFormat, render_success
from l9_ci.commands.errors import emit_error
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline
from l9_ci.providers.semgrep import SemgrepProvider


def SDK_version() -> str:
    try:
        return importlib.metadata.version("l9-ci-sdk")
    except importlib.metadata.PackageNotFoundError:
        from l9_ci import __version__

        return __version__


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--snapshot-id")
    parser.add_argument("--derive-snapshot", action="store_true")
    parser.add_argument("--identity-map", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--required", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--revision")
    parser.add_argument(
        "--dirty",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")


def register_semgrep_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("semgrep", help="Semgrep provider operations")
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
        help="Normalize an existing Semgrep JSON report",
    )
    normalize.add_argument("--input", required=True, type=Path)
    normalize.add_argument("--output", required=True, type=Path)
    normalize.add_argument(
        "--provider-version",
        required=True,
        help="Version that produced the imported report",
    )
    _add_common_arguments(normalize)
    normalize.set_defaults(handler=handle_normalize)

    run = semgrep_subparsers.add_parser(
        "run",
        help="Execute Semgrep through bounded SDK controls and normalize",
    )
    run.add_argument(
        "--report",
        required=True,
        type=Path,
        help="Path where the raw Semgrep JSON report is written",
    )
    run.add_argument("--output", required=True, type=Path)
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
        help="One provider argv item; repeat for multiple items",
    )
    _add_common_arguments(run)
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


def _request(
    args: argparse.Namespace,
    *,
    report_path: Path,
    execute: bool,
    provider_version: str | None,
) -> SemgrepPipelineRequest:
    return SemgrepPipelineRequest(
        report_path=report_path,
        repository_root=args.root.resolve(),
        snapshot_id=args.snapshot_id,
        SDK_version=SDK_version(),
        output_path=args.output,
        provider_version=provider_version,
        identity_map_path=args.identity_map,
        policy_path=args.policy,
        strict=args.strict,
        required=args.required,
        generated_at=args.generated_at,
        revision=args.revision,
        dirty=args.dirty,
        derive_snapshot=args.derive_snapshot,
        execute=execute,
        timeout_seconds=getattr(args, "timeout_seconds", 300),
        output_size_limit_bytes=getattr(
            args,
            "output_size_limit_bytes",
            50_000_000,
        ),
        execution_arguments=tuple(getattr(args, "execution_args", [])),
    )


def _execute_request(
    args: argparse.Namespace,
    request: SemgrepPipelineRequest,
    *,
    default: ExitCode,
) -> int:
    try:
        result = run_semgrep_pipeline(request)
    except Exception as exc:
        return emit_error(
            exc,
            output_format=OutputFormat(args.format),
            default=default,
        )
    print(
        render_success(
            {
                "output_path": str(result.output_path),
                "report_path": str(request.report_path),
            },
            output_format=OutputFormat(args.format),
        )
    )
    return int(ExitCode.SUCCESS)


def handle_normalize(args: argparse.Namespace) -> int:
    return _execute_request(
        args,
        _request(
            args,
            report_path=args.input,
            execute=False,
            provider_version=args.provider_version,
        ),
        default=ExitCode.PROVIDER_REPORT_FAILURE,
    )


def handle_run(args: argparse.Namespace) -> int:
    return _execute_request(
        args,
        _request(
            args,
            report_path=args.report,
            execute=True,
            provider_version=None,
        ),
        default=ExitCode.PROVIDER_EXECUTION_FAILURE,
    )
