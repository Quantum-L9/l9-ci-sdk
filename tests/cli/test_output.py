import json
from l9_ci.cli import OutputFormat, render_success


def test_json_output() -> None:
    assert (
        json.loads(render_success({"b": 2}, output_format=OutputFormat.JSON))["ok"]
        is True
    )
