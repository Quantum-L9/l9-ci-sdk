"""Assurance-compatible factual observation commands."""

from __future__ import annotations

import argparse
import hashlib as _hashlib
from pathlib import Path
from typing import Any

from l9_ci.artifacts import canonical_json_bytes, load_and_validate_bundle
from l9_ci.cli import ExitCode, OutputFormat
from l9_ci.commands.errors import emit_error
from l9_ci.integration import (
    build_observation,
    project_mandatory_findings_observation,
    validate_redaction,
)


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

    # No --status here either, and for the same reason as `build`'s missing
    # --finding-count: the projector runs the validation and derives the
    # verdict. An option to assert it would make the control meaningless.
    sdk_validation = commands.add_parser("project-sdk-validation")
    _add_common_execution_arguments(sdk_validation)
    sdk_validation.add_argument("--input", required=True, type=Path)
    sdk_validation.set_defaults(handler=handle_project_sdk_validation)


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


def handle_project_sdk_validation(args: argparse.Namespace) -> int:
    try:
        if not args.revision:
            raise ValueError(
                "--revision is required for observation project-sdk-validation"
            )
        source_path = None if args.input.is_absolute() else args.input.as_posix()
        payload = project_sdk_validation_observation(
            args.input,
            repository=args.repository,
            revision=args.revision,
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
    # A `failed` observation is a successful projection: the command reports
    # whether it could produce evidence, not whether the evidence is good news.
    # Conflating the two would make a workflow step that emits a real failure
    # look like a broken step, and the natural fix for a broken step is to stop
    # emitting -- which is how a control loses its evidence.
    return int(ExitCode.SUCCESS)


def _package_version() -> str:
    # Importing package metadata would make editable/source-tree execution
    # dependent on installation state. The canonical SDK version lives in the
    # package itself and FindingBundle projection uses bundle.SDK_version.
    from l9_ci import __version__

    return __version__


def project_sdk_validation_observation(
    bundle_path: Path,
    *,
    repository: str,
    revision: str,
    configuration_digest: str,
    run_id: str,
    attempt: int,
    started_at: str,
    completed_at: str,
    mode: str | None = None,
    source_path: str | None = None,
) -> dict[str, Any]:
    """Project the SDK's own validation of a bundle into `l9.sdk-validation`.

    This runs the validation. It does not take a status: there is no parameter
    by which a caller can assert that validation passed, because the point of
    the control is that something actually checked. `build_observation` is the
    generic path where the caller supplies the verdict; this is not that.

    The verdict is `passed` when both halves of `l9-ci bundle validate` succeed
    -- `load_and_validate_bundle` (raw summary, producer compatibility, schema,
    then semantics) and `validate_redaction` over the loaded bundle -- and
    `failed` when either rejects. `failed` is a real observation and is meant to
    be emitted: Assurance distinguishes a control that failed from one with no
    evidence, and suppressing the failure would turn a known-bad revision into
    an indeterminate one.

    `revision` binds the observation to a subject and is cross-checked against
    the bundle whenever the bundle loads. A mismatch raises rather than
    producing a `failed` observation: the two describe different subjects, so
    there is no honest verdict to record about either. The caller must still
    supply it, because a bundle that fails to parse carries no revision and the
    control requires an exact subject binding.

    Validation errors are deliberately not carried in the payload. The
    observation schema's artifact records set `unevaluatedProperties: false`
    and the control evaluates `all-requirements-satisfied` from execution
    status alone, so there is nowhere to put them that the consumer would read,
    and inventing one would be a contract change. The reasons stay on the CLI's
    stderr, where the operator reads them.
    """
    if not revision.strip():
        raise ValueError("revision is required to bind an sdk-validation observation")

    # Deliberately untyped as the concrete bundle class: `commands` may not
    # depend on `contracts` (.l9/architecture.yaml), and an annotation is
    # not a reason to add an architectural edge. `load_and_validate_bundle`
    # returns it already validated; nothing here inspects it beyond the
    # revision and the digest.
    bundle: Any = None
    passed = True
    try:
        bundle = load_and_validate_bundle(bundle_path)
        validate_redaction(bundle.to_dict()).require_valid()
    except Exception:  # noqa: BLE001 - any rejection is a failed validation
        passed = False

    if bundle is not None and bundle.snapshot.revision != revision:
        raise ValueError(
            "revision does not match the FindingBundle snapshot revision; "
            "the observation would describe a different subject than the "
            "artifact it validated"
        )

    artifacts: list[dict[str, Any]] = []
    digest = _validated_input_digest(bundle, bundle_path)
    if digest is not None:
        artifact: dict[str, Any] = {
            "name": "finding-bundle",
            "digest": {"algorithm": "sha256", "value": digest},
            "mediaType": "application/vnd.l9.finding-bundle+json",
        }
        if bundle is not None:
            # Only a loaded bundle can be asked what SDK wrote it. An
            # unreadable one still gets a content address, from its raw bytes.
            artifact["sdkVersion"] = bundle.SDK_version
        if source_path:
            source = Path(source_path)
            if source.is_absolute() or ".." in source.parts:
                raise ValueError("source_path must be repository-relative")
            artifact["path"] = source.as_posix()
        artifacts.append(artifact)

    return build_observation(
        producer_version=_package_version(),
        repository=repository,
        revision=revision,
        check_id="l9.sdk-validation",
        configuration_digest=configuration_digest,
        run_id=run_id,
        attempt=attempt,
        status="passed" if passed else "failed",
        started_at=started_at,
        completed_at=completed_at,
        artifacts=artifacts,
        mode=mode,
    )


def _validated_input_digest(
    bundle: Any,
    bundle_path: Path,
) -> str | None:
    """Content address for whatever was validated, loadable or not.

    A loaded bundle uses its canonical digest, which is order-independent and
    excludes `generated_at`, so re-validating an equivalent bundle yields the
    same artifact identity. A bundle that failed to load has no canonical form,
    so its raw bytes are hashed instead -- the observation still says exactly
    which file was rejected. A file that cannot be read at all yields no
    artifact rather than a fabricated one.
    """
    if bundle is not None:
        return bundle.canonical_digest()
    try:
        return _hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    except OSError:
        return None
