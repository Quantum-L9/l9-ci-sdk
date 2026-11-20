"""Witnesses for the declared scan scope of required Semgrep runs (lane L1f).

A required central run (``l9-ci semgrep run --required``) used to let Semgrep
decide its own scope, from a consumer ``.semgrepignore`` or Semgrep's built-in
default list, and honoured inline ``nosemgrep``. These tests pin the
replacement: the SDK resolves the scope from the packaged ``scan-scope.yaml``,
passes each file explicitly, disables ``nosem`` and records the scope as
``l9.semgrep-scan-scope/v1`` evidence. They need no ``semgrep`` executable;
tests/commands/test_semgrep_required_scope_e2e.py proves the same against the
real one.
"""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

import l9_ci.__main__ as main_module
import l9_ci.commands.semgrep as semgrep_commands
from l9_ci.providers.semgrep import SemgrepProvider
from l9_ci.providers.spi import ProviderExecutionRequest
from l9_ci.commands.semgrep_scope import (
    resolve_scan_scope,
    scope_evidence_path,
    write_scope_evidence,
)
from l9_ci.rulesets.semgrep.scope import (
    NOT_A_REGULAR_FILE,
    ScanScopeError,
    load_scan_scope_policy,
    packaged_scan_scope_policy,
    scan_scope_policy_path,
)


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *arguments], check=True, capture_output=True
    )


def _repository(root: Path, tree: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "witness@example.invalid")
    _git(root, "config", "user.name", "witness")
    for relative, content in tree.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(root, "add", "--", *tree)
    _git(root, "commit", "-q", "-m", "witness")
    return root


def _schema_validator() -> Draft202012Validator:
    path = files("l9_ci").joinpath("schemas", "v1", "semgrep-scan-scope.schema.json")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


# --- the packaged policy ---------------------------------------------------


def test_packaged_policy_declares_include_and_every_exclusion() -> None:
    policy = packaged_scan_scope_policy()
    assert policy.source == "git-tracked"
    assert policy.anchored_paths == (".l9/runtime",)
    # Test paths are excluded by an explicit, recorded policy decision.
    assert {"test", "tests", "testsuite"} <= set(policy.directory_names)
    assert policy.names == (".semgrep",)
    assert policy.file_globs == ("*.min.js", "*_test.go")


@pytest.mark.parametrize(
    ("path", "label"),
    [
        (".l9/runtime/sdk/venv/lib/x.py", "anchored_paths:.l9/runtime"),
        ("tests/test_a.py", "directory_names:tests"),
        ("pkg/test/a.py", "directory_names:test"),
        ("node_modules/x/index.js", "directory_names:node_modules"),
        (".semgrep/rules.py", "names:.semgrep"),
        ("app/static/app.min.js", "file_globs:*.min.js"),
        ("cmd/main_test.go", "file_globs:*_test.go"),
    ],
)
def test_declared_exclusions_name_their_policy_entry(path: str, label: str) -> None:
    assert packaged_scan_scope_policy().exclusion_for(path) == label


@pytest.mark.parametrize(
    "path",
    [
        "src/app.py",
        "tests.py",  # a file named like a test directory is not one
        "contest/a.py",  # a directory name is matched whole, not by substring
        ".l9/contracts/policy.yaml",  # only the runtime subtree of .l9 is excluded
        "web/app.js",
    ],
)
def test_product_paths_stay_in_scope(path: str) -> None:
    assert packaged_scan_scope_policy().exclusion_for(path) is None


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda d: d.update(schema="other/v1"), "schema must be"),
        (lambda d: d.update(extra=1), "unknown keys"),
        (lambda d: d["include"].update(source="filesystem"), "include.source"),
        (lambda d: d["exclude"].pop("names"), "exclude must declare exactly"),
        (lambda d: d["exclude"]["names"].append("a/b"), "single path component"),
        (lambda d: d["exclude"]["anchored_paths"].append("../x"), "normalized"),
        (lambda d: d["exclude"]["file_globs"].append("*.min.js"), "duplicate"),
    ],
)
def test_malformed_policy_fails_closed(tmp_path: Path, mutation, message: str) -> None:
    import yaml

    document = yaml.safe_load(scan_scope_policy_path().read_text(encoding="utf-8"))
    mutation(document)
    path = tmp_path / "scan-scope.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ScanScopeError, match=message):
        load_scan_scope_policy(path)


# --- resolving a repository ------------------------------------------------


def test_consumer_semgrepignore_cannot_narrow_the_required_scope(
    tmp_path: Path,
) -> None:
    """Known-bad: a consumer .semgrepignore listing src/ no longer hides src/."""
    root = _repository(
        tmp_path / "repo",
        {
            ".semgrepignore": "src/\n",
            "src/app.py": "x = 1\n",
            "tests/test_app.py": "x = 1\n",
        },
    )
    scope = resolve_scan_scope(root, packaged_scan_scope_policy())
    assert "src/app.py" in scope.targets
    assert "tests/test_app.py" not in scope.targets
    assert scope.consumer_semgrepignore_files == (".semgrepignore",)
    evidence = scope.to_dict()
    assert evidence["consumer_semgrepignore"] == {
        "files": [".semgrepignore"],
        "honored": False,
    }


def test_scope_is_tracked_files_minus_declared_exclusions(tmp_path: Path) -> None:
    """Known-good: every tracked product file is a target, nothing else is."""
    root = _repository(
        tmp_path / "repo",
        {
            "src/app.py": "x = 1\n",
            "src/lib/util.py": "x = 1\n",
            "tests/test_app.py": "x = 1\n",
            ".semgrep/rule.py": "x = 1\n",
        },
    )
    (root / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    scope = resolve_scan_scope(root, packaged_scan_scope_policy())
    assert scope.targets == ("src/app.py", "src/lib/util.py")
    assert scope.files_tracked == 4
    assert dict(scope.excluded) == {
        "directory_names:tests": ("tests/test_app.py",),
        "names:.semgrep": (".semgrep/rule.py",),
    }


def test_tracked_file_missing_from_the_work_tree_is_reported(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo", {"src/a.py": "x\n", "src/b.py": "x\n"})
    (root / "src" / "b.py").unlink()
    scope = resolve_scan_scope(root, packaged_scan_scope_policy())
    assert scope.targets == ("src/a.py",)
    assert dict(scope.excluded) == {NOT_A_REGULAR_FILE: ("src/b.py",)}


def test_leading_dash_file_is_passed_as_a_path_not_an_option(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo", {"-oops.py": "x\n"})
    assert resolve_scan_scope(root, packaged_scan_scope_policy()).targets == (
        "./-oops.py",
    )


def test_non_git_root_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    with pytest.raises(ScanScopeError, match="Git work tree"):
        resolve_scan_scope(tmp_path, packaged_scan_scope_policy())


def test_empty_scope_fails_closed(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo", {"tests/test_a.py": "x\n"})
    with pytest.raises(ScanScopeError, match="empty"):
        resolve_scan_scope(root, packaged_scan_scope_policy())


def test_argv_bound_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repository(tmp_path / "repo", {"src/a.py": "x\n", "src/b.py": "x\n"})
    monkeypatch.setattr("l9_ci.rulesets.semgrep.scope.MAX_TARGET_ARGUMENT_BYTES", 10)
    with pytest.raises(ScanScopeError, match="argv bytes"):
        resolve_scan_scope(root, packaged_scan_scope_policy())


def test_scope_evidence_is_schema_valid_and_deterministic(tmp_path: Path) -> None:
    root = _repository(
        tmp_path / "repo",
        {"src/a.py": "x\n", "tests/test_a.py": "x\n", ".semgrepignore": "src/\n"},
    )
    scope = resolve_scan_scope(root, packaged_scan_scope_policy())
    first = tmp_path / "out" / "report.scope.json"
    second = tmp_path / "out2" / "report.scope.json"
    write_scope_evidence(scope, first)
    write_scope_evidence(scope, second)
    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    errors = sorted(_schema_validator().iter_errors(payload), key=str)
    assert errors == []
    assert payload["nosem"] == "disabled"
    assert payload["analysis_budget"] == {
        "timeout_seconds": 30,
        "timeout_threshold": 0,
        "on_timeout": "incomplete",
    }
    assert payload["files_in_scope"] == 2  # src/a.py and .semgrepignore itself
    assert scope_evidence_path(Path("raw/report.json")) == Path("raw/report.scope.json")


# --- the command and the provider -----------------------------------------


def _capture_run(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> SimpleNamespace:
    captured: list[SimpleNamespace] = []

    def fake_run(request):
        captured.append(request)
        return SimpleNamespace(output_path=request.output_path)

    monkeypatch.setattr(semgrep_commands, "run_semgrep_pipeline", fake_run)
    monkeypatch.setattr(sys, "argv", argv)
    assert main_module.main() == 0
    assert len(captured) == 1
    return captured[0]


def _run_argv(root: Path, out: Path, *extra: str) -> list[str]:
    return [
        "l9-ci",
        "semgrep",
        "run",
        "--language",
        "python",
        "--root",
        str(root),
        "--snapshot-id",
        "snapshot-1",
        "--output",
        str(out / "bundle.json"),
        "--raw-output",
        str(out / "raw" / "report.json"),
        *extra,
    ]


def test_required_run_disables_nosem_and_scans_the_declared_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repository(
        tmp_path / "repo",
        {".semgrepignore": "src/\n", "src/a.py": "x\n", "tests/t.py": "x\n"},
    )
    request = _capture_run(monkeypatch, _run_argv(root, tmp_path / "out", "--required"))
    assert "--disable-nosem" in request.execution_arguments
    arguments = list(request.execution_arguments)
    assert arguments[arguments.index("--timeout") + 1] == "30"
    assert arguments[arguments.index("--timeout-threshold") + 1] == "0"
    assert request.execution_targets == (".semgrepignore", "src/a.py")
    evidence = tmp_path / "out" / "raw" / "report.scope.json"
    assert json.loads(evidence.read_text(encoding="utf-8"))["files_in_scope"] == 2


def test_non_required_run_keeps_semgrep_scope_and_nosem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repository(tmp_path / "repo", {"src/a.py": "x\n"})
    request = _capture_run(monkeypatch, _run_argv(root, tmp_path / "out"))
    assert "--disable-nosem" not in request.execution_arguments
    assert "--timeout" not in request.execution_arguments
    assert "--timeout-threshold" not in request.execution_arguments
    assert request.execution_targets == ()
    assert not (tmp_path / "out" / "raw" / "report.scope.json").exists()


def test_required_run_refuses_an_unresolvable_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def must_not_run(request):  # pragma: no cover - the assertion is that it is not
        raise AssertionError("Semgrep ran without a declared scope")

    monkeypatch.setattr(semgrep_commands, "run_semgrep_pipeline", must_not_run)
    monkeypatch.setattr(
        sys, "argv", _run_argv(tmp_path, tmp_path / "out", "--required")
    )
    assert main_module.main() != 0


def test_provider_scans_explicit_targets_instead_of_the_root(tmp_path: Path) -> None:
    provider = SemgrepProvider()
    plan = provider.build_execution_plan(
        ProviderExecutionRequest(
            repository_root=tmp_path,
            output_path=tmp_path / "r.json",
            timeout_seconds=1,
            output_size_limit_bytes=1,
            targets=("src/a.py",),
        )
    )
    assert plan[-1] == "src/a.py"
    assert "." not in plan
    default = provider.build_execution_plan(
        ProviderExecutionRequest(
            repository_root=tmp_path,
            output_path=tmp_path / "r.json",
            timeout_seconds=1,
            output_size_limit_bytes=1,
        )
    )
    assert default[-1] == "."


@pytest.mark.parametrize("target", ["/etc/passwd", "../outside.py", "--config=x", ""])
def test_execution_request_rejects_non_repository_targets(
    tmp_path: Path, target: str
) -> None:
    with pytest.raises(ValueError, match="repository-relative"):
        ProviderExecutionRequest(
            repository_root=tmp_path,
            output_path=tmp_path / "r.json",
            timeout_seconds=1,
            output_size_limit_bytes=1,
            targets=(target,),
        )
