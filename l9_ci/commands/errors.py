"""Centralized CLI error rendering (DWA-005).

Maps a handler exception to a structured ``Diagnostic`` and a stable
``ExitCode``, and renders it honoring the requested ``OutputFormat``. Before
this, every command printed ad-hoc plain-text ``error: ...`` strings even under
``--format json``, and duplicated the exception→exit-code logic. Now failure
output is a machine-readable envelope for every command and the mapping lives in
one place.

The exit-code mapping preserves the exact prior behavior (characterization
tests in tests/commands lock it); ``value_error_default`` supplies the
per-command default for an otherwise-unclassified ``ValueError`` (semgrep
normalize defaulted to PROVIDER_REPORT_FAILURE, other commands to
ARTIFACT_VALIDATION_FAILURE).
"""

from __future__ import annotations
import sys
from l9_ci.cli import Diagnostic, ExitCode, OutputFormat
from l9_ci.pipeline import UnsupportedProviderVersionError


def classify_exception(
    exc: BaseException,
    *,
    default: ExitCode,
) -> tuple[str, ExitCode]:
    """Return (diagnostic_code, exit_code) for a handler exception.

    ``default`` is the command's exit code for an input/validation failure that
    is not one of the specifically-typed cases (version, strict/unresolved,
    schema/validation). Missing-input (FileNotFoundError) uses it too.
    """
    # UnsupportedProviderVersionError subclasses ValueError — check it first.
    if isinstance(exc, UnsupportedProviderVersionError):
        return "incompatible_version", ExitCode.INCOMPATIBLE_VERSION
    if isinstance(exc, ValueError):
        message = str(exc)
        if "strict" in message or "unresolved" in message:
            return "unresolved_strict_contract", ExitCode.UNRESOLVED_STRICT_CONTRACT
        if "schema" in message or "validation" in message:
            return "artifact_validation", ExitCode.ARTIFACT_VALIDATION_FAILURE
        return default.name.lower(), default
    if isinstance(exc, FileNotFoundError):
        return default.name.lower(), default
    return "internal_error", ExitCode.INTERNAL_ERROR


def emit_error(
    exc: BaseException,
    *,
    output_format: OutputFormat,
    default: ExitCode = ExitCode.ARTIFACT_VALIDATION_FAILURE,
) -> int:
    """Render a structured diagnostic for ``exc`` to stderr and return its exit code."""
    code, exit_code = classify_exception(exc, default=default)
    diagnostic = Diagnostic(code=code, message=str(exc), details={})
    print(diagnostic.render(output_format), file=sys.stderr)
    return int(exit_code)
