"""Semgrep CLI command handlers."""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path

from l9_ci.cli import ExitCode, OutputFormat, render_success
from l9_ci.commands.errors import emit_error
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline
from l9_ci.providers.semgrep import SemgrepProvider
from l9_ci.rulesets.semgrep import (
    SUPPORTED_LANGUAGES,
    default_identity_map_path,
    default_profile_name,
    profile_names,
    resolve_profile,
    ruleset_dir,
)

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
        help=(
            "Execute Semgrep with the packaged global ruleset for one "
            "language and normalize the report in a single step"
        ),
    )
    run.add_argument("--language", choices=SUPPORTED_LANGUAGES, required=True)
    run.add_argument(
        "--raw-output",
        type=Path,
        help=(
            "Path where the raw Semgrep JSON report is written "
            "(default: <output stem>.raw.json)"
        ),
    )
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--timeout-seconds", type=int, default=300)
    run.add_argument(
        "--output-size-limit-bytes",
        type=int,
        default=50_000_000,
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
    run.add_argument(
        "--profile",
        choices=profile_names(),
        default=None,
        metavar="PROFILE",
        help=(
            "Versioned packaged ruleset profile selecting which config sources "
            "to compose (default: the registry's default_profile). A profile "
            "chooses among already-packaged configs only; --no-registry-config "
            "and --extra-config still apply on top of it"
        ),
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


def _build_run_config_arguments(args: argparse.Namespace) -> tuple[str, ...]:
    """Compose the --config arguments for one global-ruleset execution.

    The selected versioned profile (``--profile``, default the registry's
    ``default_profile``) decides which packaged config sources participate.
    Order: community registry ruleset (when the profile includes it and
    ``--no-registry-config`` is not set) -> packaged L9 ruleset for the
    requested language (when the profile includes it) -> caller-supplied
    ``--extra-config`` values, in the order given. The default profile
    reproduces the pre-profile composition (registry ruleset + L9 ruleset).
    """
    profile = resolve_profile(args.profile or default_profile_name())
    arguments: list[str] = []
    if profile.include_registry_ruleset and not args.no_registry_config:
        arguments.extend(("--config", _REGISTRY_CONFIG_BY_LANGUAGE[args.language]))
    if profile.include_l9_ruleset:
        arguments.extend(("--config", str(ruleset_dir(args.language))))
    for extra_config in args.extra_config:
        arguments.extend(("--config", extra_config))
    return tuple(arguments)


# The SDK provisions its own runtime -- a detached checkout plus a virtualenv of
# third-party dependencies -- INTO the repository under analysis. Core's
# `provision-sdk` defaults to `.l9/runtime/sdk` and refuses to place it outside
# `GITHUB_WORKSPACE`, so the scan root and the toolchain directory are the same
# tree by construction.
#
# Without this exclusion `semgrep scan .` analyzes the CI toolchain's own
# dependencies as if they were repository code. Observed in Quantum-L9 central
# CI: 51 of 52 findings came from `.l9/runtime/sdk/venv/.../site-packages/`
# (pip, urllib3, cryptography, peewee, semgrep), none of which carry an L9
# canonical rule id -- so `--strict` failed the organization's required check
# closed on every Python repository.
#
# `.l9/` is L9 infrastructure, never product code. Excluding the runtime
# subtree (not all of `.l9/`) keeps the exclusion narrow: repository-authored
# `.l9/` contracts stay in scope.
_RUNTIME_SCAFFOLDING_EXCLUSIONS = (".l9/runtime",)


def _build_run_exclusion_arguments() -> tuple[str, ...]:
    """Compose the --exclude arguments that keep SDK scaffolding out of scans."""
    arguments: list[str] = []
    for pattern in _RUNTIME_SCAFFOLDING_EXCLUSIONS:
        arguments.extend(("--exclude", pattern))
    return tuple(arguments)


def _request(
    args: argparse.Namespace,
    *,
    report_path: Path,
    execute: bool,
    provider_version: str | None,
    identity_map_path: Path | None,
    execution_arguments: tuple[str, ...] = (),
) -> SemgrepPipelineRequest:
    return SemgrepPipelineRequest(
        report_path=report_path,
        repository_root=args.root.resolve(),
        snapshot_id=args.snapshot_id,
        SDK_version=SDK_version(),
        output_path=args.output,
        provider_version=provider_version,
        identity_map_path=identity_map_path,
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
        execution_arguments=execution_arguments,
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
            identity_map_path=args.identity_map,
        ),
        default=ExitCode.PROVIDER_REPORT_FAILURE,
    )


def handle_run(args: argparse.Namespace) -> int:
    raw_output = args.raw_output or args.output.with_name(
        f"{args.output.stem}.raw.json"
    )
    return _execute_request(
        args,
        _request(
            args,
            report_path=raw_output,
            execute=True,
            provider_version=None,
            identity_map_path=args.identity_map or default_identity_map_path(),
            execution_arguments=_build_run_config_arguments(args)
            + _build_run_exclusion_arguments(),
        ),
        default=ExitCode.PROVIDER_EXECUTION_FAILURE,
    )
