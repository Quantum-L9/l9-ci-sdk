"""The inventory plans a Semgrep target only on files its scan will reach.

Regression for Cursor-Governance run 44824379833 (2026-11-20): every
JavaScript file in that repository is a test fixture under ``tests/``. The
inventory counted them, served by ``language:typescript`` since SDK #125, so
Core planned a required TypeScript instance. The scan then excluded ``tests/``
(the declared scan scope, l9_ci/rulesets/semgrep/scan-scope.yaml), scanned
nothing, and the gate ended ``incomplete`` on every pull request.

Each Semgrep target now carries the same declared scope the required run
resolves its targets from. A target whose matching files are all out of scope
is ``not_applicable``, with the excluded paths as evidence, so plan and scan
agree by construction.

Since B1+B2 (scan-scope policy 1.1.0) ``tests/`` is in required scope, so the
Cursor-Governance fixtures are scanned and plan a completed TypeScript
instance. The not-applicable witnesses use a path the policy still excludes
(``vendor/``).
"""

from __future__ import annotations

from pathlib import Path

from l9_ci.capabilities import (
    AnalysisTarget,
    CapabilityState,
    build_capability_inventory,
    validate_capability_inventory,
)
from l9_ci.commands.providers import default_analysis_targets


def _repository(root: Path, tree: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for relative, content in tree.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _inventory(root: Path):  # type: ignore[no-untyped-def]
    inventory = build_capability_inventory(
        root, targets=default_analysis_targets(root), SDK_version="2.0.0"
    )
    validate_capability_inventory(inventory.to_dict())
    return inventory


def _prerequisite(inventory, target: str):  # type: ignore[no-untyped-def]
    (item,) = [p for p in inventory.provider_prerequisites if p.target == target]
    return item


def test_javascript_only_in_excluded_paths_plans_no_typescript_instance(
    tmp_path: Path,
) -> None:
    """Known-bad shape: every JS file sits under a declared exclusion."""
    root = _repository(
        tmp_path / "repo",
        {
            "ops/app.py": "x = 1\n",
            "ops/vendor/a/run_workflow.js": "module.exports = {}\n",
            "ops/vendor/b/run_issue.js": "module.exports = {}\n",
        },
    )
    inventory = _inventory(root)
    typescript = _prerequisite(inventory, "language:typescript")
    assert typescript.state is CapabilityState.NOT_APPLICABLE
    assert typescript.file_count == 0
    assert "directory_names:vendor (2:" in typescript.reason
    assert "ops/vendor/a/run_workflow.js" in typescript.reason
    assert _prerequisite(inventory, "language:python").state is (
        CapabilityState.APPLICABLE
    )
    (javascript,) = [i for i in inventory.languages if i.language == "javascript"]
    assert javascript.state is CapabilityState.UNSUPPORTED
    assert javascript.unanalyzed_file_count == 2
    assert "outside the declared scan scope" in javascript.reason


def test_javascript_test_fixtures_are_in_scope_and_plan_typescript(
    tmp_path: Path,
) -> None:
    """Cursor-Governance's shape since B1+B2: tests/ is in required scope.

    Its JavaScript test fixtures are scanned, so the TypeScript instance is
    planned and completes on them instead of being dropped.
    """
    root = _repository(
        tmp_path / "repo",
        {
            "ops/app.py": "x = 1\n",
            "ops/scripts/tests/fixtures/a/run_workflow.js": "module.exports = {}\n",
        },
    )
    typescript = _prerequisite(_inventory(root), "language:typescript")
    assert typescript.state is CapabilityState.APPLICABLE
    assert typescript.file_count == 1


def test_javascript_in_product_code_still_plans_typescript(tmp_path: Path) -> None:
    """Known-good: an in-scope JS file keeps the target applicable."""
    root = _repository(
        tmp_path / "repo",
        {
            "web/app.js": "module.exports = {}\n",
            "vendor/fixture.js": "module.exports = {}\n",
        },
    )
    typescript = _prerequisite(_inventory(root), "language:typescript")
    assert typescript.state is CapabilityState.APPLICABLE
    assert typescript.file_count == 1


def test_prerequisite_counts_only_in_scope_files(tmp_path: Path) -> None:
    root = _repository(
        tmp_path / "repo",
        {
            "src/a.py": "x\n",
            "src/b.py": "x\n",
            "vendor/dep.py": "x\n",
        },
    )
    inventory = _inventory(root)
    assert _prerequisite(inventory, "language:python").file_count == 2
    (python,) = [i for i in inventory.languages if i.language == "python"]
    assert python.state is CapabilityState.APPLICABLE
    assert python.unanalyzed_file_count == 1
    assert "1 are outside the declared scan scope" in python.reason


def test_target_without_scope_exclusion_is_unchanged(tmp_path: Path) -> None:
    """A caller that declares no scope keeps the previous counting."""
    root = _repository(tmp_path / "repo", {"tests/fixture.js": "x\n"})
    target = AnalysisTarget(
        provider_id="semgrep",
        scope="language",
        name="typescript",
        languages=("typescript", "javascript"),
        rulepack="l9_ci/rulesets/semgrep/typescript",
        rulepack_resolved=True,
        suffixes=(".js",),
    )
    inventory = build_capability_inventory(root, targets=(target,), SDK_version="2.0.0")
    assert inventory.provider_prerequisites[0].state is CapabilityState.APPLICABLE
