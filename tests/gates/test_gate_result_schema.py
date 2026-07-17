import json
from importlib.resources import files
from jsonschema import Draft202012Validator
from l9_ci.gates import GateResult, GateStatus


def test_gate_result_matches_schema() -> None:
    schema = json.loads(
        files("l9_ci").joinpath("schemas/v1/gate-result.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(
        GateResult(GateStatus.PASS, (), (), (), (), ()).to_dict()
    )
