"""Generic artifact CLI commands."""

from __future__ import annotations
import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any
from l9_ci.cli import ExitCode
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from l9_ci.artifacts import (
    canonical_json_bytes,
    load_and_validate_bundle,
)
from l9_ci.integration import (
    project_agent_review_payload,
    validate_redaction,
)


def register_artifact_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    bundle = subparsers.add_parser("bundle")
    bundle_subparsers = bundle.add_subparsers(
        dest="bundle_command",
        required=True,
    )
    validate = bundle_subparsers.add_parser("validate")
    validate.add_argument("bundle_path", type=Path)
    validate.set_defaults(handler=handle_bundle_validate)
    project = bundle_subparsers.add_parser("project-agent-payload")
    project.add_argument("--input", required=True, type=Path)
    project.add_argument("--output", required=True, type=Path)
    project.add_argument("--strict", action="store_true")
    project.set_defaults(handler=handle_project_agent_payload)


def handle_bundle_validate(args: argparse.Namespace) -> int:
    try:
        bundle = load_and_validate_bundle(args.bundle_path)
        validate_redaction(bundle.to_dict()).require_valid()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return int(ExitCode.ARTIFACT_VALIDATION_FAILURE)
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)
    print(args.bundle_path)
    return int(ExitCode.SUCCESS)


def handle_project_agent_payload(args: argparse.Namespace) -> int:
    try:
        bundle = load_and_validate_bundle(args.input)
        payload = project_agent_review_payload(
            bundle,
            strict=args.strict,
        )
        payload_dict = payload.to_dict()
        validate_redaction(payload_dict).require_valid()
        _validate_agent_payload_schema(payload_dict)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_json_bytes(payload_dict))
    except ValueError as exc:
        message = str(exc)
        print(f"error: {message}", file=sys.stderr)
        if "unresolved" in message:
            return int(ExitCode.UNRESOLVED_STRICT_CONTRACT)
        return int(ExitCode.ARTIFACT_VALIDATION_FAILURE)
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)
    print(args.output)
    return int(ExitCode.SUCCESS)


def _validate_agent_payload_schema(payload: dict[str, Any]) -> None:
    schema_path = (
        files("l9_ci")
        .joinpath("schemas")
        .joinpath("v1")
        .joinpath("agent-review-payload.schema.json")
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_root = files("l9_ci").joinpath("schemas").joinpath("v1")
    resources = []
    for entry in schema_root.iterdir():
        if entry.name.endswith(".schema.json"):
            loaded = json.loads(entry.read_text(encoding="utf-8"))
            resources.append((loaded["$id"], Resource.from_contents(loaded)))
    validator = Draft202012Validator(
        schema,
        registry=Registry().with_resources(resources),
    )
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        messages = [
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        ]
        raise ValueError(
            "agent payload schema validation failed:\n"
            + "\n".join(f"- {message}" for message in messages)
        )
