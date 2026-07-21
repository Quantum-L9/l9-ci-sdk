"""Unit tests for the centralized CLI error boundary (DWA-005).

Locks the exception -> (diagnostic code, exit code) mapping and the
Diagnostic-rendering behavior directly, so the exit-code contract is explicit
and cannot drift silently.
"""

from __future__ import annotations
import json
import pytest
from l9_ci.cli import Diagnostic, ExitCode, OutputFormat
from l9_ci.commands.errors import classify_exception, emit_error
from l9_ci.pipeline import UnsupportedProviderVersionError

CASES = [
    (UnsupportedProviderVersionError("bad"), ExitCode.INCOMPATIBLE_VERSION),
    (
        ValueError("strict identity resolution failed"),
        ExitCode.UNRESOLVED_STRICT_CONTRACT,
    ),
    (ValueError("unresolved findings"), ExitCode.UNRESOLVED_STRICT_CONTRACT),
    (ValueError("schema validation failed"), ExitCode.ARTIFACT_VALIDATION_FAILURE),
    (FileNotFoundError("missing"), ExitCode.ARTIFACT_VALIDATION_FAILURE),
    (RuntimeError("boom"), ExitCode.INTERNAL_ERROR),
]


@pytest.mark.parametrize("exc,expected", CASES)
def test_classify_exception_default_artifact(exc, expected) -> None:
    _, code = classify_exception(exc, default=ExitCode.ARTIFACT_VALIDATION_FAILURE)
    assert code == expected


def test_classify_uses_command_default_for_generic_value_error() -> None:
    # A generic ValueError falls to the per-command default (semgrep normalize
    # uses PROVIDER_REPORT_FAILURE).
    _, code = classify_exception(
        ValueError("something else"), default=ExitCode.PROVIDER_REPORT_FAILURE
    )
    assert code == ExitCode.PROVIDER_REPORT_FAILURE


def test_emit_error_json_envelope(capsys) -> None:
    code = emit_error(ValueError("boom"), output_format=OutputFormat.JSON)
    payload = json.loads(capsys.readouterr().err)
    assert payload["ok"] is False
    assert payload["error"]["message"] == "boom"
    assert code == int(ExitCode.ARTIFACT_VALIDATION_FAILURE)


def test_emit_error_text_envelope(capsys) -> None:
    emit_error(ValueError("boom"), output_format=OutputFormat.TEXT)
    assert capsys.readouterr().err.startswith("error[")


def test_diagnostic_render_text_and_json() -> None:
    diag = Diagnostic(code="x", message="m", details={"k": "v"})
    assert diag.render(OutputFormat.TEXT) == "error[x]: m"
    payload = json.loads(diag.render(OutputFormat.JSON))
    assert payload == {
        "ok": False,
        "error": {"code": "x", "message": "m", "details": {"k": "v"}},
    }
