"""Capability inventory over the seven repository shapes.

Each test builds one tree and asserts the whole shape of the answer, not just
its status, because the failure this inventory exists to prevent is a correct
status reached by dropping a fact: a second language, a malformed manifest, an
unsupported language.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pytest

from l9_ci.__main__ import main
from l9_ci.artifacts import canonical_json_bytes
from l9_ci.capabilities import (
    CAPABILITY_INVENTORY_PROTOCOL,
    AnalysisTarget,
    CapabilityInventory,
    CapabilityState,
    build_capability_inventory,
    validate_capability_inventory,
)
from l9_ci.commands.providers import default_analysis_targets

from . import trees


def _inventory(
    tmp_path: Path,
    tree: Mapping[str, str],
    **target_options: object,
) -> CapabilityInventory:
    trees.materialize(tmp_path, tree)
    inventory = trees.inventory(
        tmp_path,
        trees.semgrep_targets(**target_options),  # type: ignore[arg-type]
    )
    validate_capability_inventory(inventory.to_dict())
    return inventory


def _languages(inventory: CapabilityInventory) -> dict[str, CapabilityState]:
    return {item.language: item.state for item in inventory.languages}


def _prerequisites(inventory: CapabilityInventory) -> dict[str, CapabilityState]:
    return {item.target: item.state for item in inventory.provider_prerequisites}


def test_python_only(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, trees.PYTHON_ONLY)

    assert inventory.status is CapabilityState.APPLICABLE
    assert _languages(inventory) == {"python": CapabilityState.APPLICABLE}
    assert _prerequisites(inventory) == {
        "language:python": CapabilityState.APPLICABLE,
        "language:typescript": CapabilityState.NOT_APPLICABLE,
    }
    assert inventory.package_managers == ("python",)
    assert inventory.examined_file_count == 4
    assert inventory.unclassified_file_count == 2


def test_typescript_only(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, trees.TYPESCRIPT_ONLY)

    assert inventory.status is CapabilityState.APPLICABLE
    assert _languages(inventory) == {"typescript": CapabilityState.APPLICABLE}
    assert _prerequisites(inventory) == {
        "language:python": CapabilityState.NOT_APPLICABLE,
        "language:typescript": CapabilityState.APPLICABLE,
    }
    assert inventory.package_managers == ("node",)


def test_mixed_selects_every_supported_language(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, trees.MIXED)

    assert inventory.status is CapabilityState.APPLICABLE
    assert _languages(inventory) == {
        "python": CapabilityState.APPLICABLE,
        "typescript": CapabilityState.APPLICABLE,
    }
    assert _prerequisites(inventory) == {
        "language:python": CapabilityState.APPLICABLE,
        "language:typescript": CapabilityState.APPLICABLE,
    }
    counts = {item.target: item.file_count for item in inventory.provider_prerequisites}
    assert counts == {"language:python": 2, "language:typescript": 1}
    assert inventory.package_managers == ("node", "python")


def test_odoo_recognizes_python_and_xml(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, trees.ODOO_PYTHON_XML)

    (odoo,) = inventory.frameworks
    assert odoo.framework == "odoo"
    assert odoo.state is CapabilityState.APPLICABLE
    assert odoo.languages == ("python", "xml")
    # Only files inside the addon count: tools/release.py and docs/diagram.xml
    # are in the repository but are not Odoo source.
    assert dict(odoo.language_file_counts) == {"python": 4, "xml": 1}
    assert odoo.evidence_paths == ("addons/stock_ext/__manifest__.py",)
    # No target consumes XML in this SDK build, so XML is present and named
    # unsupported rather than missing from the record.
    assert _languages(inventory) == {
        "python": CapabilityState.APPLICABLE,
        "xml": CapabilityState.UNSUPPORTED,
    }
    assert inventory.status is CapabilityState.APPLICABLE
    assert any("language xml" in reason for reason in inventory.reasons)


def test_odoo_framework_target_serves_xml_only_inside_odoo(tmp_path: Path) -> None:
    odoo_target = AnalysisTarget(
        provider_id="semgrep",
        scope="framework",
        name="odoo",
        languages=("python", "xml"),
        rulepack="example/odoo",
        rulepack_resolved=True,
    )
    targets = (*trees.semgrep_targets(), odoo_target)

    trees.materialize(tmp_path / "odoo", trees.ODOO_PYTHON_XML)
    inside = trees.inventory(tmp_path / "odoo", targets)
    assert _prerequisites(inside)["framework:odoo"] is CapabilityState.APPLICABLE
    assert _languages(inside)["xml"] is CapabilityState.APPLICABLE

    trees.materialize(tmp_path / "plain", {**trees.PYTHON_ONLY, "a.xml": "<a/>\n"})
    outside = trees.inventory(tmp_path / "plain", targets)
    assert _prerequisites(outside)["framework:odoo"] is CapabilityState.NOT_APPLICABLE
    assert _languages(outside)["xml"] is CapabilityState.UNSUPPORTED


def test_no_supported_code_is_not_applicable_with_evidence(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, trees.NO_SUPPORTED_CODE)

    assert inventory.status is CapabilityState.NOT_APPLICABLE
    assert inventory.languages == ()
    assert inventory.examined_file_count == 3
    assert inventory.reasons == (
        "no source file in a recognized language among 3 examined file(s)",
    )
    for prerequisite in inventory.provider_prerequisites:
        assert prerequisite.state is CapabilityState.NOT_APPLICABLE
        assert "3 examined file(s)" in prerequisite.reason


def test_malformed_manifest_fails_and_keeps_the_languages(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, trees.MALFORMED_MANIFEST)

    assert inventory.status is CapabilityState.FAILED
    failed = {
        item.path: item.reason
        for item in inventory.manifests
        if item.state is CapabilityState.FAILED
    }
    assert sorted(failed) == ["pyproject.toml", "web/package.json"]
    assert all("malformed" in reason for reason in failed.values())
    # A failed manifest hides nothing: both languages are still inventoried.
    assert _languages(inventory) == {
        "python": CapabilityState.APPLICABLE,
        "typescript": CapabilityState.APPLICABLE,
    }
    assert len(inventory.reasons) == 2


def test_malformed_odoo_manifest_fails_the_framework(tmp_path: Path) -> None:
    tree = {
        **trees.ODOO_PYTHON_XML,
        "addons/broken/__manifest__.py": "{'name': 'Broken',\n",
    }
    inventory = _inventory(tmp_path, tree)

    (odoo,) = inventory.frameworks
    assert odoo.state is CapabilityState.FAILED
    assert odoo.evidence_count == 2
    assert inventory.status is CapabilityState.FAILED


def test_unsupported_language_is_visible_and_not_not_applicable(
    tmp_path: Path,
) -> None:
    inventory = _inventory(tmp_path, trees.UNSUPPORTED_LANGUAGE)

    assert inventory.status is CapabilityState.UNSUPPORTED
    assert _languages(inventory) == {"kotlin": CapabilityState.UNSUPPORTED}
    assert inventory.languages[0].file_count == 2
    assert inventory.package_managers == ("gradle",)


def test_unsupported_language_beside_supported_code_stays_listed(
    tmp_path: Path,
) -> None:
    inventory = _inventory(
        tmp_path, {**trees.PYTHON_ONLY, "cmd/main.go": "package x\n"}
    )

    assert inventory.status is CapabilityState.APPLICABLE
    assert _languages(inventory)["go"] is CapabilityState.UNSUPPORTED
    assert any("language go" in reason for reason in inventory.reasons)


def test_missing_executable_is_incomplete_not_applicable(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, trees.MIXED, executable="missing")

    assert inventory.status is CapabilityState.INCOMPLETE
    assert set(_prerequisites(inventory).values()) == {CapabilityState.INCOMPLETE}


def test_missing_executable_does_not_touch_a_not_applicable_target(
    tmp_path: Path,
) -> None:
    inventory = _inventory(tmp_path, trees.PYTHON_ONLY, executable="missing")

    assert _prerequisites(inventory) == {
        "language:python": CapabilityState.INCOMPLETE,
        "language:typescript": CapabilityState.NOT_APPLICABLE,
    }


def test_unresolved_rulepack_fails(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, trees.PYTHON_ONLY, resolved=False)

    assert inventory.status is CapabilityState.FAILED
    assert _prerequisites(inventory)["language:python"] is CapabilityState.FAILED


def test_no_declared_target_makes_code_unsupported_never_absent(
    tmp_path: Path,
) -> None:
    trees.materialize(tmp_path, trees.PYTHON_ONLY)
    inventory = trees.inventory(tmp_path, ())

    assert inventory.status is CapabilityState.UNSUPPORTED
    assert _languages(inventory) == {"python": CapabilityState.UNSUPPORTED}


@pytest.mark.parametrize(
    "tree",
    [
        trees.PYTHON_ONLY,
        trees.TYPESCRIPT_ONLY,
        trees.MIXED,
        trees.ODOO_PYTHON_XML,
        trees.NO_SUPPORTED_CODE,
        trees.MALFORMED_MANIFEST,
        trees.UNSUPPORTED_LANGUAGE,
    ],
)
def test_inventory_is_deterministic_and_schema_valid(
    tmp_path: Path,
    tree: Mapping[str, str],
) -> None:
    trees.materialize(tmp_path / "a", tree)
    trees.materialize(tmp_path / "b", dict(reversed(list(tree.items()))))

    first = trees.inventory(tmp_path / "a", trees.semgrep_targets())
    second = trees.inventory(tmp_path / "b", trees.semgrep_targets())

    assert canonical_json_bytes(first.to_dict()) == canonical_json_bytes(
        second.to_dict()
    )
    payload = first.to_dict()
    assert payload["schema"] == CAPABILITY_INVENTORY_PROTOCOL
    validate_capability_inventory(payload)
    assert "verdict" not in payload
    assert str(tmp_path) not in json.dumps(payload)


def test_validation_rejects_a_status_its_entries_do_not_support(
    tmp_path: Path,
) -> None:
    payload = _inventory(tmp_path, trees.MALFORMED_MANIFEST).to_dict()
    payload["status"] = "applicable"

    with pytest.raises(ValueError, match="inconsistent"):
        validate_capability_inventory(payload)


def test_validation_rejects_an_unknown_field(tmp_path: Path) -> None:
    payload = _inventory(tmp_path, trees.PYTHON_ONLY).to_dict()
    payload["verdict"] = "pass"

    with pytest.raises(ValueError, match="verdict"):
        validate_capability_inventory(payload)


def test_analysis_target_rejects_unknown_scope_and_executable_state() -> None:
    with pytest.raises(ValueError, match="scope"):
        AnalysisTarget("semgrep", "product", "x", ("python",), None, True)
    with pytest.raises(ValueError, match="executable"):
        AnalysisTarget("semgrep", "language", "x", ("python",), None, True, "maybe")


def test_default_targets_cover_every_packaged_language(tmp_path: Path) -> None:
    targets = default_analysis_targets(tmp_path)

    assert [target.target for target in targets] == [
        "language:python",
        "language:typescript",
    ]
    assert all(target.rulepack_resolved for target in targets)
    assert {target.executable for target in targets} == {"not_probed"}
    by_name = {target.name: target for target in targets}
    assert by_name["python"].languages == ("python",)
    assert by_name["typescript"].languages == ("typescript", "javascript")
    assert ".mts" not in by_name["typescript"].suffixes
    assert ".cts" not in by_name["typescript"].suffixes


def _default(tmp_path: Path, tree: Mapping[str, str]) -> CapabilityInventory:
    trees.materialize(tmp_path, tree)
    inventory = build_capability_inventory(
        tmp_path,
        targets=default_analysis_targets(tmp_path),
        SDK_version=trees.SDK_VERSION,
    )
    validate_capability_inventory(inventory.to_dict())
    return inventory


def test_javascript_only_is_analyzed_by_the_typescript_pack(tmp_path: Path) -> None:
    inventory = _default(tmp_path, trees.JAVASCRIPT_ONLY)

    assert inventory.status is CapabilityState.APPLICABLE
    assert _languages(inventory) == {"javascript": CapabilityState.APPLICABLE}
    (javascript,) = inventory.languages
    assert javascript.file_count == 4
    assert javascript.unanalyzed_file_count == 0
    prerequisites = {item.target: item for item in inventory.provider_prerequisites}
    assert prerequisites["language:typescript"].state is CapabilityState.APPLICABLE
    assert prerequisites["language:typescript"].file_count == 4
    assert prerequisites["language:typescript"].rulepack == (
        "l9_ci/rulesets/semgrep/typescript"
    )
    assert prerequisites["language:python"].state is CapabilityState.NOT_APPLICABLE


def test_mixed_typescript_and_javascript_is_one_target(tmp_path: Path) -> None:
    inventory = _default(
        tmp_path, {**trees.TYPESCRIPT_ONLY, "scripts/build.js": "module.exports = 1;\n"}
    )

    assert _languages(inventory) == {
        "javascript": CapabilityState.APPLICABLE,
        "typescript": CapabilityState.APPLICABLE,
    }
    counts = {item.target: item.file_count for item in inventory.provider_prerequisites}
    assert counts == {"language:python": 0, "language:typescript": 3}


def test_unscanned_typescript_suffixes_are_not_counted_as_covered(
    tmp_path: Path,
) -> None:
    inventory = _default(tmp_path, trees.TYPESCRIPT_UNSCANNED_SUFFIXES)

    (typescript,) = inventory.languages
    assert typescript.state is CapabilityState.APPLICABLE
    assert typescript.file_count == 3
    assert typescript.unanalyzed_file_count == 2
    assert ".cts" in typescript.reason and ".mts" in typescript.reason
    prerequisites = {item.target: item for item in inventory.provider_prerequisites}
    assert prerequisites["language:typescript"].file_count == 1
    assert any(
        reason.startswith("language typescript:") for reason in inventory.reasons
    )


def test_only_unscanned_suffixes_leave_the_language_unsupported(
    tmp_path: Path,
) -> None:
    inventory = _default(tmp_path, {"src/worker.mts": "export const w = 1;\n"})

    assert _languages(inventory) == {"typescript": CapabilityState.UNSUPPORTED}
    assert inventory.status is CapabilityState.UNSUPPORTED
    prerequisites = {item.target: item for item in inventory.provider_prerequisites}
    assert prerequisites["language:typescript"].state is CapabilityState.NOT_APPLICABLE


def test_framework_scope_counts_unanalyzed_files_per_language(
    tmp_path: Path,
) -> None:
    tree = {
        **trees.ODOO_PYTHON_XML,
    }
    odoo_target = AnalysisTarget(
        provider_id="semgrep",
        scope="framework",
        name="odoo",
        languages=("python", "xml"),
        rulepack="example/odoo",
        rulepack_resolved=True,
    )
    trees.materialize(tmp_path, tree)

    inventory = trees.inventory(tmp_path, (*trees.semgrep_targets(), odoo_target))

    xml = next(item for item in inventory.languages if item.language == "xml")
    # odoo19 view inside the addon is analyzed; docs/diagram.xml is not.
    assert xml.state is CapabilityState.APPLICABLE
    assert xml.file_count == 2
    assert xml.unanalyzed_file_count == 1


@pytest.mark.parametrize("suffix", ["ts", ".TS", "."])
def test_analysis_target_rejects_a_malformed_suffix(suffix: str) -> None:
    with pytest.raises(ValueError, match="suffix"):
        AnalysisTarget(
            "semgrep", "language", "x", ("python",), None, True, suffixes=(suffix,)
        )


def test_two_targets_with_one_name_are_refused(tmp_path: Path) -> None:
    trees.materialize(tmp_path, trees.PYTHON_ONLY)
    target = trees.semgrep_targets()[0]

    with pytest.raises(ValueError, match="share"):
        build_capability_inventory(
            tmp_path, targets=(target, target), SDK_version=trees.SDK_VERSION
        )


def test_cli_emits_the_inventory_and_writes_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = trees.materialize(tmp_path / "repo", trees.MIXED)
    output = tmp_path / "out" / "capability-inventory.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "l9-ci",
            "providers",
            "inventory",
            "--root",
            str(root),
            "--output",
            str(output),
            "--format",
            "json",
        ],
    )

    assert main() == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["ok"] is True
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written == printed["result"]
    validate_capability_inventory(written)
    assert written["status"] == "applicable"
    assert [item["target"] for item in written["provider_prerequisites"]] == [
        "language:python",
        "language:typescript",
    ]


def test_cli_reports_a_failed_inventory_as_a_record_not_a_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = trees.materialize(tmp_path / "repo", trees.MALFORMED_MANIFEST)
    monkeypatch.setattr(
        "sys.argv",
        ["l9-ci", "providers", "inventory", "--root", str(root), "--format", "json"],
    )

    assert main() == 0
    assert json.loads(capsys.readouterr().out)["result"]["status"] == "failed"


def test_inventory_carries_the_producing_sdk_version(tmp_path: Path) -> None:
    payload = _inventory(tmp_path, trees.PYTHON_ONLY).to_dict()

    assert payload["SDK_version"] == trees.SDK_VERSION
    del payload["SDK_version"]
    with pytest.raises(ValueError, match="SDK_version"):
        validate_capability_inventory(payload)


@pytest.mark.parametrize("version", ["", "   "])
def test_sdk_version_is_required_and_never_guessed(
    tmp_path: Path, version: str
) -> None:
    trees.materialize(tmp_path, trees.PYTHON_ONLY)

    with pytest.raises(ValueError, match="SDK_version"):
        build_capability_inventory(
            tmp_path, targets=trees.semgrep_targets(), SDK_version=version
        )


def test_manifest_content_is_bound_when_the_snapshot_id_is_not(tmp_path: Path) -> None:
    # Same paths, different manifest bytes: the snapshot identity covers which
    # paths exist, so it does not move. The manifest digest must.
    trees.materialize(tmp_path, trees.PYTHON_ONLY)
    valid = trees.inventory(tmp_path, trees.semgrep_targets())
    (tmp_path / "pyproject.toml").write_text("[project\nname = \n", encoding="utf-8")
    broken = trees.inventory(tmp_path, trees.semgrep_targets())

    assert valid.snapshot_id == broken.snapshot_id
    assert valid.status is CapabilityState.APPLICABLE
    assert broken.status is CapabilityState.FAILED
    (before,) = (item for item in valid.manifests if item.path == "pyproject.toml")
    (after,) = (item for item in broken.manifests if item.path == "pyproject.toml")
    assert before.sha256 and after.sha256
    assert before.sha256 != after.sha256
    assert canonical_json_bytes(valid.to_dict()) != canonical_json_bytes(
        broken.to_dict()
    )


def test_undecodable_manifest_fails_and_keeps_its_digest(tmp_path: Path) -> None:
    trees.materialize(tmp_path, trees.PYTHON_ONLY)
    (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe not utf-8")

    inventory = trees.inventory(tmp_path, trees.semgrep_targets())

    (manifest,) = (
        item for item in inventory.manifests if item.path == "pyproject.toml"
    )
    assert manifest.state is CapabilityState.FAILED
    assert manifest.sha256 is not None
    assert "could not be read" in manifest.reason


def test_framework_target_does_not_serve_a_language_outside_the_framework(
    tmp_path: Path,
) -> None:
    # The addon holds Python only. The repository's one XML file is outside
    # it, so an Odoo target will not analyze that file and XML stays unsupported.
    tree = {
        "addons/stock_ext/__manifest__.py": '{"name": "Stock Ext"}\n',
        "addons/stock_ext/models/stock.py": "x = 1\n",
        "docs/diagram.xml": "<diagram/>\n",
    }
    odoo_target = AnalysisTarget(
        provider_id="semgrep",
        scope="framework",
        name="odoo",
        languages=("python", "xml"),
        rulepack="example/odoo",
        rulepack_resolved=True,
    )
    trees.materialize(tmp_path, tree)

    inventory = trees.inventory(tmp_path, (*trees.semgrep_targets(), odoo_target))

    assert _prerequisites(inventory)["framework:odoo"] is CapabilityState.APPLICABLE
    assert _languages(inventory)["xml"] is CapabilityState.UNSUPPORTED
    assert any("language xml" in reason for reason in inventory.reasons)
