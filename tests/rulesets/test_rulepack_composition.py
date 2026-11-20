"""Rulepack composition: exact, reproducible and monotonic (L9-CI-SDK-003)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml
from jsonschema import Draft202012Validator

from l9_ci.__main__ import main
from l9_ci.rulesets.semgrep import (
    SUPPORTED_LANGUAGES,
    RulepackCompositionError,
    compose_rulepack,
    rulepack_definitions,
    ruleset_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "l9_ci" / "rulesets" / "semgrep"
PACK_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "semgrep" / "rules" / "packs"

_SEMGREP = shutil.which("semgrep")
_needs_semgrep = pytest.mark.skipif(
    _SEMGREP is None, reason="semgrep executable not available on PATH"
)


def _schema() -> Mapping[str, Any]:
    path = files("l9_ci").joinpath("schemas", "v1", "rulepack-composition.schema.json")
    document: Mapping[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def _product_rule(path: Path, rule_id: str) -> Path:
    path.write_text(
        yaml.safe_dump(
            {
                "rules": [
                    {
                        "id": rule_id,
                        "pattern": "forbidden_call(...)",
                        "message": "product rule",
                        "languages": ["python"],
                        "severity": "WARNING",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_baseline_composition_is_every_rule_the_scan_directory_holds() -> None:
    composition = compose_rulepack(languages=("python",))

    on_disk = sorted(
        rule["id"]
        for path in ruleset_dir("python").glob("*.yml")
        for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]
    )
    assert list(composition.rule_ids) == on_disk
    assert [pack.pack_id for pack in composition.packs] == ["python-baseline"]
    assert composition.reproducible is True


def test_every_composed_file_digest_is_the_file_content() -> None:
    composition = compose_rulepack(
        languages=("python", "typescript"), include_candidates=True
    )

    for pack in composition.packs:
        for file in pack.files:
            content = (PACKAGE / file.path).read_bytes()
            assert file.sha256 == hashlib.sha256(content).hexdigest()


def test_composition_is_deterministic_and_order_independent() -> None:
    first = compose_rulepack(languages=("python", "typescript"))
    second = compose_rulepack(languages=("typescript", "python", "python"))

    assert first.to_dict() == second.to_dict()
    assert first.content_digest == second.content_digest


def test_digest_changes_when_the_selection_changes() -> None:
    baseline = compose_rulepack(languages=("python",))
    with_candidates = compose_rulepack(languages=("python",), include_candidates=True)

    assert baseline.content_digest != with_candidates.content_digest
    assert set(baseline.rule_ids) < set(with_candidates.rule_ids)


def test_candidate_pack_is_composed_only_on_request() -> None:
    default = compose_rulepack(languages=("python",))
    requested = compose_rulepack(languages=("python",), include_candidates=True)

    assert not any(rule.startswith("l9.python.portable.") for rule in default.rule_ids)
    portable = [
        rule for rule in requested.rule_ids if rule.startswith("l9.python.portable.")
    ]
    assert len(portable) == 4
    assert [pack.status for pack in requested.packs] == ["active", "candidate"]


def test_language_packs_do_not_reach_a_non_target_language() -> None:
    composition = compose_rulepack(languages=("typescript",), include_candidates=True)

    assert [pack.pack_id for pack in composition.packs] == ["typescript-baseline"]
    assert not any(".python." in rule for rule in composition.rule_ids)


def test_baseline_rule_cannot_be_excluded() -> None:
    baseline_rule = compose_rulepack(languages=("python",)).rule_ids[0]

    with pytest.raises(RulepackCompositionError, match="baseline"):
        compose_rulepack(languages=("python",), excluded_rule_ids=(baseline_rule,))


def test_non_baseline_rule_can_be_excluded_and_the_digest_records_it() -> None:
    full = compose_rulepack(languages=("python",), include_candidates=True)
    narrowed = compose_rulepack(
        languages=("python",),
        include_candidates=True,
        excluded_rule_ids=("l9.python.portable.datetime-utcnow",),
    )

    assert "l9.python.portable.datetime-utcnow" not in narrowed.rule_ids
    assert narrowed.excluded_rule_ids == ("l9.python.portable.datetime-utcnow",)
    assert narrowed.content_digest != full.content_digest
    baseline = set(compose_rulepack(languages=("python",)).rule_ids)
    assert baseline <= set(narrowed.rule_ids)


def test_unknown_exclusion_is_refused() -> None:
    with pytest.raises(RulepackCompositionError, match="no composed source"):
        compose_rulepack(languages=("python",), excluded_rule_ids=("not.a.rule",))


def test_product_config_cannot_redefine_a_baseline_rule(tmp_path: Path) -> None:
    baseline_rule = compose_rulepack(languages=("python",)).rule_ids[0]
    shadow = _product_rule(tmp_path / "product.yml", baseline_rule)

    with pytest.raises(RulepackCompositionError, match="redefines"):
        compose_rulepack(languages=("python",), product_configs=(shadow,))


def test_product_config_adds_rules_and_is_pinned_by_content(tmp_path: Path) -> None:
    product = _product_rule(tmp_path / "product.yml", "product.forbidden-call")
    baseline = compose_rulepack(languages=("python",))

    composed = compose_rulepack(languages=("python",), product_configs=(product,))

    assert set(composed.rule_ids) == set(baseline.rule_ids) | {"product.forbidden-call"}
    (entry,) = composed.product_configs
    assert entry.path == "product:product.yml"
    assert entry.sha256 == hashlib.sha256(product.read_bytes()).hexdigest()
    assert str(tmp_path) not in json.dumps(composed.to_dict())

    product.write_text(product.read_text(encoding="utf-8") + "\n# edited\n", "utf-8")
    edited = compose_rulepack(languages=("python",), product_configs=(product,))
    assert edited.content_digest != composed.content_digest


def test_registry_label_makes_the_composition_not_reproducible() -> None:
    pinned = compose_rulepack(languages=("python",))
    labelled = compose_rulepack(languages=("python",), registry_rulesets=("p/python",))

    assert pinned.reproducible is True
    assert labelled.reproducible is False
    assert labelled.unpinned_sources == ("p/python",)
    assert labelled.to_dict()["reproducible"] is False
    assert labelled.content_digest != pinned.content_digest


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"languages": ("kotlin",)}, "no baseline rulepack"),
        ({"languages": ("python",), "frameworks": ("odoo",)}, "framework 'odoo'"),
        ({"languages": ()}, "nothing selected"),
        ({"languages": ("",)}, "non-empty"),
    ],
)
def test_unresolvable_selection_is_refused(
    arguments: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(RulepackCompositionError, match=message):
        compose_rulepack(**arguments)


def test_malformed_product_config_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yml"
    broken.write_text("rules: [\n", encoding="utf-8")

    with pytest.raises(RulepackCompositionError, match="could not be read"):
        compose_rulepack(languages=("python",), product_configs=(broken,))


def test_registry_lists_a_baseline_for_every_supported_language() -> None:
    definitions = rulepack_definitions()

    baselines = {
        item.selector_value: item.directory
        for item in definitions
        if item.kind == "baseline"
    }
    assert baselines == {language: language for language in SUPPORTED_LANGUAGES}
    assert all(
        item.status == "active" for item in definitions if item.kind == "baseline"
    )


def test_every_packaged_rule_directory_is_registered() -> None:
    registered = {item.directory for item in rulepack_definitions()}
    on_disk = {
        path.parent.relative_to(PACKAGE).as_posix() for path in PACKAGE.rglob("*.yml")
    }

    assert on_disk == registered


def test_harvested_rules_carry_identity_mode_and_exact_donor_provenance() -> None:
    for definition in rulepack_definitions():
        if definition.status != "candidate":
            continue
        for path in sorted((PACKAGE / definition.directory).glob("*.yml")):
            for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]:
                metadata = rule["metadata"]
                assert metadata["mode"] == "shadow", rule["id"]
                l9 = metadata["l9"]
                assert l9["canonical_rule_id"].startswith("L9-"), rule["id"]
                harvest = l9["harvest"]
                assert harvest["donor_rule_id"], rule["id"]
                assert harvest["donors"], rule["id"]
                for donor in harvest["donors"]:
                    assert len(donor["head"]) == 40 and len(donor["blob"]) == 40
                    assert donor["repository"] and donor["path"]


def test_composition_payload_conforms_to_its_schema(tmp_path: Path) -> None:
    product = _product_rule(tmp_path / "product.yml", "product.forbidden-call")
    payload = compose_rulepack(
        languages=("python", "typescript"),
        include_candidates=True,
        product_configs=(product,),
        registry_rulesets=("p/python",),
        excluded_rule_ids=("l9.python.portable.datetime-utcnow",),
    ).to_dict()

    assert list(Draft202012Validator(_schema()).iter_errors(payload)) == []
    assert "verdict" not in payload


def test_cli_compose_emits_the_composition(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["l9-ci", "semgrep", "compose", "--language", "python", "--format", "json"],
    )

    assert main() == 0

    result = json.loads(capsys.readouterr().out)["result"]
    assert result == compose_rulepack(languages=("python",)).to_dict()


def test_cli_compose_refuses_a_baseline_exclusion_with_exit_code_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline_rule = compose_rulepack(languages=("python",)).rule_ids[0]
    monkeypatch.setattr(
        "sys.argv",
        [
            "l9-ci",
            "semgrep",
            "compose",
            "--language",
            "python",
            "--exclude-rule",
            baseline_rule,
            "--format",
            "json",
        ],
    )

    assert main() == 2

    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "rulepack_composition_refused"
    assert "baseline" in error["message"]


@pytest.mark.parametrize("pack", ["python-portable"])
def test_candidate_pack_fixture_pins_both_directions(pack: str) -> None:
    for rule_file in sorted((PACKAGE / "packs" / pack).glob("*.yml")):
        fixture = PACK_FIXTURES / pack / f"{rule_file.stem}.py"
        assert fixture.is_file(), f"missing Semgrep fixture {fixture}"
        text = fixture.read_text(encoding="utf-8")
        for rule in yaml.safe_load(rule_file.read_text(encoding="utf-8"))["rules"]:
            assert f"# ruleid: {rule['id']}" in text, f"{rule['id']}: no known-bad"
            assert f"# ok: {rule['id']}" in text, f"{rule['id']}: no known-good"


@_needs_semgrep
@pytest.mark.parametrize("pack", ["python-portable"])
def test_candidate_pack_passes_its_fixture(pack: str) -> None:
    assert _SEMGREP is not None
    proc = subprocess.run(
        [
            _SEMGREP,
            "--test",
            "--metrics=off",
            "--json",
            "--config",
            str(PACKAGE / "packs" / pack),
            str(PACK_FIXTURES / pack),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert proc.returncode == 0, f"semgrep --test failed:\n{proc.stdout}\n{proc.stderr}"
    report = json.loads(proc.stdout)
    checked: set[str] = set()
    for file_result in report["results"].values():
        for rule_id, check in file_result["checks"].items():
            assert check["passed"], f"{rule_id}: {check['matches']}"
            checked.add(rule_id.rsplit("packs.", 1)[-1].split(".", 1)[-1])
    assert len(checked) == 4, checked
