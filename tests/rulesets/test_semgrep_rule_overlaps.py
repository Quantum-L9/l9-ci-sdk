"""Witnesses for superseded registry rules (rule-overlaps.yaml, CTO 2026-11-21).

Cursor-Governance run 44848823829 reported each shell=True call site twice:
once by l9.baseline.python.subprocess-shell-true and once by the registry rule
python.lang.security.audit.subprocess-shell-true. A run that composes both
rulesets now skips the registry rule, so a site is reported once, under its L9
canonical ID. The registry rule may be skipped only because the L9 rule matches
every site it matches. The real-Semgrep tests below check that on every
shell=True form.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from l9_ci.commands.semgrep import _build_run_config_arguments
from l9_ci.rulesets.semgrep import ruleset_dir
from l9_ci.rulesets.semgrep.overlaps import (
    RuleOverlapError,
    load_rule_overlaps,
    packaged_rule_overlaps,
)
from tests.commands.test_semgrep_command import _build_run_namespace

REGISTRY_RULE = "python.lang.security.audit.subprocess-shell-true.subprocess-shell-true"
L9_RULE = "l9.baseline.python.subprocess-shell-true"
FORMS = Path("tests/fixtures/semgrep/rules/overlaps/shell_true_forms.py")

_needs_semgrep = pytest.mark.skipif(
    shutil.which("semgrep") is None and os.environ.get("L9_REQUIRE_SEMGREP") != "1",
    reason="semgrep executable not available on PATH",
)


def _packaged_rules(language: str) -> dict[str, dict]:
    rules: dict[str, dict] = {}
    for path in sorted(ruleset_dir(language).glob("*.yml")):
        for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]:
            rules[rule["id"]] = rule
    return rules


def test_every_superseding_rule_is_packaged_with_its_canonical_id() -> None:
    overlaps = packaged_rule_overlaps()
    assert overlaps.superseded_rule_ids("python") == (REGISTRY_RULE,)
    for item in overlaps.overlaps:
        rule = _packaged_rules(item.language)[item.rule_id]
        assert rule["metadata"]["l9"]["canonical_rule_id"] == item.canonical_rule_id


def test_the_registry_rule_is_skipped_only_when_both_rulesets_compose() -> None:
    standard = _build_run_config_arguments(_build_run_namespace(output="b.json"))
    assert ("--exclude-rule", REGISTRY_RULE) == standard[-2:]
    baseline = _build_run_config_arguments(
        _build_run_namespace(output="b.json", profile="l9-baseline")
    )
    assert "--exclude-rule" not in baseline
    no_registry = _build_run_config_arguments(
        _build_run_namespace(output="b.json", no_registry_config=True)
    )
    assert "--exclude-rule" not in no_registry


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda d: d.update(schema="x/v1"), "schema must be"),
        (lambda d: d["overlaps"][0].update(supersedes=[]), "non-empty list"),
        (
            lambda d: d["overlaps"][0].update(supersedes=["l9.baseline.x"]),
            "only registry",
        ),
        (lambda d: d["overlaps"].append(dict(d["overlaps"][0])), "superseded twice"),
        (lambda d: d["overlaps"][0].pop("reason"), "must carry exactly"),
    ],
)
def test_a_malformed_registry_is_refused(
    tmp_path: Path, mutation, message: str
) -> None:  # type: ignore[no-untyped-def]
    from l9_ci.rulesets.semgrep.overlaps import rule_overlaps_path

    document = yaml.safe_load(rule_overlaps_path().read_text(encoding="utf-8"))
    mutation(document)
    path = tmp_path / "rule-overlaps.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(RuleOverlapError, match=message):
        load_rule_overlaps(path)


def _scan(*arguments: str) -> list[dict]:
    completed = subprocess.run(
        ["semgrep", "scan", "--metrics=off", "--json", *arguments, "--", str(FORMS)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    return json.loads(completed.stdout)["results"]


def _spans(results: list[dict], suffix: str) -> list[tuple[int, int]]:
    return sorted(
        (item["start"]["line"], item["end"]["line"])
        for item in results
        if item["check_id"].endswith(suffix)
    )


@_needs_semgrep
def test_the_l9_rule_matches_every_site_the_registry_rule_matches() -> None:
    l9 = _spans(_scan("--config", str(ruleset_dir("python"))), L9_RULE)
    registry = _spans(_scan("--config", f"r/{REGISTRY_RULE}"), REGISTRY_RULE)
    assert registry, "the registry rule must match the fixture"
    for start, end in registry:
        assert any(a <= start and end <= b for a, b in l9), (start, end)
    # The L9 rule also reports the literal-string command the registry skips.
    assert len(l9) == len(registry) + 1


@_needs_semgrep
def test_the_composed_run_reports_each_site_once() -> None:
    both = _scan(
        "--config",
        f"r/{REGISTRY_RULE}",
        "--config",
        str(ruleset_dir("python")),
        "--exclude-rule",
        REGISTRY_RULE,
    )
    assert _spans(both, REGISTRY_RULE) == []
    assert len(_spans(both, L9_RULE)) == 7
