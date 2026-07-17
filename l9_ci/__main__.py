"""l9-ci command-line entry point."""

import argparse
from l9_ci.commands import (
    register_artifact_commands,
    register_gate_commands,
    register_integration_commands,
    register_provider_commands,
    register_semgrep_commands,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="l9-ci")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_artifact_commands(subparsers)
    register_gate_commands(subparsers)
    register_integration_commands(subparsers)
    register_provider_commands(subparsers)
    register_semgrep_commands(subparsers)
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
