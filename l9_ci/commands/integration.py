"""Integration compatibility CLI commands."""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from l9_ci.cli import Diagnostic, ExitCode, OutputFormat, render_success
from l9_ci.commands.errors import emit_error
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
    check.add_argument("--format", choices=("text", "json"), default="text")
    check.set_defaults(handler=handle_compatibility_check)


def handle_compatibility_check(args: argparse.Namespace) -> int:
    output_format = OutputFormat(args.format)
    try:
        payload = json.loads(args.bundle.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("bundle root must be an object")
        result = negotiate_versions(
            payload,
            minimum_SDK_version=args.minimum_SDK_version,
        )
    except Exception as exc:
        return emit_error(exc, output_format=output_format)
    if not result.compatible:
        diagnostic = Diagnostic(
            code="incompatible_version",
            message="; ".join(result.errors),
            details={"errors": list(result.errors)},
        )
        print(diagnostic.render(output_format), file=sys.stderr)
        return int(ExitCode.INCOMPATIBLE_VERSION)
    print(
        render_success(
            {
                "SDK_version": result.SDK_version,
                "schema_version": result.artifact_schema_version,
                "compatible": True,
            },
            output_format=output_format,
        )
    )
    return int(ExitCode.SUCCESS)
