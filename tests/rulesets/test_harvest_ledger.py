"""The donor harvest ledger holds: one evidenced row per donor rule.

``docs/harvest/semgrep-donor-ledger.yaml`` is what stands between a
specialized consumer rule and its silent loss (L9-CI-SDK-004). These tests do
not re-run the donor rules, which are not in this repository; they check that
the ledger is complete, that every row passes the validator, that every
fixture a row cites exists, and that the ledger and the packaged rules agree.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

from l9_ci.rulesets.semgrep import (
    HARVEST_DISPOSITIONS,
    HARVEST_LEDGER_SCHEMA,
    compose_rulepack,
    rulepack_definitions,
    validate_harvest_ledger,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = REPO_ROOT / "docs" / "harvest" / "semgrep-donor-ledger.yaml"
PACKAGE = REPO_ROOT / "l9_ci" / "rulesets" / "semgrep"

EXPECTED_ROWS = {
    "Quantum-L9/Enrichment.Inference.Engine": 8,
    "Quantum-L9/Cognitive.Engine.Graphs": 8,
    "Quantum-L9/Cursor-Governance": 4,
    "cryptoxdog/IB-Odoo_19": 39,
}


def _document() -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    return document


ROWS: list[dict[str, Any]] = _document()["rows"]


def _row() -> dict[str, Any]:
    return {
        "rule_id": "example.rule",
        "donor": {
            "repository": "Quantum-L9/example",
            "head": "a" * 40,
            "path": ".semgrep/rules.yaml",
            "blob": "b" * 40,
        },
        "behavior": "Flags example().",
        "disposition": "retain_domain",
        "rationale": "Product law.",
        "witnesses": {
            "known_bad": {"evidence": "flags line 3"},
            "known_good": {"evidence": "no finding on line 7"},
            "non_target": {"evidence": "no finding outside the path scope"},
        },
    }


def test_ledger_declares_its_schema_and_passes_the_validator() -> None:
    assert _document()["schema"] == HARVEST_LEDGER_SCHEMA
    assert validate_harvest_ledger(ROWS) == []


def test_every_donor_rule_has_exactly_one_row() -> None:
    per_donor = Counter(row["donor"]["repository"] for row in ROWS)
    assert dict(per_donor) == EXPECTED_ROWS
    assert sum(per_donor.values()) == 59
    keys = [(row["donor"]["repository"], row["rule_id"]) for row in ROWS]
    assert len(set(keys)) == len(keys)


def test_each_donor_is_bound_to_one_exact_head_and_blob() -> None:
    coordinates: dict[str, set[tuple[str, str, str]]] = {}
    for row in ROWS:
        donor = row["donor"]
        coordinates.setdefault(donor["repository"], set()).add(
            (donor["head"], donor["path"], donor["blob"])
        )
    assert all(len(found) == 1 for found in coordinates.values()), coordinates


def test_no_row_is_blank() -> None:
    for row in ROWS:
        assert row["disposition"] in HARVEST_DISPOSITIONS
        for field in ("behavior", "scope", "rationale", "retirement"):
            assert str(row[field]).strip(), f"{row['rule_id']}: {field} is blank"
        for witness in ("known_bad", "known_good", "non_target"):
            assert row["witnesses"][witness]["evidence"].strip()


def test_no_row_retires_a_donor_rule() -> None:
    assert not [
        row["rule_id"] for row in ROWS if row["disposition"] == "retire_duplicate"
    ]
    for row in ROWS:
        assert row["retirement"].startswith("None."), row["rule_id"]


def test_every_cited_sdk_fixture_exists() -> None:
    for row in ROWS:
        for witness in row["witnesses"].values():
            fixture = witness.get("fixture", "")
            if fixture.startswith("tests/"):
                assert (REPO_ROOT / fixture).is_file(), f"{row['rule_id']}: {fixture}"
        evidence = row["witnesses"]["non_target"]["evidence"]
        for word in evidence.split():
            if word.startswith("tests/fixtures/"):
                assert (REPO_ROOT / word.rstrip(".,")).is_file(), word


def test_consolidated_rows_name_a_rule_the_sdk_really_composes() -> None:
    composed = set(
        compose_rulepack(
            languages=("python", "typescript"), include_candidates=True
        ).rule_ids
    )
    for row in ROWS:
        if "sdk_rule" in row:
            assert row["sdk_rule"] in composed, f"{row['rule_id']}: {row['sdk_rule']}"
        else:
            assert row["disposition"] in {"retain_domain", "defer_unknown"}


def test_no_donor_rule_id_is_delivered_by_any_composition() -> None:
    """The non-target witness for every rule that stays at its owner."""
    composed = set(
        compose_rulepack(
            languages=("python", "typescript"), include_candidates=True
        ).rule_ids
    )
    donor_ids = {row["rule_id"] for row in ROWS}
    assert composed.isdisjoint(donor_ids)
    assert not any(
        "plasticos" in rule or "memory-boundary" in rule for rule in composed
    )
    assert not [item for item in rulepack_definitions() if item.kind == "framework"]


def test_promoted_rows_match_the_provenance_recorded_in_the_rule() -> None:
    recorded: dict[str, set[tuple[str, str, str]]] = {}
    for path in sorted((PACKAGE / "packs").rglob("*.yml")):
        for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]:
            harvest = rule["metadata"]["l9"]["harvest"]
            recorded[rule["id"]] = {
                (donor["repository"], donor["head"], donor["blob"])
                for donor in harvest["donors"]
            }
    promoted = [row for row in ROWS if row["disposition"].startswith("promote_")]
    assert promoted
    for row in promoted:
        donor = row["donor"]
        coordinate = (donor["repository"], donor["head"], donor["blob"])
        assert coordinate in recorded[row["sdk_rule"]], row["rule_id"]
    for rule_id, donors in recorded.items():
        from_ledger = {
            (row["donor"]["repository"], row["donor"]["head"], row["donor"]["blob"])
            for row in promoted
            if row["sdk_rule"] == rule_id
        }
        assert donors == from_ledger, rule_id


def test_same_id_pairs_are_compared_by_behaviour_not_by_id() -> None:
    by_key = {(row["donor"]["repository"], row["rule_id"]): row for row in ROWS}
    for rule_id in ("singleton-requires-lock", "float-requires-try-except"):
        ceg = by_key[("Quantum-L9/Cognitive.Engine.Graphs", rule_id)]
        eie = by_key[("Quantum-L9/Enrichment.Inference.Engine", rule_id)]
        assert ceg["disposition"] == "promote_language"
        assert eie["disposition"] == "defer_unknown"
        assert "different behaviour" in eie["rationale"]


def test_validator_accepts_a_complete_row() -> None:
    assert validate_harvest_ledger([_row()]) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"disposition": "retire_duplicate"}, "names no central rule"),
        ({"disposition": "retire_duplicate", "sdk_rule": "l9.x"}, "parity receipt"),
        ({"disposition": "promote_language"}, "names no central rule"),
        ({"disposition": "already_satisfied"}, "names no central rule"),
        ({"disposition": "defer_unknown"}, "no next proof"),
        ({"disposition": "delete_it"}, "unknown disposition"),
        ({"witnesses": {}}, "no known-bad witness"),
        ({"rationale": " "}, "no rationale"),
        ({"behavior": ""}, "behavior is not described"),
    ],
)
def test_validator_refuses_the_shortcuts(change: dict[str, Any], expected: str) -> None:
    row = {**_row(), **change}

    errors = validate_harvest_ledger([row])

    assert any(expected in error for error in errors), errors


def test_validator_refuses_an_unbound_donor_and_a_duplicate_row() -> None:
    unbound = _row()
    unbound["donor"] = {**unbound["donor"], "head": "main", "blob": ""}

    errors = validate_harvest_ledger([unbound])
    assert any("donor.head" in error for error in errors)
    assert any("donor.blob" in error for error in errors)

    duplicate = validate_harvest_ledger([_row(), _row()])
    assert any("second row" in error for error in duplicate)
