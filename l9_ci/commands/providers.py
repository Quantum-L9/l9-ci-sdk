"""Generic provider registry commands."""

from __future__ import annotations
import argparse
from pathlib import Path
from l9_ci.artifacts import canonical_json_bytes
from l9_ci.capabilities import (
    AnalysisTarget,
    build_capability_inventory,
    detect_repository_capabilities,
    validate_capability_inventory,
)
from l9_ci.cli import ExitCode, OutputFormat, render_success
from l9_ci.commands.errors import emit_error
from l9_ci.commands.semgrep import SDK_version
from l9_ci.providers import ProviderRegistry, SemgrepProvider
from l9_ci.rulesets.semgrep import SUPPORTED_LANGUAGES, ruleset_dir


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
    inventory_parser = provider_subparsers.add_parser("inventory")
    inventory_parser.add_argument("--root", type=Path, default=Path("."))
    inventory_parser.add_argument(
        "--probe-executables",
        action="store_true",
        help=(
            "also record whether each provider executable is available on "
            "this machine; without it the record is a pure function of the "
            "snapshot and reports executables as not_probed"
        ),
    )
    inventory_parser.add_argument("--output", type=Path, default=None)
    inventory_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    inventory_parser.set_defaults(handler=handle_inventory)


def handle_list(args: argparse.Namespace) -> int:
    try:
        registry = default_registry()
        payload = {
            "providers": [
                provider.metadata.to_dict() for provider in registry.providers()
            ]
        }
    except Exception as exc:
        return emit_error(exc, output_format=OutputFormat(args.format))
    print(render_success(payload, output_format=OutputFormat(args.format)))
    return int(ExitCode.SUCCESS)


def handle_detect(args: argparse.Namespace) -> int:
    try:
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
                        provider.metadata.provider_id
                        in capabilities.provider_candidates
                    ),
                }
            )
        payload = {
            "capabilities": capabilities.to_dict(),
            "providers": providers,
        }
    except Exception as exc:
        return emit_error(exc, output_format=OutputFormat(args.format))
    print(render_success(payload, output_format=OutputFormat(args.format)))
    return int(ExitCode.SUCCESS)


# What each packaged Semgrep language run actually analyzes: the inventory
# languages it serves and the file suffixes Semgrep scans for them. Observed
# with Semgrep 1.171.0 against this repository's rulepacks
# (tests/rulesets/test_semgrep_target_suffixes.py re-checks it wherever a
# semgrep executable is present).
#
# The typescript run serves JavaScript too: every rule in
# l9_ci/rulesets/semgrep/typescript declares `languages: [typescript,
# javascript]`, and tests/fixtures/semgrep/rules/typescript/ proves each one
# on JavaScript in both directions. Semgrep does not scan .mts or .cts, so
# those TypeScript files are reported as not analyzed rather than covered.
_TARGET_FILES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "python": (("python",), (".py",)),
    "typescript": (
        ("typescript", "javascript"),
        (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"),
    ),
}


def default_analysis_targets(
    root: Path,
    *,
    probe_executables: bool = False,
) -> tuple[AnalysisTarget, ...]:
    """Declare every analysis target this SDK build can run.

    One target per packaged Semgrep language rulepack. A rulepack that does
    not resolve is declared with ``rulepack_resolved=False`` so the inventory
    reports it as failed instead of dropping the target.
    """
    executable = "not_probed"
    version: str | None = None
    if probe_executables:
        provider = SemgrepProvider()
        if provider.detect(root):
            executable = "available"
            version = provider.detect_version()
        else:
            executable = "missing"
    targets = []
    for language in sorted(SUPPORTED_LANGUAGES):
        languages, suffixes = _TARGET_FILES[language]
        try:
            resolved = any(ruleset_dir(language).glob("*.yml"))
        except (FileNotFoundError, ValueError):
            resolved = False
        targets.append(
            AnalysisTarget(
                provider_id="semgrep",
                scope="language",
                name=language,
                languages=languages,
                rulepack=f"l9_ci/rulesets/semgrep/{language}",
                rulepack_resolved=resolved,
                executable=executable,
                executable_version=version,
                suffixes=suffixes,
            )
        )
    return tuple(targets)


def handle_inventory(args: argparse.Namespace) -> int:
    try:
        root = args.root.resolve()
        inventory = build_capability_inventory(
            root,
            targets=default_analysis_targets(
                root,
                probe_executables=args.probe_executables,
            ),
            SDK_version=SDK_version(),
        )
        payload = inventory.to_dict()
        validate_capability_inventory(payload)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(canonical_json_bytes(payload))
    except Exception as exc:
        return emit_error(exc, output_format=OutputFormat(args.format))
    print(render_success(payload, output_format=OutputFormat(args.format)))
    return int(ExitCode.SUCCESS)
