import json
from pathlib import Path

EXPECTED_SCHEMAS = {
    "repository-snapshot.schema.json",
    "gate-result.schema.json",
    "agent-review-payload.schema.json",
    "source-location.schema.json",
    "evidence-record.schema.json",
    "finding.schema.json",
    "finding-classification.schema.json",
    "provider-failure.schema.json",
    "coverage.schema.json",
    "finding-bundle.schema.json",
}


def test_schema_inventory() -> None:
    schema_root = Path("l9_ci/schemas/v1")
    actual = {path.name for path in schema_root.glob("*.schema.json")}
    assert actual == EXPECTED_SCHEMAS


def test_all_schemas_are_valid_json() -> None:
    for path in Path("l9_ci/schemas/v1").glob("*.schema.json"):
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        assert payload["$schema"] == ("https://json-schema.org/draft/2020-12/schema")
