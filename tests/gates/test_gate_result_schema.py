import json
from importlib.resources import files
import pytest
from jsonschema import Draft202012Validator
from l9_ci.gates import GateResult, GateStatus


def _schema() -> dict:
    return json.loads(
        files("l9_ci").joinpath("schemas/v1/gate-result.schema.json").read_text()
    )


RESULTS = {
    "pass": GateResult(GateStatus.PASS, (), (), (), (), ()),
    "fail_with_blocking": GateResult(
        GateStatus.FAIL, ("f1", "f2"), (), (), (), ("blocking findings exist",)
    ),
    "incomplete_with_providers": GateResult(
        GateStatus.INCOMPLETE,
        (),
        (),
        ("semgrep",),
        ("gitleaks",),
        ("required providers failed", "required provider coverage is incomplete"),
    ),
    "invalid_missing_classification": GateResult(
        GateStatus.INVALID,
        (),
        ("f9",),
        (),
        (),
        ("findings are missing classifications",),
    ),
}


@pytest.mark.parametrize("result", list(RESULTS.values()), ids=list(RESULTS.keys()))
def test_gate_result_artifact_matches_schema(result: GateResult) -> None:
    # The emitted gate-result.json (result.to_dict()) is the canonical artifact
    # that crosses the Core boundary; every status shape must validate.
    Draft202012Validator(_schema()).validate(result.to_dict())


def test_incomplete_summary_counts_are_consistent() -> None:
    result = RESULTS["incomplete_with_providers"]
    payload = result.to_dict()
    assert payload["status"] == "incomplete"
    assert payload["summary"]["fatal_provider_count"] == 1
    assert payload["summary"]["incomplete_provider_count"] == 1
