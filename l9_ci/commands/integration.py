"""Integration compatibility CLI commands."""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from l9_ci.cli import ExitCode
from l9_ci.integration import negotiate_versions


def register_integration_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    compatibility = subparsers.add_parser("compatibility")
    compatibility_subparsers = compatibility.add_subparsers(
        dest="compatibility_command",
        required=True,
    )
    check = compatibility_subparsers.add_parser("check")
    check.add_argument("--bundle", required=True, type=Path)
    check.add_argument("--minimum-SDK-version")
    check.set_defaults(handler=handle_compatibility_check)


def handle_compatibility_check(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(args.bundle.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("bundle root must be an object")
        result = negotiate_versions(
            payload,
            minimum_SDK_version=args.minimum_SDK_version,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.ARTIFACT_VALIDATION_FAILURE)
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)
    if not result.compatible:
        for error in result.errors:
            print(f"error: {error}", file=sys.stderr)
        return int(ExitCode.INCOMPATIBLE_VERSION)
    print(f"SDK_version={result.SDK_version}")
    print(f"schema_version={result.artifact_schema_version}")
    print("compatible=true")
    return int(ExitCode.SUCCESS)
