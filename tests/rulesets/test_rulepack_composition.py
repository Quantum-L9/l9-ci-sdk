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
    RulepackComposition,
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


def _compose(**selection: Any) -> RulepackComposition:
    """Compose the way a caller does, with a fixed SDK version."""
    return compose_rulepack(**selection, SDK_version="2.0.0")


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
    composition = _compose(languages=("python",))

    on_disk = sorted(
        rule["id"]
        for path in ruleset_dir("python").glob("*.yml")
        for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]
    )
    assert list(composition.rule_ids) == on_disk
    assert [pack.pack_id for pack in composition.packs] == ["python-baseline"]
    assert composition.reproducible is True


def test_every_composed_file_digest_is_the_file_content() -> None:
    composition = _compose(languages=("python", "typescript"), include_candidates=True)

    for pack in composition.packs:
        for file in pack.files:
            content = (PACKAGE / file.path).read_bytes()
            assert file.sha256 == hashlib.sha256(content).hexdigest()


def test_composition_is_deterministic_and_order_independent() -> None:
    first = _compose(languages=("python", "typescript"))
    second = _compose(languages=("typescript", "python", "python"))

    assert first.to_dict() == second.to_dict()
    assert first.content_digest == second.content_digest


def test_digest_changes_when_the_selection_changes() -> None:
    baseline = _compose(languages=("python",))
    with_candidates = _compose(languages=("python",), include_candidates=True)

    assert baseline.content_digest != with_candidates.content_digest
    assert set(baseline.rule_ids) < set(with_candidates.rule_ids)


def test_candidate_pack_is_composed_only_on_request() -> None:
    default = _compose(languages=("python",))
    requested = _compose(languages=("python",), include_candidates=True)

    assert not any(rule.startswith("l9.python.portable.") for rule in default.rule_ids)
    portable = [
        rule for rule in requested.rule_ids if rule.startswith("l9.python.portable.")
    ]
    assert len(portable) == 4
    assert [pack.status for pack in requested.packs] == ["active", "candidate"]


def test_language_packs_do_not_reach_a_non_target_language() -> None:
    composition = _compose(languages=("typescript",), include_candidates=True)

    assert [pack.pack_id for pack in composition.packs] == ["typescript-baseline"]
    assert not any(".python." in rule for rule in composition.rule_ids)


def test_baseline_rule_cannot_be_excluded() -> None:
    baseline_rule = _compose(languages=("python",)).rule_ids[0]

    with pytest.raises(RulepackCompositionError, match="baseline"):
        _compose(languages=("python",), excluded_rule_ids=(baseline_rule,))


def test_non_baseline_rule_can_be_excluded_and_the_digest_records_it() -> None:
    full = _compose(languages=("python",), include_candidates=True)
    narrowed = _compose(
        languages=("python",),
        include_candidates=True,
        excluded_rule_ids=("l9.python.portable.datetime-utcnow",),
    )

    assert "l9.python.portable.datetime-utcnow" not in narrowed.rule_ids
    assert narrowed.excluded_rule_ids == ("l9.python.portable.datetime-utcnow",)
    assert narrowed.content_digest != full.content_digest
    baseline = set(_compose(languages=("python",)).rule_ids)
    assert baseline <= set(narrowed.rule_ids)


def test_unknown_exclusion_is_refused() -> None:
    with pytest.raises(RulepackCompositionError, match="no composed source"):
        _compose(languages=("python",), excluded_rule_ids=("not.a.rule",))


def test_product_config_cannot_redefine_a_baseline_rule(tmp_path: Path) -> None:
    baseline_rule = _compose(languages=("python",)).rule_ids[0]
    shadow = _product_rule(tmp_path / "product.yml", baseline_rule)

    with pytest.raises(RulepackCompositionError, match="redefines"):
        _compose(languages=("python",), product_configs=(shadow,))


def test_product_config_adds_rules_and_is_pinned_by_content(tmp_path: Path) -> None:
    product = _product_rule(tmp_path / "product.yml", "product.forbidden-call")
    baseline = _compose(languages=("python",))

    composed = _compose(languages=("python",), product_configs=(product,))

    assert set(composed.rule_ids) == set(baseline.rule_ids) | {"product.forbidden-call"}
    (entry,) = composed.product_configs
    assert entry.path == f"product:{entry.sha256[:12]}:product.yml"
    assert entry.sha256 == hashlib.sha256(product.read_bytes()).hexdigest()
    assert str(tmp_path) not in json.dumps(composed.to_dict())

    product.write_text(product.read_text(encoding="utf-8") + "\n# edited\n", "utf-8")
    edited = _compose(languages=("python",), product_configs=(product,))
    assert edited.content_digest != composed.content_digest


def test_registry_label_makes_the_composition_not_reproducible() -> None:
    pinned = _compose(languages=("python",))
    labelled = _compose(languages=("python",), registry_rulesets=("p/python",))

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
        _compose(**arguments)


def test_malformed_product_config_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yml"
    broken.write_text("rules: [\n", encoding="utf-8")

    with pytest.raises(RulepackCompositionError, match="could not be read"):
        _compose(languages=("python",), product_configs=(broken,))


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
    payload = _compose(
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
    expected = _compose(languages=("python",)).to_dict()
    assert result["materialized"] == []
    assert {**result["composition"], "SDK_version": "2.0.0"} == expected
    assert result["composition"]["SDK_version"]


def test_cli_compose_refuses_a_baseline_exclusion_with_exit_code_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline_rule = _compose(languages=("python",)).rule_ids[0]
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


def test_composition_carries_the_sdk_version_outside_the_digest() -> None:
    first = compose_rulepack(languages=("python",), SDK_version="2.0.0")
    second = compose_rulepack(languages=("python",), SDK_version="2.1.0")

    assert first.to_dict()["SDK_version"] == "2.0.0"
    assert second.to_dict()["SDK_version"] == "2.1.0"
    assert first.content_digest == second.content_digest
    with pytest.raises(RulepackCompositionError, match="SDK_version"):
        compose_rulepack(languages=("python",), SDK_version=" ")


def test_same_named_product_configs_compose_in_one_order(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = _product_rule(tmp_path / "a" / "product.yml", "product.first")
    second = _product_rule(tmp_path / "b" / "product.yml", "product.second")

    forward = _compose(languages=("python",), product_configs=(first, second))
    backward = _compose(languages=("python",), product_configs=(second, first))

    assert forward.to_dict() == backward.to_dict()
    assert forward.content_digest == backward.content_digest
    labels = [item.path for item in forward.product_configs]
    assert len(set(labels)) == 2


def test_composition_exposes_no_source_location() -> None:
    composition = _compose(languages=("python",), include_candidates=True)

    assert not hasattr(composition, "config_paths")
    assert str(PACKAGE) not in json.dumps(composition.to_dict())
    assert str(PACKAGE) not in repr(composition)


def _materialized_rule_ids(paths: tuple[Path, ...]) -> list[str]:
    return sorted(
        rule["id"]
        for path in paths
        for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]
    )


def test_materialize_writes_exactly_the_composed_rules(tmp_path: Path) -> None:
    product = _product_rule(tmp_path / "product.yml", "product.forbidden-call")
    composition = _compose(
        languages=("python",),
        include_candidates=True,
        product_configs=(product,),
        excluded_rule_ids=("l9.python.portable.datetime-utcnow",),
    )

    written = composition.materialize(tmp_path / "out")

    assert _materialized_rule_ids(written) == list(composition.rule_ids)
    assert "l9.python.portable.datetime-utcnow" not in _materialized_rule_ids(written)
    assert [path.name for path in written] == sorted(path.name for path in written)


def test_materialize_copies_an_untouched_file_byte_for_byte(tmp_path: Path) -> None:
    composition = _compose(languages=("python",))

    written = composition.materialize(tmp_path / "out")

    digests = sorted(hashlib.sha256(path.read_bytes()).hexdigest() for path in written)
    recorded = sorted(file.sha256 for pack in composition.packs for file in pack.files)
    assert digests == recorded


def test_materialize_omits_a_file_whose_every_rule_is_excluded(tmp_path: Path) -> None:
    product = _product_rule(tmp_path / "product.yml", "product.forbidden-call")
    composition = _compose(
        languages=("python",),
        product_configs=(product,),
        excluded_rule_ids=("product.forbidden-call",),
    )

    written = composition.materialize(tmp_path / "out")

    assert not any("product" in path.name for path in written)
    assert _materialized_rule_ids(written) == list(composition.rule_ids)


def test_materialize_refuses_a_non_empty_destination(tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "stale.yml").write_text("rules: []\n", encoding="utf-8")

    with pytest.raises(RulepackCompositionError, match="not empty"):
        _compose(languages=("python",)).materialize(tmp_path / "out")


def test_materialize_refuses_a_source_that_changed(tmp_path: Path) -> None:
    product = _product_rule(tmp_path / "product.yml", "product.forbidden-call")
    composition = _compose(languages=("python",), product_configs=(product,))
    _product_rule(product, "product.swapped-after-compose")

    with pytest.raises(RulepackCompositionError, match="changed after"):
        composition.materialize(tmp_path / "out")


@_needs_semgrep
def test_an_excluded_rule_does_not_run_from_the_materialized_config(
    tmp_path: Path,
) -> None:
    assert _SEMGREP is not None
    excluded = "l9.python.portable.datetime-utcnow"
    composition = _compose(
        languages=("python",), include_candidates=True, excluded_rule_ids=(excluded,)
    )
    config = tmp_path / "config"
    composition.materialize(config)
    source = tmp_path / "scan"
    source.mkdir()
    shutil.copy2(
        PACK_FIXTURES / "python-portable" / "l9-python-portable.py", source / "a.py"
    )
    (source / ".semgrepignore").write_text("", encoding="utf-8")

    proc = subprocess.run(
        [
            _SEMGREP,
            "scan",
            "--metrics=off",
            "--quiet",
            "--json",
            "--config",
            str(config),
            ".",
        ],
        cwd=source,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert proc.returncode in (0, 1), proc.stderr
    found = {result["check_id"] for result in json.loads(proc.stdout)["results"]}
    assert found, "the scan produced no finding at all"
    assert not any(check.endswith(excluded) for check in found)
    assert any(check.endswith("singleton-init-without-lock") for check in found)


def test_cli_compose_materializes_on_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "config"
    monkeypatch.setattr(
        "sys.argv",
        [
            "l9-ci",
            "semgrep",
            "compose",
            "--language",
            "python",
            "--materialize",
            str(out),
            "--format",
            "json",
        ],
    )

    assert main() == 0

    result = json.loads(capsys.readouterr().out)["result"]
    assert result["materialized"] == sorted(path.name for path in out.iterdir())
    assert result["materialized"]
