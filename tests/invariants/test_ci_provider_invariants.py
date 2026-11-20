"""Running witnesses for the proposed ``ci_provider_invariants``.

SDK ADR 0020 (Proposed) binds ``L9-CI-SDK-001`` to ``L9-CI-SDK-005`` in
``.l9/integration-contract.yaml``. A statement in YAML is not enforcement, so
every invariant has one positive (known-good) and one negative (known-bad)
witness here, named by its ID.

Two kinds of witness exist while ADR 0020 is being realized:

* A witness whose behaviour the SDK already has runs as an ordinary test.
* A witness that needs a capability a later change adds is marked
  ``xfail(strict=True, raises=ImportError)`` and names the exact missing
  symbol. It is executed, never skipped. ``strict`` makes it fail closed: the
  moment the capability exists the marker itself fails the suite, so the
  marker has to be removed and the assertions have to hold. ``raises`` keeps
  it from hiding any other defect.

The contract test at the bottom keeps this file and the contract in step: an
invariant ID without both witnesses, or a witness for an ID the contract does
not carry, fails.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from l9_ci.capabilities import detect_repository_capabilities
from l9_ci.contracts import (
    Coverage,
    CoverageStatus,
    FindingBundle,
    ProviderRun,
    SnapshotDescriptor,
)
from l9_ci.gates import GATE_RESULT_PROTOCOL, GateStatus, evaluate_gate
from l9_ci.integration import build_observation, validate_observation
from l9_ci.providers import ProviderNormalizationContext
from l9_ci.providers.semgrep import SemgrepProvider
from l9_ci.rulesets.semgrep import ruleset_dir

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / ".l9" / "integration-contract.yaml"
ADR_0020 = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0020-all-applicable-capabilities-and-lossless-provider-evidence.md"
)
ADR_INDEX = REPO_ROOT / "docs" / "adr" / "README.md"
SEMGREP_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "semgrep"
RULE_FIXTURES = SEMGREP_FIXTURES / "rules" / "python"

INVARIANT_IDS = tuple(f"L9-CI-SDK-00{number}" for number in range(1, 6))


def _missing(symbol: str, change: str) -> pytest.MarkDecorator:
    """Fail-closed marker for a witness whose capability is not built yet."""
    return pytest.mark.xfail(
        strict=True,
        raises=ImportError,
        reason=f"missing capability: {symbol} ({change})",
    )


def _write(root: Path, relative: str, text: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _required_semgrep_gate(coverage: Coverage) -> GateStatus:
    bundle = FindingBundle(
        SDK_version="1.0.0",
        generated_at="2026-11-20T00:00:00Z",
        snapshot=SnapshotDescriptor("snapshot-1", "."),
        providers=(ProviderRun("semgrep", "1.0.0", "1.100.0", "import", True),),
        evidence=(),
        findings=(),
        classifications=(),
        provider_failures=(),
        coverage=(coverage,),
    )
    return evaluate_gate(bundle).status


def _normalize(fixture_name: str, *, required: bool) -> Any:
    report = json.loads((SEMGREP_FIXTURES / fixture_name).read_text(encoding="utf-8"))
    return SemgrepProvider().normalize(
        report,
        ProviderNormalizationContext(
            snapshot_id="snapshot-1",
            repository_root=REPO_ROOT,
            provider_version="1.100.0",
            required=required,
        ),
    )


# --- L9-CI-SDK-001: capability selection is exhaustive and deterministic ----


def test_l9_ci_sdk_001_positive_mixed_repository_keeps_every_language(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "service/app.py", "x = 1\n")
    _write(tmp_path, "web/src/index.ts", "export const x = 1;\n")
    _write(tmp_path, "web/src/view.tsx", "export const y = 2;\n")

    first = detect_repository_capabilities(tmp_path)
    second = detect_repository_capabilities(tmp_path)

    assert first.languages == ("python", "typescript")
    assert first == second


@_missing("l9_ci.capabilities.build_capability_inventory", "PR 1b")
def test_l9_ci_sdk_001_negative_malformed_manifest_is_not_absence(
    tmp_path: Path,
) -> None:
    from l9_ci.capabilities import (
        CapabilityState,
        build_capability_inventory,
    )

    _write(tmp_path, "pkg/mod.py", "x = 1\n")
    _write(tmp_path, "pyproject.toml", "[project\nname = \n")

    inventory = build_capability_inventory(tmp_path)

    assert inventory.status is CapabilityState.FAILED
    failed = [
        manifest
        for manifest in inventory.manifests
        if manifest.state is CapabilityState.FAILED
    ]
    assert [manifest.path for manifest in failed] == ["pyproject.toml"]
    assert failed[0].reason


# --- L9-CI-SDK-002: not applicable and coverage are evidence states ---------


@_missing("l9_ci.capabilities.build_capability_inventory", "PR 1b")
def test_l9_ci_sdk_002_positive_no_supported_code_is_reasoned_not_applicable(
    tmp_path: Path,
) -> None:
    from l9_ci.capabilities import (
        CapabilityState,
        build_capability_inventory,
    )

    _write(tmp_path, "README.md", "# docs only\n")
    _write(tmp_path, "data/table.csv", "a,b\n1,2\n")

    inventory = build_capability_inventory(tmp_path)

    assert inventory.status is CapabilityState.NOT_APPLICABLE
    assert inventory.examined_file_count == 2
    assert inventory.reasons
    for prerequisite in inventory.provider_prerequisites:
        assert prerequisite.state is CapabilityState.NOT_APPLICABLE
        assert prerequisite.reason


@pytest.mark.parametrize(
    "status",
    [
        CoverageStatus.SKIPPED,
        CoverageStatus.UNSUPPORTED,
        CoverageStatus.PARTIAL,
        CoverageStatus.FAILED,
    ],
)
def test_l9_ci_sdk_002_negative_skip_or_unsupported_is_never_pass(
    status: CoverageStatus,
) -> None:
    gate = _required_semgrep_gate(Coverage("semgrep", status, 1, 0, ()))
    assert gate is GateStatus.INCOMPLETE


@pytest.mark.parametrize(
    "fixture_name",
    [
        "zero-findings-no-paths.json",
        "zero-findings-empty-scanned.json",
        "skipped-only.json",
    ],
)
def test_l9_ci_sdk_002_negative_zero_findings_over_zero_files_is_never_pass(
    fixture_name: str,
) -> None:
    normalization = _normalize(fixture_name, required=True)

    assert normalization.findings == ()
    assert normalization.coverage.files_analyzed == 0
    assert normalization.coverage.status is not CoverageStatus.COMPLETE
    assert _required_semgrep_gate(normalization.coverage) is GateStatus.INCOMPLETE


# --- L9-CI-SDK-003: rulepack composition is immutable and monotonic ---------


@_missing("l9_ci.rulesets.semgrep.compose_rulepack", "PR 1c")
def test_l9_ci_sdk_003_positive_composition_resolves_one_digest() -> None:
    from l9_ci.rulesets.semgrep import compose_rulepack

    first = compose_rulepack(languages=("python",))
    second = compose_rulepack(languages=("python",))

    assert first.content_digest == second.content_digest
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", first.content_digest)
    assert first.rule_ids == second.rule_ids
    assert first.rule_ids == tuple(sorted(first.rule_ids))
    assert first.rule_ids


@_missing("l9_ci.rulesets.semgrep.compose_rulepack", "PR 1c")
def test_l9_ci_sdk_003_negative_restriction_cannot_suppress_the_baseline() -> None:
    from l9_ci.rulesets.semgrep import (
        RulepackCompositionError,
        compose_rulepack,
    )

    baseline_rule = compose_rulepack(languages=("python",)).rule_ids[0]

    with pytest.raises(RulepackCompositionError, match="baseline"):
        compose_rulepack(
            languages=("python",),
            excluded_rule_ids=(baseline_rule,),
        )


# --- L9-CI-SDK-004: specialized behaviour is preserved by fixtures ----------


def test_l9_ci_sdk_004_positive_fixtured_rules_pin_both_directions() -> None:
    fixtures = sorted(RULE_FIXTURES.glob("*.py"))
    assert fixtures, "no packaged rule fixtures found"
    for fixture in fixtures:
        rule_file = ruleset_dir("python") / f"{fixture.stem}.yml"
        assert rule_file.is_file(), f"{fixture.name} has no packaged rule file"
        text = fixture.read_text(encoding="utf-8")
        assert "# ruleid:" in text, f"{fixture.name} has no known-bad trigger"
        assert "# ok:" in text, f"{fixture.name} has no known-good nontrigger"


@_missing("l9_ci.rulesets.semgrep.validate_harvest_ledger", "PR 1c")
def test_l9_ci_sdk_004_negative_consolidation_without_witness_is_refused() -> None:
    from l9_ci.rulesets.semgrep import validate_harvest_ledger

    name_only_retirement = {
        "donor": {
            "repository": "Quantum-L9/example",
            "head": "0" * 40,
            "path": ".semgrep/rules.yaml",
            "blob": "0" * 40,
        },
        "rule_id": "example.sql-injection",
        "disposition": "retire_duplicate",
        "behavior": "same name as a central rule",
        "witnesses": {},
    }

    errors = validate_harvest_ledger([name_only_retirement])

    assert any("known-bad" in error for error in errors)
    assert any("known-good" in error for error in errors)


# --- L9-CI-SDK-005: native facts and unique findings survive ----------------


def test_l9_ci_sdk_005_positive_native_rule_ids_and_results_survive() -> None:
    report = json.loads((SEMGREP_FIXTURES / "results.json").read_text("utf-8"))
    native = sorted(result["check_id"] for result in report["results"])
    assert native, "the provider fixture carries no native result"

    normalization = _normalize("results.json", required=True)

    assert (
        sorted(record.provider_rule_id for record in normalization.evidence) == native
    )
    assert len(normalization.findings) == len(native)
    assert {record.provider_id for record in normalization.evidence} == {"semgrep"}


def test_l9_ci_sdk_005_negative_observation_rejects_a_verdict() -> None:
    observation = build_observation(
        producer_version="2.0.0",
        repository="Quantum-L9/example",
        revision="a" * 40,
        check_id="l9.tests",
        configuration_digest="b" * 64,
        run_id="1",
        attempt=1,
        status="passed",
        started_at="2026-11-20T00:00:00Z",
        completed_at="2026-11-20T00:00:01Z",
    )
    assert "verdict" not in observation
    validate_observation(observation)

    with pytest.raises(ValueError, match="verdict"):
        validate_observation({**observation, "verdict": "pass"})
    assert "assurance" not in GATE_RESULT_PROTOCOL.lower()


# --- The contract, the ADR and this file stay in step -----------------------


def _contract_invariants() -> dict[str, str]:
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    entries = contract["ci_provider_invariants"]
    return {entry["id"]: " ".join(entry["statement"].split()) for entry in entries}


def test_contract_carries_exactly_the_five_proposed_invariants() -> None:
    invariants = _contract_invariants()
    assert tuple(invariants) == INVARIANT_IDS
    for statement in invariants.values():
        assert statement


def test_adr_0020_is_proposed_and_indexed() -> None:
    adr = ADR_0020.read_text(encoding="utf-8")
    status = adr.split("## Status", 1)[1].split("##", 1)[0].strip()
    assert status.startswith("Proposed.")
    assert "Accepted" not in status

    rows = [
        line
        for line in ADR_INDEX.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| [0020]({ADR_0020.name})")
    ]
    assert len(rows) == 1
    assert rows[0].rstrip().endswith("| Proposed |")


@pytest.mark.parametrize("invariant_id", INVARIANT_IDS)
def test_every_invariant_has_a_positive_and_a_negative_witness(
    invariant_id: str,
) -> None:
    prefix = "test_" + invariant_id.lower().replace("-", "_")
    names = [name for name in vars(sys.modules[__name__]) if name.startswith(prefix)]
    assert any(name.startswith(f"{prefix}_positive_") for name in names)
    assert any(name.startswith(f"{prefix}_negative_") for name in names)


def test_no_witness_names_an_invariant_the_contract_lacks() -> None:
    pattern = re.compile(r"^test_l9_ci_sdk_(\d{3})_")
    witnessed = {
        f"L9-CI-SDK-{match.group(1)}"
        for name in vars(sys.modules[__name__])
        if (match := pattern.match(name))
    }
    assert witnessed == set(_contract_invariants())
