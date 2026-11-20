"""Running witnesses for the proposed ``ci_provider_invariants``.

SDK ADR 0020 (Proposed) binds ``L9-CI-SDK-001`` to ``L9-CI-SDK-005`` in
``.l9/integration-contract.yaml``. A statement in YAML is not enforcement, so
every invariant has one positive (known-good) and one negative (known-bad)
witness here, named by its ID.

Every witness is an ordinary test. While the capabilities were being built,
the witnesses that needed one were strict ``xfail`` and named the missing
symbol; each was converted in the change that added its capability.

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

from l9_ci.capabilities import (
    AnalysisTarget,
    CapabilityInventory,
    CapabilityState,
    build_capability_inventory,
    detect_repository_capabilities,
)
from l9_ci.commands.providers import default_analysis_targets
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
from l9_ci.rulesets.semgrep import (
    RulepackComposition,
    RulepackCompositionError,
    compose_rulepack,
    ruleset_dir,
    validate_harvest_ledger,
)

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

_TARGETS = default_analysis_targets(REPO_ROOT)

INVARIANT_IDS = tuple(f"L9-CI-SDK-00{number}" for number in range(1, 6))


def _inventory(
    root: Path,
    targets: tuple[AnalysisTarget, ...],
) -> CapabilityInventory:
    return build_capability_inventory(root, targets=targets, SDK_version="2.0.0")


def _compose(**selection: Any) -> RulepackComposition:
    """Compose the way a caller does, with a fixed SDK version."""
    return compose_rulepack(**selection, SDK_version="2.0.0")


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


def test_l9_ci_sdk_001_positive_odoo_recognizes_python_and_xml(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "addons/sale_ext/__manifest__.py", '{"name": "Sale Ext"}\n')
    _write(tmp_path, "addons/sale_ext/models/sale.py", "x = 1\n")
    _write(tmp_path, "addons/sale_ext/views/sale.xml", "<odoo/>\n")

    inventory = _inventory(tmp_path, _TARGETS)

    (odoo,) = inventory.frameworks
    assert odoo.state is CapabilityState.APPLICABLE
    assert dict(odoo.language_file_counts) == {"python": 2, "xml": 1}
    assert {item.language for item in inventory.languages} == {"python", "xml"}


def test_l9_ci_sdk_001_positive_javascript_is_analyzed_not_hidden(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "svc/app.py", "x = 1\n")
    _write(tmp_path, "web/index.js", "module.exports = 1;\n")

    inventory = _inventory(tmp_path, _TARGETS)

    states = {item.language: item.state for item in inventory.languages}
    assert states == {
        "javascript": CapabilityState.APPLICABLE,
        "python": CapabilityState.APPLICABLE,
    }


def test_l9_ci_sdk_001_negative_unscanned_suffix_is_not_counted_as_covered(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "src/index.ts", "export const x = 1;\n")
    _write(tmp_path, "src/worker.mts", "export const w = 1;\n")

    inventory = _inventory(tmp_path, _TARGETS)

    (typescript,) = inventory.languages
    assert typescript.unanalyzed_file_count == 1
    covered = {
        item.target: item.file_count for item in inventory.provider_prerequisites
    }
    assert covered["language:typescript"] == 1


def test_l9_ci_sdk_001_negative_malformed_manifest_is_not_absence(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "pkg/mod.py", "x = 1\n")
    _write(tmp_path, "pyproject.toml", "[project\nname = \n")

    inventory = _inventory(tmp_path, _TARGETS)

    assert inventory.status is CapabilityState.FAILED
    failed = [
        manifest
        for manifest in inventory.manifests
        if manifest.state is CapabilityState.FAILED
    ]
    assert [manifest.path for manifest in failed] == ["pyproject.toml"]
    assert failed[0].reason


def test_l9_ci_sdk_001_negative_second_language_is_never_hidden(
    tmp_path: Path,
) -> None:
    # Forty Python files and one TypeScript file: a primary-language heuristic
    # would report Python alone.
    for index in range(40):
        _write(tmp_path, f"svc/mod_{index}.py", "x = 1\n")
    _write(tmp_path, "web/index.ts", "export const x = 1;\n")
    _write(tmp_path, "native/lib.rs", "fn main() {}\n")

    inventory = _inventory(tmp_path, _TARGETS)

    states = {item.language: item.state for item in inventory.languages}
    assert states == {
        "python": CapabilityState.APPLICABLE,
        "typescript": CapabilityState.APPLICABLE,
        "rust": CapabilityState.UNSUPPORTED,
    }
    applicable = [
        item.target
        for item in inventory.provider_prerequisites
        if item.state is CapabilityState.APPLICABLE
    ]
    assert applicable == ["language:python", "language:typescript"]


# --- L9-CI-SDK-002: not applicable and coverage are evidence states ---------


def test_l9_ci_sdk_002_positive_no_supported_code_is_reasoned_not_applicable(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "README.md", "# docs only\n")
    _write(tmp_path, "data/table.csv", "a,b\n1,2\n")

    inventory = _inventory(tmp_path, _TARGETS)

    assert inventory.status is CapabilityState.NOT_APPLICABLE
    assert inventory.examined_file_count == 2
    assert inventory.reasons
    for prerequisite in inventory.provider_prerequisites:
        assert prerequisite.state is CapabilityState.NOT_APPLICABLE
        assert prerequisite.reason


def test_l9_ci_sdk_002_negative_missing_executable_is_incomplete(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "svc/app.py", "x = 1\n")
    missing = tuple(
        AnalysisTarget(
            target.provider_id,
            target.scope,
            target.name,
            target.languages,
            target.rulepack,
            target.rulepack_resolved,
            executable="missing",
        )
        for target in _TARGETS
    )

    inventory = _inventory(tmp_path, missing)

    assert inventory.status is CapabilityState.INCOMPLETE
    python = next(
        item
        for item in inventory.provider_prerequisites
        if item.target == "language:python"
    )
    assert python.state is CapabilityState.INCOMPLETE


def test_l9_ci_sdk_002_negative_unsupported_is_not_not_applicable(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "app/Main.kt", "fun main() {}\n")

    inventory = _inventory(tmp_path, _TARGETS)

    assert inventory.status is CapabilityState.UNSUPPORTED
    assert inventory.status is not CapabilityState.NOT_APPLICABLE


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


def test_l9_ci_sdk_003_positive_composition_resolves_one_digest() -> None:
    first = _compose(languages=("python",), include_candidates=True)
    second = _compose(languages=("python",), include_candidates=True)

    assert first.content_digest == second.content_digest
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", first.content_digest)
    assert first.rule_ids == second.rule_ids
    assert first.rule_ids == tuple(sorted(first.rule_ids))
    assert first.rule_ids
    assert first.reproducible is True
    for pack in first.packs:
        for file in pack.files:
            assert re.fullmatch(r"[0-9a-f]{64}", file.sha256)


def test_l9_ci_sdk_003_negative_restriction_cannot_suppress_the_baseline() -> None:
    baseline_rule = _compose(languages=("python",)).rule_ids[0]

    with pytest.raises(RulepackCompositionError, match="baseline"):
        _compose(
            languages=("python",),
            excluded_rule_ids=(baseline_rule,),
        )


def test_l9_ci_sdk_003_negative_registry_label_is_not_a_pin() -> None:
    labelled = _compose(languages=("python",), registry_rulesets=("p/python",))

    assert labelled.reproducible is False
    assert labelled.unpinned_sources == ("p/python",)


# --- L9-CI-SDK-004: specialized behaviour is preserved by fixtures ----------


def test_l9_ci_sdk_004_positive_fixtured_rules_pin_both_directions() -> None:
    # A fixture is paired by stem, whatever its suffix: the repository stores
    # one of them as .pyfixture so that scanners do not read it as product code.
    fixtures = sorted(path for path in RULE_FIXTURES.iterdir() if path.is_file())
    assert fixtures, "no packaged rule fixtures found"
    for fixture in fixtures:
        rule_file = ruleset_dir("python") / f"{fixture.stem}.yml"
        assert rule_file.is_file(), f"{fixture.name} has no packaged rule file"
        text = fixture.read_text(encoding="utf-8")
        assert "# ruleid:" in text, f"{fixture.name} has no known-bad trigger"
        assert "# ok:" in text, f"{fixture.name} has no known-good nontrigger"
    fixtured = {fixture.stem for fixture in fixtures}
    packaged = {path.stem for path in ruleset_dir("python").glob("*.yml")}
    assert fixtured == packaged, (
        "every packaged Python rule file needs a fixture: "
        f"missing={sorted(packaged - fixtured)}"
    )


def test_l9_ci_sdk_004_positive_harvested_rules_keep_donor_witnesses() -> None:
    pack = REPO_ROOT / "l9_ci" / "rulesets" / "semgrep" / "packs" / "python-portable"
    fixture = (RULE_FIXTURES.parent / "packs" / "python-portable").glob("*.py")
    text = "\n".join(path.read_text(encoding="utf-8") for path in fixture)
    rules = [
        rule
        for path in sorted(pack.glob("*.yml"))
        for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]
    ]
    assert rules
    for rule in rules:
        assert f"# ruleid: {rule['id']}" in text, f"{rule['id']}: no known-bad"
        assert f"# ok: {rule['id']}" in text, f"{rule['id']}: no known-good"
        assert rule["metadata"]["l9"]["harvest"]["donors"]


def test_l9_ci_sdk_004_negative_consolidation_without_witness_is_refused() -> None:
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


def test_contract_marks_the_invariant_block_as_proposed() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    preamble = text.split("\nci_provider_invariants:\n", 1)[0].rsplit("\n\n", 1)[1]
    assert preamble.startswith("# PROPOSED, NOT ADMITTED.")
    assert "ADR 0020" in preamble


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
