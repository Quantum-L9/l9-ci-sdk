"""The inventory reports a consumer rulepack declaration as a target (ADR 0021).

``semgrep consumer:<owner>`` is reported only when the caller asks
(``l9-ci providers inventory --consumer-rules``): Core's planner accepts only
``language:`` and ``framework:`` targets today, so an unrequested consumer
target would make it reject every inventory of a declaring repository.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from l9_ci.capabilities import (
    CapabilityState,
    build_capability_inventory,
    validate_capability_inventory,
)
from l9_ci.commands.providers import (
    consumer_analysis_target,
    default_analysis_targets,
)

OWNER = "Quantum-L9/Cursor-Governance"
RULE = {
    "id": "l9.memory-boundary-no-shell",
    "languages": ["python"],
    "message": "m",
    "severity": "ERROR",
    "pattern": "forbidden_call(...)",
    "paths": {"include": ["ops/memory/"], "exclude": ["**/test_*.py"]},
    "metadata": {"l9": {"canonical_rule_id": "CONSUMER-CURSOR-GOVERNANCE-NO-SHELL"}},
}


def _repository(
    root: Path, tree: dict[str, str], rules: list[dict] | None = None
) -> Path:
    for relative, content in tree.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if rules is not None:
        (root / ".semgrep").mkdir(parents=True, exist_ok=True)
        (root / ".semgrep/l9-pr.yml").write_text(
            yaml.safe_dump({"rules": rules}), encoding="utf-8"
        )
        (root / ".l9").mkdir(parents=True, exist_ok=True)
        (root / ".l9/semgrep-consumer-rules.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema": "l9.semgrep-consumer-rulepack/v1",
                    "owner": OWNER,
                    "rule_files": [".semgrep/l9-pr.yml"],
                }
            ),
            encoding="utf-8",
        )
    return root


def _inventory(root: Path):  # type: ignore[no-untyped-def]
    consumer = consumer_analysis_target(root)
    targets = default_analysis_targets(root)
    if consumer is not None:
        targets = (*targets, consumer)
    inventory = build_capability_inventory(root, targets=targets, SDK_version="2.0.0")
    validate_capability_inventory(inventory.to_dict())
    return inventory


def _consumer(inventory):  # type: ignore[no-untyped-def]
    return [
        p for p in inventory.provider_prerequisites if p.target.startswith("consumer:")
    ]


def test_declared_rules_matching_a_tracked_file_are_applicable(tmp_path: Path) -> None:
    root = _repository(
        tmp_path / "repo",
        {
            "ops/memory/cli.py": "x\n",
            "ops/memory/test_cli.py": "x\n",
            "src/a.py": "x\n",
        },
        [RULE],
    )
    (item,) = _consumer(_inventory(root))
    assert item.target == "consumer:quantum-l9.cursor-governance"
    assert item.state is CapabilityState.APPLICABLE
    assert item.file_count == 1  # the test file is excluded by the rule itself
    assert item.rulepack == ".l9/semgrep-consumer-rules.yaml"


def test_declared_rules_matching_nothing_are_not_applicable(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo", {"src/a.py": "x\n"}, [RULE])
    (item,) = _consumer(_inventory(root))
    assert item.state is CapabilityState.NOT_APPLICABLE
    assert "paths.include" in item.reason


def test_invalid_declaration_is_failed_not_dropped(tmp_path: Path) -> None:
    unscoped = {key: value for key, value in RULE.items() if key != "paths"}
    root = _repository(tmp_path / "repo", {"ops/memory/cli.py": "x\n"}, [unscoped])
    inventory = _inventory(root)
    (item,) = _consumer(inventory)
    assert item.state is CapabilityState.FAILED
    assert "must declare paths" in item.reason
    assert inventory.status is CapabilityState.FAILED


def test_no_declaration_adds_no_target(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo", {"src/a.py": "x\n"})
    assert consumer_analysis_target(root) is None
    assert _consumer(_inventory(root)) == []


def test_consumer_coverage_never_counts_as_central_language_coverage(
    tmp_path: Path,
) -> None:
    """A file only a consumer rule reaches stays out of central coverage."""
    root = _repository(
        tmp_path / "repo",
        {"ops/memory/cli.py": "x\n", "vendor/ops/memory/lib.py": "x\n"},
        [{**RULE, "paths": {"include": ["vendor/"]}}],
    )
    inventory = _inventory(root)
    (item,) = _consumer(inventory)
    assert item.state is CapabilityState.APPLICABLE
    (python,) = [i for i in inventory.languages if i.language == "python"]
    # vendor/ is outside the central declared scope; the consumer rule does
    # not make it centrally analyzed.
    assert python.unanalyzed_file_count == 1


def _cli_inventory(root: Path, *extra: str) -> dict:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "l9_ci",
            "providers",
            "inventory",
            "--root",
            str(root),
            "--format",
            "json",
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    return payload.get("result", payload)


def test_cli_reports_the_consumer_target_only_when_asked(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo", {"ops/memory/cli.py": "x\n"}, [RULE])
    plain = _cli_inventory(root)
    assert all(
        not p["target"].startswith("consumer:") for p in plain["provider_prerequisites"]
    )
    asked = _cli_inventory(root, "--consumer-rules")
    targets = {p["target"]: p for p in asked["provider_prerequisites"]}
    assert targets["consumer:quantum-l9.cursor-governance"]["state"] == "applicable"
    assert asked["schema_version"] == "1.2.0"
