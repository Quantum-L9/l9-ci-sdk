"""Witnesses for superseded registry rules (rule-overlaps.yaml, CTO 2026-11-21).

Cursor-Governance run 44848823829 reported each shell=True call site twice:
once by l9.baseline.python.subprocess-shell-true and once by the registry rule
python.lang.security.audit.subprocess-shell-true. A run that composes both
rulesets now reports a site once, under its L9 canonical ID: both rules run, and
the registry finding is withdrawn only where the L9 rule reported the same call.
A registry finding no L9 finding covers stays, so a later revision of the
unpinned registry rule cannot hide a site (Codex review on #143). The
real-Semgrep tests below check the supersession on every shell=True form.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.commands.semgrep import _active_rule_overlaps, _build_run_config_arguments
from l9_ci.pipeline import SemgrepPipelineRequest, run_semgrep_pipeline
from l9_ci.rulesets.semgrep import ruleset_dir
from l9_ci.rulesets.semgrep.overlaps import (
    RuleOverlapError,
    load_rule_overlaps,
    packaged_rule_overlaps,
)
from tests.commands.test_semgrep_command import _build_run_namespace

REGISTRY_RULE = "python.lang.security.audit.subprocess-shell-true.subprocess-shell-true"
L9_RULE = "l9.baseline.python.subprocess-shell-true"
# Deliberate shell=True calls: named .pyfixture so that bandit and CodeQL do
# not read them as product code (the convention of l9-file-permissions); passed
# to Semgrep as a .py copy in a temporary directory.
FORMS = Path("tests/fixtures/semgrep/rules/overlaps/shell_true_forms.pyfixture")

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


def test_supersession_applies_only_when_both_rulesets_compose() -> None:
    standard = _build_run_namespace(output="b.json")
    active = _active_rule_overlaps(standard)
    assert len(active) == 1
    assert active[0].supersedes == (REGISTRY_RULE,)
    for namespace in (
        _build_run_namespace(output="b.json", profile="l9-baseline"),
        _build_run_namespace(output="b.json", no_registry_config=True),
    ):
        assert _active_rule_overlaps(namespace) == ()


def test_no_rule_is_excluded_before_the_scan() -> None:
    """The unpinned registry rule always runs; nothing is excluded up front."""
    arguments = _build_run_config_arguments(_build_run_namespace(output="b.json"))
    assert "--exclude-rule" not in arguments


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


def _scan(tmp_path: Path, *arguments: str) -> list[dict]:
    target = tmp_path / "shell_true_forms.py"
    target.write_text(FORMS.read_text(encoding="utf-8"), encoding="utf-8")
    completed = subprocess.run(
        ["semgrep", "scan", "--metrics=off", "--json", *arguments, "--", str(target)],
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
def test_the_l9_rule_matches_every_site_the_registry_rule_matches(
    tmp_path: Path,
) -> None:
    l9 = _spans(_scan(tmp_path, "--config", str(ruleset_dir("python"))), L9_RULE)
    registry = _spans(_scan(tmp_path, "--config", f"r/{REGISTRY_RULE}"), REGISTRY_RULE)
    assert registry, "the registry rule must match the fixture"
    for start, end in registry:
        assert any(a <= start and end <= b for a, b in l9), (start, end)
    # The L9 rule also reports the literal-string command the registry skips.
    assert len(l9) == len(registry) + 1


def _composed_report(tmp_path: Path) -> Path:
    target = tmp_path / "repo" / "shell_true_forms.py"
    target.parent.mkdir(parents=True)
    target.write_text(FORMS.read_text(encoding="utf-8"), encoding="utf-8")
    completed = subprocess.run(
        [
            "semgrep",
            "scan",
            "--metrics=off",
            "--json",
            "--config",
            f"r/{REGISTRY_RULE}",
            "--config",
            str(ruleset_dir("python")),
            "--",
            "shell_true_forms.py",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=target.parent,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    report = tmp_path / "report.json"
    report.write_text(completed.stdout, encoding="utf-8")
    return report


def _bundle(tmp_path: Path, report: Path):  # type: ignore[no-untyped-def]
    output = tmp_path / "bundle.json"
    run_semgrep_pipeline(
        SemgrepPipelineRequest(
            report_path=report,
            repository_root=(tmp_path / "repo").resolve(),
            snapshot_id="snapshot-1",
            SDK_version="2.0.0-test",
            output_path=output,
            provider_version="1.171.0",
            generated_at="2026-11-21T00:00:00Z",
            superseded_rules=packaged_rule_overlaps().supersessions("python"),
        )
    )
    return load_and_validate_bundle(output)


@_needs_semgrep
def test_the_composed_run_reports_each_site_once(tmp_path: Path) -> None:
    report = _composed_report(tmp_path)
    results = json.loads(report.read_text(encoding="utf-8"))["results"]
    registry = _spans(results, REGISTRY_RULE)
    assert len(registry) == 6  # both rules ran: nothing was excluded
    bundle = _bundle(tmp_path, report)
    rules = [finding.provider_rule_id for finding in bundle.findings]
    assert all(rule.endswith(L9_RULE) for rule in rules)
    assert len(rules) == 7
    # The withdrawn registry results stay as evidence, and the bundle says so.
    assert len(bundle.evidence) == 7 + len(registry)
    (note,) = [i for i in bundle.limitations if i.startswith("registry rule")]
    assert f"{len(registry)} finding(s) withdrawn" in note


@_needs_semgrep
def test_a_registry_finding_no_l9_finding_covers_stays(tmp_path: Path) -> None:
    """Known-bad drift: the registry rule reports a site the L9 rule does not.

    The report is the real composed report with one registry result moved to a
    line no L9 finding spans, standing in for a later revision of the unpinned
    registry rule that matches more than the packaged L9 rule.
    """
    report = _composed_report(tmp_path)
    document = json.loads(report.read_text(encoding="utf-8"))
    drifted = next(
        dict(item) for item in document["results"] if item["check_id"] == REGISTRY_RULE
    )
    drifted["start"] = {**drifted["start"], "line": 1}
    drifted["end"] = {**drifted["end"], "line": 1}
    document["results"].append(drifted)
    report.write_text(json.dumps(document), encoding="utf-8")
    bundle = _bundle(tmp_path, report)
    kept = [f for f in bundle.findings if f.provider_rule_id == REGISTRY_RULE]
    assert [f.locations[0].start_line for f in kept] == [1]
