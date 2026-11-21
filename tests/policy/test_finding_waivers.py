"""Witnesses for central finding waivers (``l9.finding-waivers/v1``).

CTO decision 2026-11-21: a waiver names one finding by rule ID, path and
fingerprint, carries an owner, a reason and an expiry, stops applying on its
own once expired, and cannot be supplied by the repository under analysis.
"""

from __future__ import annotations

import json
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.gates import GateStatus, evaluate_gate
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline
from l9_ci.policy import FindingWaiverError, FindingWaiverLedger

FIXTURES = Path("tests/fixtures/semgrep")
REPORT = FIXTURES / "report-sdk-provider-subprocess-injection.json"
POLICY = FIXTURES / "core-semgrep-policy-v4.json"
REPOSITORY = "Quantum-L9/l9-ci-sdk"
RULE = (
    "python.django.security.injection.command.subprocess-injection.subprocess-injection"
)
PATH = "l9_ci/providers/semgrep/provider.py"
FINGERPRINT = "f65ae3b056b2c34fdec05fa7b48591263a961da1b449dc86bd31491a14329b40"


def _entry(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": "SDK-PROVIDER-SUBPROCESS-REQUEST-NAME",
        "owner": "L1/SDK",
        "reason": "taint source is the Django `request`-name heuristic",
        "created": "2026-11-21",
        "expires": "2027-02-21",
        "scope": {
            "repository": REPOSITORY,
            "provider_id": "semgrep",
            "provider_rule_id": RULE,
            "path": PATH,
        },
        "fingerprint": FINGERPRINT,
    }
    entry.update(overrides)
    return entry


def _ledger(directory: Path, *entries: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "waivers.yaml"
    path.write_text(
        yaml.safe_dump({"schema": "l9.finding-waivers/v1", "waivers": list(entries)}),
        encoding="utf-8",
    )
    return path


def _run(
    tmp_path: Path,
    *,
    ledger: Path | None,
    on: str = "2026-11-21",
    repository: str | None = REPOSITORY,
    policy: Path | None = POLICY,
):  # type: ignore[no-untyped-def]
    output = tmp_path / "out" / "bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=REPORT,
            repository_root=Path(".").resolve(),
            snapshot_id="snapshot-1",
            SDK_version="2.0.0-test",
            output_path=output,
            provider_version="1.171.0",
            policy_path=policy,
            required=True,
            generated_at="2026-11-21T00:00:00Z",
            waivers_path=ledger,
            repository=repository,
            waiver_date=date.fromisoformat(on),
        )
    )
    return load_and_validate_bundle(output)


def test_the_fixture_reproduces_the_central_finding() -> None:
    """The fixture's finding is the one Core reported on SDK #135 (run 44843278484)."""
    bundle_finding = json.loads(REPORT.read_text("utf-8"))["results"]
    assert [item["check_id"] for item in bundle_finding] == [RULE]


def test_without_a_ledger_the_finding_blocks(tmp_path: Path) -> None:
    bundle = _run(tmp_path, ledger=None)
    (finding,) = bundle.findings
    assert finding.fingerprint == FINGERPRINT
    assert evaluate_gate(bundle).status is GateStatus.FAIL


def test_an_active_exact_waiver_makes_the_finding_advisory(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "central", _entry())
    bundle = _run(tmp_path, ledger=ledger)
    (classification,) = bundle.classifications
    assert classification.mode.value == "advisory"
    assert classification.waiver_id == "SDK-PROVIDER-SUBPROCESS-REQUEST-NAME"
    # What the policy said is kept: the default blocking resolution.
    assert classification.used_default is True
    assert classification.resolution_status.value == "defaulted"
    assert evaluate_gate(bundle).status is GateStatus.PASS


def test_the_expiry_day_still_applies(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "central", _entry())
    bundle = _run(tmp_path, ledger=ledger, on="2027-02-21")
    assert evaluate_gate(bundle).status is GateStatus.PASS


def test_an_expired_waiver_stops_applying_automatically(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "central", _entry())
    bundle = _run(tmp_path, ledger=ledger, on="2027-02-22")
    (classification,) = bundle.classifications
    assert classification.mode.value == "blocking"
    assert classification.waiver_id is None
    assert evaluate_gate(bundle).status is GateStatus.FAIL
    assert any("expired on 2027-02-21" in item for item in bundle.limitations)


def test_a_waiver_not_yet_in_force_does_not_apply(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "central", _entry(created="2026-12-01"))
    bundle = _run(tmp_path, ledger=ledger, on="2026-11-21")
    assert evaluate_gate(bundle).status is GateStatus.FAIL
    assert any("not in force until" in item for item in bundle.limitations)


@pytest.mark.parametrize(
    "overrides",
    [
        {"fingerprint": "0" * 64},  # the code changed: a new finding
        {"scope": {**_entry()["scope"], "path": "l9_ci/other.py"}},
        {"scope": {**_entry()["scope"], "provider_rule_id": "other.rule"}},
        {"scope": {**_entry()["scope"], "repository": "Quantum-L9/Other"}},
    ],
)
def test_a_waiver_matches_only_its_exact_finding(
    tmp_path: Path, overrides: dict[str, Any]
) -> None:
    ledger = _ledger(tmp_path / "central", _entry(**overrides))
    bundle = _run(tmp_path, ledger=ledger)
    assert evaluate_gate(bundle).status is GateStatus.FAIL


def test_an_unmatched_waiver_is_reported(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "central", _entry(fingerprint="0" * 64))
    bundle = _run(tmp_path, ledger=ledger)
    assert any("matched no finding" in item for item in bundle.limitations)


def test_a_consumer_cannot_supply_its_own_ledger(tmp_path: Path) -> None:
    """Known-bad: a ledger inside the repository under analysis is refused."""
    inside = Path(".").resolve() / ".l9" / "runtime" / "waiver-witness"
    ledger = _ledger(inside, _entry())
    try:
        with pytest.raises(ValueError, match="outside the repository"):
            _run(tmp_path, ledger=ledger)
    finally:
        ledger.unlink()
        inside.rmdir()


def test_a_ledger_needs_a_policy_and_a_repository(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "central", _entry())
    with pytest.raises(ValueError, match="requires a finding policy"):
        _run(tmp_path, ledger=ledger, policy=None)
    with pytest.raises(ValueError, match="repository identity"):
        _run(tmp_path, ledger=ledger, repository=None)


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({k: v for k, v in _entry().items() if k != "owner"}, "must carry exactly"),
        (
            {k: v for k, v in _entry().items() if k != "fingerprint"},
            "must carry exactly",
        ),
        ({k: v for k, v in _entry().items() if k != "expires"}, "must carry exactly"),
        (_entry(fingerprint="xyz"), "64 lowercase hex"),
        (_entry(expires="2026-01-01"), "expires is before created"),
        (_entry(expires="soon"), "ISO date"),
        (_entry(reason="  "), "reason must be a non-empty"),
        (_entry(scope={**_entry()["scope"], "path": "../x.py"}), "repository-relative"),
        (_entry(scope={**_entry()["scope"], "repository": "nope"}), "<owner>/<name>"),
        (_entry(extra=1), "unknown"),
    ],
)
def test_a_malformed_entry_refuses_the_whole_ledger(
    tmp_path: Path, entry: dict[str, Any], message: str
) -> None:
    ledger = _ledger(tmp_path / "central", entry)
    with pytest.raises(FindingWaiverError, match=message):
        FindingWaiverLedger.load(ledger)


def test_duplicate_ids_are_refused(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "central", _entry(), _entry())
    with pytest.raises(FindingWaiverError, match="unique"):
        FindingWaiverLedger.load(ledger)


def test_the_first_entry_validates_against_the_schema() -> None:
    schema = files("l9_ci").joinpath("schemas", "v1", "finding-waivers.schema.json")
    validator = Draft202012Validator(json.loads(schema.read_text(encoding="utf-8")))
    document = {"schema": "l9.finding-waivers/v1", "waivers": [_entry()]}
    assert sorted(validator.iter_errors(document), key=str) == []
    assert FindingWaiverLedger.from_dict(document).waivers[0].owner == "L1/SDK"
