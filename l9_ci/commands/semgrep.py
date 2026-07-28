"""Semgrep CLI command handlers."""

from __future__ import annotations
import argparse
import importlib.metadata
import sys
from pathlib import Path
from l9_ci.integration import OperationalLimits
from l9_ci.pipeline import (
    SemgrepPipelineRequest,
    run_semgrep_pipeline,
)
from l9_ci.providers import ProviderExecutionRequest
from l9_ci.providers.semgrep import SemgrepProvider
from l9_ci.rulesets.semgrep import (
    SUPPORTED_LANGUAGES,
    default_identity_map_path,
    ruleset_dir,
)

from l9_ci.cli import ExitCode, OutputFormat, render_success

# One global registry ruleset per language, inherited by every downstream
# consumer by default. A caller may opt out with --no-registry-config
# (e.g. a repository that only wants the packaged L9 rules) or extend it
# with --extra-config.
_REGISTRY_CONFIG_BY_LANGUAGE: dict[str, str] = {
    "python": "p/python",
    "typescript": "p/typescript",
}


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
    run = semgrep_subparsers.add_parser(
        "run",
        help=(
            "Execute Semgrep with the packaged global ruleset for one "
            "language and normalize the report in a single step"
        ),
    )
    run.add_argument("--language", choices=SUPPORTED_LANGUAGES, required=True)
    run.add_argument("--root", type=Path, default=Path("."))
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--raw-output", type=Path)
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
    run.add_argument(
        "--extra-config",
        action="append",
        default=[],
        metavar="CONFIG",
        help="Additional --config value (path or registry ref) to pass to semgrep",
    )
    run.add_argument(
        "--no-registry-config",
        action="store_true",
        help=(
            "Do not add the default community registry ruleset "
            "(p/python or p/typescript); scan with the packaged L9 "
            "ruleset (and any --extra-config) only"
        ),
    )
    run.add_argument("--timeout-seconds", type=int)
    run.add_argument("--output-size-limit-bytes", type=int)
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


def _run_pipeline_and_render(
    request: SemgrepPipelineRequest,
    *,
    output_format: OutputFormat,
) -> int:
    """Run the normalization pipeline and translate outcomes to exit codes.

    Shared by ``normalize`` (pre-existing raw report) and ``run`` (report
    just produced by ``provider.execute()``) so both commands report
    failures identically.
    """
    try:
        result = run_semgrep_pipeline(request)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.PROVIDER_REPORT_FAILURE)
    except ValueError as exc:
        message = str(exc)
        print(f"error: {message}", file=sys.stderr)
        if "strict" in message or "unresolved" in message:
            return int(ExitCode.UNRESOLVED_STRICT_CONTRACT)
        if "schema" in message or "validation" in message:
            return int(ExitCode.ARTIFACT_VALIDATION_FAILURE)
        return int(ExitCode.PROVIDER_REPORT_FAILURE)
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)
    print(
        render_success(
            {"output_path": str(result.output_path)},
            output_format=output_format,
        )
    )
    return int(ExitCode.SUCCESS)


def handle_normalize(args: argparse.Namespace) -> int:
    return _run_pipeline_and_render(
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
        ),
        output_format=OutputFormat(args.format),
    )


def _build_run_config_arguments(args: argparse.Namespace) -> tuple[str, ...]:
    """Compose the --config arguments for one global-ruleset execution.

    Order: community registry ruleset (unless disabled) -> packaged L9
    ruleset for the requested language -> caller-supplied --extra-config
    values, in the order given.
    """
    arguments: list[str] = []
    if not args.no_registry_config:
        arguments.extend(("--config", _REGISTRY_CONFIG_BY_LANGUAGE[args.language]))
    arguments.extend(("--config", str(ruleset_dir(args.language))))
    for extra_config in args.extra_config:
        arguments.extend(("--config", extra_config))
    return tuple(arguments)


def handle_run(args: argparse.Namespace) -> int:
    provider = SemgrepProvider()
    repository_root = args.root.resolve()
    if not provider.detect(repository_root):
        print("error: semgrep executable not found on PATH", file=sys.stderr)
        return int(ExitCode.PROVIDER_EXECUTION_FAILURE)
    configuration_errors = provider.validate_configuration(repository_root)
    if configuration_errors:
        for error in configuration_errors:
            print(f"error: {error}", file=sys.stderr)
        return int(ExitCode.PROVIDER_EXECUTION_FAILURE)

    provider_version = provider.detect_version()
    limits = OperationalLimits()
    raw_output = args.raw_output or args.output.with_name(
        f"{args.output.stem}.raw.json"
    )
    execution_result = provider.execute(
        ProviderExecutionRequest(
            repository_root=repository_root,
            output_path=raw_output,
            timeout_seconds=args.timeout_seconds or limits.timeout_seconds,
            output_size_limit_bytes=(
                args.output_size_limit_bytes or limits.process_output_limit_bytes
            ),
            arguments=_build_run_config_arguments(args),
        )
    )
    failure = provider.execution_failure(
        execution_result,
        required=args.required,
        provider_version=provider_version,
    )
    if failure is not None:
        stream = sys.stderr
        prefix = "error" if failure.fatal else "warning"
        print(f"{prefix}: {failure.message}", file=stream)
        if execution_result.stderr.strip():
            print(execution_result.stderr, file=stream)
        if failure.fatal:
            return int(ExitCode.PROVIDER_EXECUTION_FAILURE)
    if execution_result.report_path is None:
        print(
            "error: Semgrep did not produce a report to normalize",
            file=sys.stderr,
        )
        return int(ExitCode.PROVIDER_EXECUTION_FAILURE)

    return _run_pipeline_and_render(
        SemgrepPipelineRequest(
            report_path=execution_result.report_path,
            repository_root=repository_root,
            snapshot_id=args.snapshot_id,
            SDK_version=SDK_version(),
            output_path=args.output,
            provider_version=provider_version,
            identity_map_path=args.identity_map or default_identity_map_path(),
            policy_path=args.policy,
            strict=args.strict,
            required=args.required,
            generated_at=args.generated_at,
            revision=args.revision,
            dirty=args.dirty,
            derive_snapshot=args.derive_snapshot,
        ),
        output_format=OutputFormat(args.format),
    )
