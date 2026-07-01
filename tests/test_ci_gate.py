from l9_ci.gate.ci_gate import evaluate


def test_gate_passes_when_required_success() -> None:
    result = evaluate({"validate": "success", "lint": "success", "test": "success"}, ["validate", "lint", "test"])
    assert result.passed


def test_gate_fails_on_missing_required() -> None:
    result = evaluate({"validate": "success"}, ["validate", "lint"])
    assert not result.passed
    assert result.failed_required["lint"] == "missing"


def test_gate_fails_on_required_failure() -> None:
    result = evaluate({"validate": "success", "lint": "failure"}, ["validate", "lint"])
    assert not result.passed
