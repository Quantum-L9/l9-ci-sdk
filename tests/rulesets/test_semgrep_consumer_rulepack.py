"""Witnesses for the scoped consumer rulepack declaration (ADR 0021).

A consumer declares its own Semgrep rules in ``.l9/semgrep-consumer-rules.yaml``.
These tests pin decision 2: the SDK validates every rule before anything
runs, and any violation fails the consumer declaration, never a central run.
They need no ``semgrep`` executable; the real-Semgrep witnesses are in
tests/commands/test_semgrep_consumer_run_e2e.py.
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from l9_ci.rulesets.semgrep.consumer import (
    CONSUMER_DECLARATION_PATH,
    ConsumerRule,
    ConsumerRulepackError,
    consumer_canonical_prefix,
    consumer_target_name,
    load_consumer_declaration,
    packaged_rule_ids,
)

OWNER = "Quantum-L9/Cursor-Governance"


def _rule(**overrides: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "id": "l9.memory-boundary-no-shell",
        "languages": ["python"],
        "message": "no shell string spawn",
        "severity": "ERROR",
        "pattern": "forbidden_call(...)",
        "paths": {"include": ["ops/memory/"], "exclude": ["**/test_*.py"]},
        "metadata": {
            "l9": {"canonical_rule_id": "CONSUMER-CURSOR-GOVERNANCE-NO-SHELL"}
        },
    }
    rule.update(overrides)
    return rule


def _repository(
    root: Path,
    rules: list[dict[str, Any]] | None = None,
    *,
    declaration: dict[str, Any] | None = None,
    rule_file: str = ".semgrep/l9-pr.yml",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".semgrep").mkdir(exist_ok=True)
    (root / rule_file).parent.mkdir(parents=True, exist_ok=True)
    (root / rule_file).write_text(
        yaml.safe_dump({"rules": rules if rules is not None else [_rule()]}),
        encoding="utf-8",
    )
    (root / ".l9").mkdir(exist_ok=True)
    document = declaration or {
        "schema": "l9.semgrep-consumer-rulepack/v1",
        "owner": OWNER,
        "rule_files": [rule_file],
    }
    (root / CONSUMER_DECLARATION_PATH).write_text(
        yaml.safe_dump(document), encoding="utf-8"
    )
    return root


def test_no_declaration_is_none(tmp_path: Path) -> None:
    assert load_consumer_declaration(tmp_path) is None


def test_valid_declaration_loads_with_digests(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    declaration = load_consumer_declaration(root)
    assert declaration is not None
    assert declaration.owner == OWNER
    assert declaration.target_name == "quantum-l9.cursor-governance"
    (rule_file,) = declaration.rule_files
    assert rule_file.path == ".semgrep/l9-pr.yml"
    assert rule_file.rule_ids == ("l9.memory-boundary-no-shell",)
    assert len(rule_file.sha256) == 64 and len(declaration.sha256) == 64
    assert declaration.config_paths(root) == (root / ".semgrep/l9-pr.yml",)


def test_consumer_evidence_is_schema_valid(tmp_path: Path) -> None:
    declaration = load_consumer_declaration(_repository(tmp_path / "repo"))
    assert declaration is not None
    record = declaration.to_evidence()
    record["analysis_budget"] = {
        "timeout_seconds": 30,
        "timeout_threshold": 0,
        "on_timeout": "incomplete",
    }
    schema = files("l9_ci").joinpath(
        "schemas", "v1", "semgrep-consumer-rulepack-evidence.schema.json"
    )
    validator = Draft202012Validator(json.loads(schema.read_text(encoding="utf-8")))
    assert sorted(validator.iter_errors(record), key=str) == []
    assert record["nosem"] == "honored"


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        # Decision 2: a rule with no path scope cannot claim the whole tree.
        ([_rule(paths=None)], "must declare paths"),
        ([{k: v for k, v in _rule().items() if k != "paths"}], "must declare paths"),
        ([_rule(paths={"exclude": ["x/"]})], "paths.include must be a list"),
        ([_rule(paths={"include": []})], "paths.include must not be empty"),
        (
            [_rule(paths={"include": ["a/"], "skip": ["b/"]})],
            "only include and exclude",
        ),
        # Namespacing: consumer prefix, never a packaged SDK rule.
        ([_rule(id="other.rule")], "not namespaced under 'l9.'"),
        # Identity: only the consumer canonical namespace.
        ([_rule(metadata={})], "canonical_rule_id starting"),
        (
            [_rule(metadata={"l9": {"canonical_rule_id": "L9-PYTHON-EXEC-EVAL-USE"}})],
            "canonical_rule_id starting",
        ),
        (
            [
                _rule(
                    metadata={
                        "l9": {"canonical_rule_id": "CONSUMER-OTHER-REPO-NO-SHELL"}
                    }
                )
            ],
            "canonical_rule_id starting",
        ),
        (
            [
                _rule(
                    metadata={
                        "l9": {"canonical_rule_id": "CONSUMER-CURSOR-GOVERNANCE-"}
                    }
                )
            ],
            "is malformed",
        ),
        # Allow-list: per-rule keys only.
        ([_rule(**{"min-version": "1.0.0"})], "outside the allow-list"),
        ([_rule(languages=[])], "languages must not be empty"),
        ([], "non-empty 'rules' list"),
        (
            [
                _rule(),
                _rule(
                    metadata={
                        "l9": {"canonical_rule_id": "CONSUMER-CURSOR-GOVERNANCE-B"}
                    }
                ),
            ],
            "is defined in both",
        ),
        (
            [_rule(), _rule(id="l9.second")],
            "is used by both",
        ),
    ],
)
def test_known_bad_rules_are_refused(
    tmp_path: Path, rules: list[dict[str, Any]], message: str
) -> None:
    root = _repository(tmp_path / "repo", rules)
    with pytest.raises(ConsumerRulepackError, match=message):
        load_consumer_declaration(root)


def test_a_packaged_sdk_rule_id_cannot_be_redefined(tmp_path: Path) -> None:
    packaged = sorted(i for i in packaged_rule_ids() if i.startswith("l9."))
    assert packaged, "the SDK packages l9.-namespaced rules"
    root = _repository(tmp_path / "repo", [_rule(id=packaged[0])])
    with pytest.raises(ConsumerRulepackError, match="redefines an SDK packaged rule"):
        load_consumer_declaration(root)


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        (
            {"schema": "other/v1", "owner": OWNER, "rule_files": ["r.yml"]},
            "schema must be",
        ),
        (
            {
                "schema": "l9.semgrep-consumer-rulepack/v1",
                "owner": "no-slash",
                "rule_files": ["r.yml"],
            },
            "owner must be",
        ),
        (
            {
                "schema": "l9.semgrep-consumer-rulepack/v1",
                "owner": OWNER,
                "rule_files": ["../outside.yml"],
            },
            "normalized repository-relative",
        ),
        (
            {
                "schema": "l9.semgrep-consumer-rulepack/v1",
                "owner": OWNER,
                "rule_files": ["missing.yml"],
            },
            "not a regular file",
        ),
        (
            {
                "schema": "l9.semgrep-consumer-rulepack/v1",
                "owner": OWNER,
                "rule_files": [],
            },
            "between 1 and",
        ),
        (
            {
                "schema": "l9.semgrep-consumer-rulepack/v1",
                "owner": OWNER,
                "rule_files": ["r.yml"],
                "include_all": True,
            },
            "unknown keys",
        ),
    ],
)
def test_known_bad_declarations_are_refused(
    tmp_path: Path, declaration: dict[str, Any], message: str
) -> None:
    root = _repository(tmp_path / "repo", declaration=declaration, rule_file="r.yml")
    with pytest.raises(ConsumerRulepackError, match=message):
        load_consumer_declaration(root)


def test_a_rule_file_holds_only_rules(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    path = root / ".semgrep/l9-pr.yml"
    path.write_text(
        yaml.safe_dump({"rules": [_rule()], "options": {"max_target_bytes": 1}}),
        encoding="utf-8",
    )
    with pytest.raises(ConsumerRulepackError, match="exactly one key"):
        load_consumer_declaration(root)


def test_a_symlinked_rule_file_is_refused(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    outside = tmp_path / "outside.yml"
    outside.write_text(yaml.safe_dump({"rules": [_rule()]}), encoding="utf-8")
    target = root / ".semgrep/l9-pr.yml"
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(ConsumerRulepackError, match="not a regular file"):
        load_consumer_declaration(root)


# --- path matching, against Cursor-Governance's own pattern shapes ---------


def _scoped(include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> ConsumerRule:
    return ConsumerRule(
        rule_id="l9.x",
        canonical_rule_id="CONSUMER-X-Y",
        languages=("python",),
        include=include,
        exclude=exclude,
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("ops/memory/cli.py", True),
        ("ops/memory/sub/deep.py", True),
        ("ops/memory/test_cli.py", False),  # **/test_*.py
        ("ops/memory/hosted_hook_transport.py", False),  # an exact exclusion
        ("ops/graphiti/hydration/close_session.py", True),  # an exact file
        ("ops/graphiti/hydration/other.py", False),
        ("x/ops/memory/cli.py", False),  # an inner slash anchors at the root
        ("ops/memory/README.md", False),  # python rules analyze .py/.pyi only
        ("ops/memoryx/cli.py", False),  # a directory matches whole
    ],
)
def test_paths_match_like_semgrep_include_and_exclude(
    path: str, expected: bool
) -> None:
    rule = _scoped(
        ("ops/memory/", "ops/graphiti/hydration/close_session.py"),
        ("**/test_*.py", "ops/memory/hosted_hook_transport.py"),
    )
    assert rule.matches(path) is expected


def test_unanchored_patterns_match_at_any_depth() -> None:
    rule = _scoped(("*.py",))
    assert rule.matches("a.py") and rule.matches("deep/dir/a.py")
    assert not _scoped(("/top.py",)).matches("sub/top.py")


def test_naming_helpers() -> None:
    assert consumer_canonical_prefix(OWNER) == "CONSUMER-CURSOR-GOVERNANCE-"
    assert consumer_target_name(OWNER) == "quantum-l9.cursor-governance"
