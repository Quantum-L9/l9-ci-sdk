"""Assurance-compatible factual observation commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from l9_ci.artifacts import canonical_json_bytes, load_and_validate_bundle
from l9_ci.cli import ExitCode, OutputFormat
from l9_ci.commands.errors import emit_error
from l9_ci.integration import build_observation, project_mandatory_findings_observation


def register_observation_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    observation = subparsers.add_parser("observation")
    commands = observation.add_subparsers(dest="observation_command", required=True)

    build = commands.add_parser("build")
    _add_common_execution_arguments(build)
    build.add_argument("--check-id", required=True)
    build.add_argument(
        "--status", required=True, choices=("passed", "failed", "error", "skipped")
    )
    # No --finding-count: `build` carries no way to supply finding records, and
    # build_observation requires finding_count == len(findings). The option could
    # therefore only ever be passed as 0, and any positive value failed the
    # command outright. Observations that carry findings are produced by
    # `project-mandatory-findings`, which derives the count from the bundle.
    build.add_argument("--error-count", type=int, default=0)
    build.add_argument("--warning-count", type=int, default=0)
    build.add_argument("--informational-count", type=int, default=0)
    build.set_defaults(handler=handle_build)

    mandatory = commands.add_parser("project-mandatory-findings")
    _add_common_execution_arguments(mandatory)
    mandatory.add_argument("--input", required=True, type=Path)
    mandatory.set_defaults(handler=handle_project_mandatory_findings)


def _add_common_execution_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=False)
    parser.add_argument("--configuration-digest", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--completed-at", required=True)
    parser.add_argument("--mode")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")


def _write_output(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload))


def handle_build(args: argparse.Namespace) -> int:
    try:
        if not args.revision:
            raise ValueError("--revision is required for observation build")
        payload = build_observation(
            producer_version=_package_version(),
            repository=args.repository,
            revision=args.revision,
            check_id=args.check_id,
            configuration_digest=args.configuration_digest,
            run_id=args.run_id,
            attempt=args.attempt,
            status=args.status,
            started_at=args.started_at,
            completed_at=args.completed_at,
            error_count=args.error_count,
            warning_count=args.warning_count,
            informational_count=args.informational_count,
            mode=args.mode,
        )
        _write_output(args.output, payload)
    except Exception as exc:
        return emit_error(exc, output_format=OutputFormat(args.format))
    print(args.output)
    return int(ExitCode.SUCCESS)


def handle_project_mandatory_findings(args: argparse.Namespace) -> int:
    try:
        bundle = load_and_validate_bundle(args.input)
        if args.revision and bundle.snapshot.revision != args.revision:
            raise ValueError(
                "--revision does not match FindingBundle snapshot revision"
            )
        source_path = None if args.input.is_absolute() else args.input.as_posix()
        payload = project_mandatory_findings_observation(
            bundle,
            repository=args.repository,
            configuration_digest=args.configuration_digest,
            run_id=args.run_id,
            attempt=args.attempt,
            started_at=args.started_at,
            completed_at=args.completed_at,
            mode=args.mode,
            source_path=source_path,
        )
        _write_output(args.output, payload)
    except Exception as exc:
        return emit_error(exc, output_format=OutputFormat(args.format))
    print(args.output)
    return int(ExitCode.SUCCESS)


def _package_version() -> str:
    # Importing package metadata would make editable/source-tree execution
    # dependent on installation state. The canonical SDK version lives in the
    # package itself and FindingBundle projection uses bundle.SDK_version.
    from l9_ci import __version__

    return __version__
