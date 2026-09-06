"""Assurance-compatible factual observation commands."""

from __future__ import annotations

import argparse
import hashlib as _hashlib
from pathlib import Path
from typing import Any, Sequence

from l9_ci.artifacts import canonical_json_bytes, load_and_validate_bundle
from l9_ci.cli import ExitCode, OutputFormat
from l9_ci.commands.errors import emit_error
from l9_ci.integration import (
    build_observation,
    project_mandatory_findings_observation,
    validate_redaction,
)
from l9_ci.repository.git import inspect_git_repository, is_git_repository
from l9_ci.repository.manifest import (
    DEFAULT_MANIFEST_PATH,
    build_repository_manifest,
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

    # No --status, same reason. Note there is no --input either: the input is
    # the repository, and the projector reads it rather than being handed a
    # summary of it.
    metadata = commands.add_parser("project-repository-metadata")
    _add_common_execution_arguments(metadata)
    metadata.add_argument("--repository-root", type=Path, default=Path("."))
    metadata.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    metadata.add_argument("--tracked-only", action="store_true")
    metadata.add_argument("--exclude-path", action="append")
    metadata.add_argument("--exclude-dir", action="append")
    metadata.set_defaults(handler=handle_project_repository_metadata)


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


def handle_project_repository_metadata(args: argparse.Namespace) -> int:
    try:
        if not args.revision:
            raise ValueError(
                "--revision is required for observation project-repository-metadata"
            )
        payload = project_repository_metadata_observation(
            repository_root=args.repository_root,
            repository=args.repository,
            revision=args.revision,
            configuration_digest=args.configuration_digest,
            run_id=args.run_id,
            attempt=args.attempt,
            started_at=args.started_at,
            completed_at=args.completed_at,
            manifest_path=args.manifest,
            include_untracked=not args.tracked_only,
            excluded_paths=args.exclude_path or (),
            excluded_directories=args.exclude_dir or (),
            mode=args.mode,
        )
        _write_output(args.output, payload)
    except Exception as exc:
        return emit_error(exc, output_format=OutputFormat(args.format))
    print(args.output)
    # As with sdk-validation: a `failed` verdict is a successful projection.
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
    except (ValueError, OSError):
        # Only the two families that mean "this bundle is not valid":
        # ValueError from every validator on the path -- raw summary,
        # compatibility, schema, semantics, redaction -- with
        # json.JSONDecodeError arriving as a subclass of it, and OSError for a
        # file that cannot be read.
        #
        # This was `except Exception`, which code scanning flagged and was
        # right to. Under it a defect in this SDK -- an AttributeError, a
        # TypeError from a refactor -- would have been reported as `failed`:
        # an observation asserting that someone's revision fails validation
        # when in truth the validator crashed. Emitting evidence that blames
        # the wrong party is worse than crashing, and this projector exists to
        # stop unfounded verdicts. Anything outside these two families is a
        # bug here and must surface as one.
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


def project_repository_metadata_observation(
    *,
    repository_root: Path,
    repository: str,
    revision: str,
    configuration_digest: str,
    run_id: str,
    attempt: int,
    started_at: str,
    completed_at: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    include_untracked: bool = True,
    excluded_paths: Sequence[str] = (),
    excluded_directories: Sequence[str] = (),
    mode: str | None = None,
) -> dict[str, Any]:
    """Project the tracked manifest's reconciliation into `l9.repository-metadata`.

    Like the sdk-validation projector, this runs the check and takes no status
    argument. The verdict is `passed` when the manifest committed to the
    repository matches what `build_repository_manifest` derives from repository
    truth right now, and `failed` when it has drifted -- the same comparison
    `l9-ci manifest check` makes, and the same one that turns its exit code
    into GATE_FAILURE.

    It deliberately does not call `write_repository_manifest`, which is what
    `manifest check` uses: that function *writes* the reconciled manifest as a
    side effect. A producer of evidence must not mutate the repository it is
    describing, so the comparison is done here against the file on disk and
    nothing is written.

    The subject binding is observed rather than accepted. `inspect_git_repository`
    reads the real HEAD, and `revision` is cross-checked against it; a mismatch
    raises, because an observation naming one revision while measuring another
    describes neither. A root that is not a git repository raises for the same
    reason -- there is no revision to bind to, and binding to the caller's word
    is the caller-asserted evidence this projector exists to avoid.

    A dirty tree also raises. The control declares
    `subjectBinding.exactRevision`, and a manifest compared against modified
    files is not a statement about the committed revision. In practice this
    means emitting the observation *before* any step that writes generated
    files -- including `manifest check` itself, which would dirty the very file
    under comparison.
    """
    root = Path(repository_root).resolve()
    if not revision.strip():
        raise ValueError(
            "revision is required to bind a repository-metadata observation"
        )
    if not is_git_repository(root):
        raise ValueError(
            f"{root} is not a git repository, so no revision can be observed; "
            "an observation bound to an unverified revision would be an "
            "assertion rather than evidence"
        )

    state = inspect_git_repository(root)
    if state.revision != revision:
        raise ValueError(
            "revision does not match the repository HEAD "
            f"({state.revision}); the observation would name one revision "
            "while describing another"
        )
    if state.dirty:
        raise ValueError(
            "the working tree is dirty, so a manifest comparison does not "
            "describe the committed revision; emit this observation before "
            "any step that writes generated files"
        )

    output = manifest_path if manifest_path.is_absolute() else root / manifest_path
    try:
        manifest = build_repository_manifest(
            root,
            manifest_path=output,
            include_untracked=include_untracked,
            excluded_paths=excluded_paths,
            excluded_directories=excluded_directories,
        )
        rendered = manifest.render_markdown()
        tracked = output.read_text(encoding="utf-8") if output.exists() else None
        reconciled = tracked == rendered
    except (ValueError, OSError):
        # Same narrow families as the sdk-validation projector, and for the
        # same reason: a defect in this SDK must surface as one rather than
        # being reported as a repository whose metadata is invalid.
        reconciled = False
        rendered = None

    artifacts: list[dict[str, Any]] = [
        {
            "name": "repository-manifest",
            "digest": {
                "algorithm": "sha256",
                # The digest addresses what repository truth says the manifest
                # should be, not what is committed. On a pass they are equal;
                # on a failure this is the value that would make it pass, which
                # is the useful half for whoever reads the evidence.
                "value": (
                    _hashlib.sha256(rendered.encode("utf-8")).hexdigest()
                    if rendered is not None
                    else _hashlib.sha256(b"").hexdigest()
                ),
            },
            "mediaType": "text/markdown",
            "path": _repository_relative(output, root),
        }
    ]

    return build_observation(
        producer_version=_package_version(),
        repository=repository,
        revision=revision,
        check_id="l9.repository-metadata",
        configuration_digest=configuration_digest,
        run_id=run_id,
        attempt=attempt,
        status="passed" if reconciled else "failed",
        started_at=started_at,
        completed_at=completed_at,
        artifacts=artifacts,
        mode=mode,
    )


def _repository_relative(path: Path, root: Path) -> str:
    """The manifest's path as the repository sees it, never as this host does.

    An absolute path would put the runner's directory layout into a canonical
    artifact, which the SDK's redaction rules forbid outright.
    """
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name
