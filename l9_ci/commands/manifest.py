"""``l9-ci manifest`` command group."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from l9_ci.cli.exit_codes import ExitCode
from l9_ci.repository.manifest import DEFAULT_MANIFEST_PATH, write_repository_manifest


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def _handle_generate(args: argparse.Namespace) -> int:
    root = Path(args.repository_root)
    output = Path(args.output)
    try:
        manifest, changed = write_repository_manifest(
            root,
            manifest_path=output,
            include_untracked=not args.tracked_only,
            excluded_paths=args.exclude_path or (),
            excluded_directories=args.exclude_dir or (),
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.INVALID_ARGUMENTS)

    _emit(
        {
            "changed": changed,
            "file_count": manifest.file_count,
            "manifest": output.as_posix(),
            "repository_root": root.as_posix(),
        }
    )
    return int(ExitCode.SUCCESS)


def _handle_check(args: argparse.Namespace) -> int:
    root = Path(args.repository_root)
    output = Path(args.output)
    try:
        _manifest, changed = write_repository_manifest(
            root,
            manifest_path=output,
            include_untracked=not args.tracked_only,
            excluded_paths=args.exclude_path or (),
            excluded_directories=args.exclude_dir or (),
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.INVALID_ARGUMENTS)

    _emit({"changed": changed, "manifest": output.as_posix()})
    return int(ExitCode.GATE_FAILURE if changed else ExitCode.SUCCESS)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output", default=DEFAULT_MANIFEST_PATH.as_posix())
    parser.add_argument("--tracked-only", action="store_true")
    parser.add_argument("--exclude-path", action="append")
    parser.add_argument("--exclude-dir", action="append")


def register_manifest_commands(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    parser = subparsers.add_parser(
        "manifest", help="generate and reconcile deterministic repository manifests"
    )
    manifest_subparsers = parser.add_subparsers(dest="manifest_command", required=True)

    generate = manifest_subparsers.add_parser(
        "generate", help="write the canonical manifest from repository truth"
    )
    _add_shared_arguments(generate)
    generate.set_defaults(handler=_handle_generate)

    check = manifest_subparsers.add_parser(
        "check", help="reconcile the manifest and exit non-zero when it changed"
    )
    _add_shared_arguments(check)
    check.set_defaults(handler=_handle_check)
