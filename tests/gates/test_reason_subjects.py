"""Every non-PASS reason names its subjects (L9-SIGNAL-001, ADR 0025).

One witness per reason class: gate reasons (and their ``reason_details``),
provider execution failures, runner failures, baseline refusals, bundle
validation and compatibility. The static invariant at the end refuses a
subject-less literal reason anywhere in the modules that emit them.
"""

from __future__ import annotations

import ast
import json
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from l9_ci.artifacts import validate_bundle_semantics
from l9_ci.artifacts.compatibility import check_bundle_compatibility
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    Finding,
    FindingBundle,
    FindingClassification,
    ProviderFailure,
    ProviderFailureType,
    ProviderRun,
    ResolutionStatus,
    RuleMode,
    SnapshotDescriptor,
    SourceLocation,
    format_subjects,
    subject_reason,
)
from l9_ci.contracts.subjects import display_path, strip_absolute_paths, text_tail
from l9_ci.gates import GateStatus, ReasonCode, evaluate_gate
from l9_ci.providers import ProviderExecutionResult
from l9_ci.providers.semgrep import SemgrepProvider


def _finding(name: str, path: str = "src/app.py", line: int = 7) -> Finding:
    return Finding(
        finding_id=f"fn-{name}",
        snapshot_id="snapshot-1",
        provider_id="semgrep",
        provider_rule_id=f"registry.rule.{name}",
        canonical_rule_id=f"L9-RULE-{name.upper()}",
        category="security",
        message="m",
        evidence_ids=(f"ev-{name}",),
        locations=(
            SourceLocation(normalized_path=path, start_line=line, end_line=line),
        ),
        fingerprint=f"{name:0<64}"[:64],
    )


def _classification(name: str, mode: RuleMode) -> FindingClassification:
    unresolved = mode is RuleMode.UNRESOLVED
    return FindingClassification(
        finding_id=f"fn-{name}",
        mode=mode,
        resolution_status=(
            ResolutionStatus.UNRESOLVED if unresolved else ResolutionStatus.DEFAULTED
        ),
        used_default=not unresolved,
    )


def _bundle(**overrides) -> FindingBundle:  # type: ignore[no-untyped-def]
    fields = {
        "SDK_version": "2.0.0",
        "generated_at": "2026-11-21T00:00:00Z",
        "snapshot": SnapshotDescriptor("snapshot-1", "."),
        "providers": (ProviderRun("semgrep", "1.0.0", "1.186.0", "execute", True),),
        "evidence": (),
        "findings": (),
        "classifications": (),
        "provider_failures": (),
        "coverage": (Coverage("semgrep", CoverageStatus.COMPLETE, 1, 1, ()),),
    }
    fields.update(overrides)
    return FindingBundle(**fields)  # type: ignore[arg-type]


def _schema_valid(result) -> None:  # type: ignore[no-untyped-def]
    schema = files("l9_ci").joinpath("schemas", "v1", "gate-result.schema.json")
    validator = Draft202012Validator(json.loads(schema.read_text(encoding="utf-8")))
    assert sorted(validator.iter_errors(result.to_dict()), key=str) == []


# --- the helpers ------------------------------------------------------------


def test_subjects_are_sorted_unique_and_capped() -> None:
    items = [f"s{index:02d}" for index in range(25)] + ["s00"]
    assert format_subjects(items) == ", ".join(f"s{i:02d}" for i in range(20)) + (
        " (+5 more)"
    )
    assert subject_reason("x failed", ["b", "a"]) == "x failed: a, b"


@pytest.mark.parametrize("subjects", [[], [" "], [""]])
def test_a_reason_without_a_subject_cannot_be_built(subjects: list[str]) -> None:
    with pytest.raises(ValueError, match="at least one subject"):
        subject_reason("x failed", subjects)


def test_no_absolute_path_reaches_a_reason(tmp_path: Path) -> None:
    assert strip_absolute_paths("open /home/runner/work/a/b.py:3 failed") == (
        "open …/b.py:3 failed"
    )
    assert display_path(tmp_path / "src" / "a.py", tmp_path) == "src/a.py"
    assert display_path(Path("/elsewhere/report.json"), tmp_path) == "…/report.json"
    assert text_tail("x\n\nError: /tmp/q/z.json missing\n") == "Error: …/z.json missing"
    assert text_tail("") == "no output"


# --- gate reasons -------------------------------------------------------------


def test_blocking_findings_name_rule_and_path_line() -> None:
    result = evaluate_gate(
        _bundle(
            findings=(_finding("a", "src/a.py", 3), _finding("b", "lib/b.py", 9)),
            classifications=(
                _classification("a", RuleMode.BLOCKING),
                _classification("b", RuleMode.BLOCKING),
            ),
        )
    )
    assert result.status is GateStatus.FAIL
    assert result.reasons == (
        "blocking findings exist: L9-RULE-A at src/a.py:3, L9-RULE-B at lib/b.py:9",
    )
    (detail,) = result.reason_details
    assert detail.code is ReasonCode.BLOCKING_FINDINGS
    assert detail.subjects == ("L9-RULE-A at src/a.py:3", "L9-RULE-B at lib/b.py:9")
    _schema_valid(result)


def test_more_than_twenty_findings_are_capped_and_counted() -> None:
    names = [f"r{index:02d}" for index in range(23)]
    result = evaluate_gate(
        _bundle(
            findings=tuple(_finding(name, "src/x.py", 1) for name in names),
            classifications=tuple(
                _classification(name, RuleMode.BLOCKING) for name in names
            ),
        )
    )
    (detail,) = result.reason_details
    assert len(detail.subjects) == 20 and detail.omitted == 3
    assert result.reasons[0].endswith("(+3 more)")
    assert len(result.blocking_finding_ids) == 23  # the IDs stay complete
    _schema_valid(result)


def test_unresolved_findings_are_named_under_strict_evaluation() -> None:
    result = evaluate_gate(
        _bundle(
            findings=(_finding("u"),),
            classifications=(_classification("u", RuleMode.UNRESOLVED),),
        )
    )
    assert result.status is GateStatus.INCOMPLETE
    assert result.reasons == (
        "unresolved findings exist under strict evaluation: L9-RULE-U at src/app.py:7",
    )


def test_missing_classifications_name_the_findings() -> None:
    result = evaluate_gate(_bundle(findings=(_finding("m", "src/m.py", 2),)))
    assert result.status is GateStatus.INVALID
    assert result.reasons == (
        "findings are missing classifications: L9-RULE-M at src/m.py:2",
    )


@pytest.mark.parametrize(
    ("fatal", "code", "text"),
    [
        (True, ReasonCode.REQUIRED_PROVIDER_FAILED, "required providers failed"),
        (
            False,
            ReasonCode.REQUIRED_PROVIDER_NONFATAL_FAILURE,
            "required providers reported non-fatal failures",
        ),
    ],
)
def test_provider_failures_name_provider_type_and_error(
    fatal: bool, code: ReasonCode, text: str
) -> None:
    failure = ProviderFailure(
        provider_id="semgrep",
        failure_type=ProviderFailureType.EXECUTION_ERROR,
        message="Semgrep exited with code 2: invalid config",
        required=True,
        fatal=fatal,
    )
    result = evaluate_gate(_bundle(provider_failures=(failure,)))
    assert result.status is GateStatus.INCOMPLETE
    expected = "semgrep: execution_error: Semgrep exited with code 2: invalid config"
    assert f"{text}: {expected}" in result.reasons
    assert any(
        detail.code is code and detail.subjects == (expected,)
        for detail in result.reason_details
    )
    _schema_valid(result)


@pytest.mark.parametrize(
    ("coverage", "subject"),
    [
        (
            (
                Coverage(
                    "semgrep", CoverageStatus.PARTIAL, 2, 1, ("timeout: src/big.py",)
                ),
            ),
            "semgrep: coverage partial: timeout: src/big.py",
        ),
        ((), "semgrep: no coverage record"),
    ],
)
def test_incomplete_coverage_names_provider_status_and_limitations(
    coverage: tuple[Coverage, ...], subject: str
) -> None:
    result = evaluate_gate(_bundle(coverage=coverage))
    assert result.status is GateStatus.INCOMPLETE
    assert result.reasons == (f"required provider coverage is incomplete: {subject}",)


def test_pass_has_no_reason() -> None:
    result = evaluate_gate(_bundle())
    assert result.status is GateStatus.PASS
    assert result.reasons == () and result.reason_details == ()
    _schema_valid(result)


# --- provider and runner failures ---------------------------------------------


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            ProviderExecutionResult(
                exit_code=-1,
                report_path=None,
                stdout="",
                stderr="",
                timed_out=True,
            ),
            "Semgrep execution timed out: no output",
        ),
        (
            ProviderExecutionResult(
                exit_code=2,
                report_path=Path("r.json"),
                stdout="",
                stderr="[ERROR] invalid rule in /home/ci/rules/x.yml\n",
            ),
            "Semgrep exited unsuccessfully with code 2: [ERROR] invalid rule in …/x.yml",
        ),
        (
            ProviderExecutionResult(
                exit_code=-1,
                report_path=None,
                stdout="",
                stderr="failed to launch semgrep: [Errno 2] No such file: '/usr/bin/semgrep'",
            ),
            "Semgrep did not produce a report (exit -1): failed to launch semgrep: "
            "[Errno 2] No such file: '…/semgrep'",
        ),
    ],
)
def test_provider_execution_failures_carry_exit_code_and_stderr(
    result: ProviderExecutionResult, expected: str
) -> None:
    failure = SemgrepProvider().execution_failure(
        result, required=True, provider_version="1.186.0"
    )
    assert failure is not None
    assert failure.message == expected


def test_a_malformed_report_names_its_errors() -> None:
    normalization = SemgrepProvider().normalize(
        {"results": "not a list"},
        __import__("l9_ci.providers", fromlist=["x"]).ProviderNormalizationContext(
            snapshot_id="s",
            repository_root=Path("."),
            provider_version="1.186.0",
            required=True,
        ),
    )
    (failure,) = normalization.failures
    assert failure.message.startswith("Semgrep report failed structural validation: ")
    assert "results" in failure.message


# --- bundle validation and compatibility ---------------------------------------


def test_duplicate_ids_are_named() -> None:
    finding = _finding("d")
    errors = validate_bundle_semantics(
        _bundle(
            findings=(finding, finding),
            classifications=(_classification("d", RuleMode.BLOCKING),),
        )
    ).errors
    assert "finding IDs must be unique: fn-d (x2)" in errors


def test_a_non_string_schema_version_is_named() -> None:
    payload = {"schema": "l9.finding-bundle/v1", "schema_version": 2}
    result = check_bundle_compatibility(payload)
    assert "schema_version must be a string: got int 2" in result.errors


# --- the invariant --------------------------------------------------------------

_EMITTERS = ("gates", "pipeline", "providers", "artifacts")
_SINKS = {"reasons", "errors", "limitations"}


def _subject_less(node: ast.expr) -> bool:
    """A reason built from text alone: a plain string or an f-string with no value."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):
        return not any(isinstance(part, ast.FormattedValue) for part in node.values)
    return False


def _violations() -> list[str]:
    root = Path(__file__).resolve().parents[2] / "l9_ci"
    found = []
    for package in _EMITTERS:
        for path in sorted((root / package).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                candidates: list[ast.expr] = []
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "append"
                    and isinstance(func.value, ast.Name)
                    and func.value.id in _SINKS
                    and node.args
                ):
                    candidates.append(node.args[0])
                if isinstance(func, ast.Name) and func.id in {
                    "ProviderFailure",
                    "_failure",
                }:
                    candidates += [k.value for k in node.keywords if k.arg == "message"]
                    if func.id == "_failure" and len(node.args) >= 4:
                        candidates.append(node.args[3])
                for candidate in candidates:
                    if _subject_less(candidate):
                        relative = path.relative_to(root.parent)
                        found.append(f"{relative}:{candidate.lineno}")
    return found


def test_no_reason_is_emitted_without_a_subject() -> None:
    """Known-bad: a literal reason or failure message names nothing."""
    assert _violations() == []


def test_the_invariant_catches_a_subject_less_reason(tmp_path: Path) -> None:
    tree = ast.parse('reasons.append("required providers failed")')
    call = tree.body[0].value  # type: ignore[attr-defined]
    assert _subject_less(call.args[0])
    tree = ast.parse('reasons.append(f"required providers failed: {ids}")')
    assert not _subject_less(tree.body[0].value.args[0])  # type: ignore[attr-defined]
