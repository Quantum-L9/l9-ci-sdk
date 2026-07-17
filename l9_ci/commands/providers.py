"""Generic provider registry commands."""

from __future__ import annotations
import argparse
from pathlib import Path
from l9_ci.capabilities import detect_repository_capabilities
from l9_ci.cli import ExitCode, OutputFormat, render_success
from l9_ci.providers import ProviderRegistry, SemgrepProvider


def default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(SemgrepProvider())
    return registry


def register_provider_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    providers = subparsers.add_parser("providers")
    provider_subparsers = providers.add_subparsers(
        dest="providers_command",
        required=True,
    )
    list_parser = provider_subparsers.add_parser("list")
    list_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    list_parser.set_defaults(handler=handle_list)
    detect_parser = provider_subparsers.add_parser("detect")
    detect_parser.add_argument("--root", type=Path, default=Path("."))
    detect_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    detect_parser.set_defaults(handler=handle_detect)


def handle_list(args: argparse.Namespace) -> int:
    registry = default_registry()
    payload = {
        "providers": [provider.metadata.to_dict() for provider in registry.providers()]
    }
    print(
        render_success(
            payload,
            output_format=OutputFormat(args.format),
        )
    )
    return int(ExitCode.SUCCESS)


def handle_detect(args: argparse.Namespace) -> int:
    registry = default_registry()
    root = args.root.resolve()
    capabilities = detect_repository_capabilities(root)
    providers = []
    for provider in registry.providers():
        providers.append(
            {
                "provider_id": provider.metadata.provider_id,
                "installed": provider.detect(root),
                "version": provider.detect_version(),
                "candidate": (
                    provider.metadata.provider_id in capabilities.provider_candidates
                ),
            }
        )
    print(
        render_success(
            {
                "capabilities": capabilities.to_dict(),
                "providers": providers,
            },
            output_format=OutputFormat(args.format),
        )
    )
    return int(ExitCode.SUCCESS)
