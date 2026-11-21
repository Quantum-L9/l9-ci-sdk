"""Real-Semgrep witnesses for CENTRAL-DIFF (ADR 0023).

Each case runs ``l9-ci semgrep run --required --baseline-commit <base>`` end to
end, with the packaged L9 baseline profile and a policy whose default mode is
``blocking``, against a throwaway Git repository with a base and a head commit.
The CTO's five cases (ASSIGN CENTRAL-DIFF, 2026-11-21):

* a new finding blocks;
* a pre-existing finding warns (advisory, counted) and does not block;
* an unresolvable base blocks (fails closed, every finding ``unknown``);
* an incomplete result blocks, whether the head scan or the base scan;
* a finding whose file was renamed stays pre-existing.

The known-bad source lines are assembled at runtime so this file holds no
literal match for the rule. Like the other real-Semgrep tests these skip
without a ``semgrep`` executable; the ``semgrep rule fixtures`` step of
.github/workflows/ci.yml runs this file with the self-CI pinned Semgrep.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from l9_ci.artifacts import load_and_validate_bundle
from l9_ci.contracts import CoverageStatus
from l9_ci.gates import GateStatus, evaluate_gate

_needs_semgrep = pytest.mark.skipif(
    shutil.which("semgrep") is None and os.environ.get("L9_REQUIRE_SEMGREP") != "1",
    reason="semgrep executable not available on PATH",
)

POLICY = Path("tests/fixtures/semgrep/core-semgrep-policy-v4.json").resolve()
_RULE = "L9-PYTHON-EXEC-EVAL-USE"
_CALL = "ev" + "al"
_BAD = f"def run(user_input):\n    return {_CALL}(user_input)\n"
_OTHER_BAD = f"def other(value):\n    return {_CALL}(value)\n"


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write(root: Path, tree: dict[str, str]) -> None:
    for relative, content in tree.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _repository(root: Path, base: dict[str, str]) -> tuple[Path, str]:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "witness@example.invalid")
    _git(root, "config", "user.name", "witness")
    _write(root, base)
    _git(root, "add", "--", *base)
    _git(root, "commit", "-q", "-m", "base")
    return root, _git(root, "rev-parse", "HEAD")


def _commit(root: Path, tree: dict[str, str], message: str = "head") -> None:
    _write(root, tree)
    _git(root, "add", "--", *tree)
    _git(root, "commit", "-q", "-m", message)


def _run(root: Path, out: Path, baseline: str):  # type: ignore[no-untyped-def]
    command = [
        sys.executable,
        "-m",
        "l9_ci",
        "semgrep",
        "run",
        "--language",
        "python",
        "--profile",
        "l9-baseline",
        "--root",
        str(root),
        "--snapshot-id",
        "witness",
        "--policy",
        str(POLICY),
        "--required",
        "--baseline-commit",
        baseline,
        "--output",
        str(out / "bundle.json"),
        "--raw-output",
        str(out / "raw" / "report.json"),
        "--format",
        "json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return load_and_validate_bundle(out / "bundle.json")


def _statuses(bundle) -> dict[tuple[str, int], tuple[str, str]]:  # type: ignore[no-untyped-def]
    by_id = {item.finding_id: item for item in bundle.classifications}
    result = {}
    for finding in bundle.findings:
        if finding.canonical_rule_id != _RULE:
            continue
        location = finding.locations[0]
        classification = by_id[finding.finding_id]
        status = classification.baseline_status
        result[(location.normalized_path, location.start_line)] = (
            status.value if status is not None else "none",
            classification.mode.value,
        )
    return result


@_needs_semgrep
def test_a_new_finding_blocks(tmp_path: Path) -> None:
    root, base = _repository(tmp_path / "repo", {"src/a.py": _BAD})
    _commit(root, {"src/b.py": _OTHER_BAD})
    bundle = _run(root, tmp_path / "out", base)
    assert _statuses(bundle) == {
        ("src/a.py", 2): ("pre_existing", "advisory"),
        ("src/b.py", 2): ("new", "blocking"),
    }
    assert evaluate_gate(bundle).status is GateStatus.FAIL


@_needs_semgrep
def test_a_pre_existing_finding_warns_with_counts(tmp_path: Path) -> None:
    root, base = _repository(tmp_path / "repo", {"src/a.py": _BAD})
    # The finding moves two lines down; it is the same finding.
    _commit(root, {"src/a.py": "# one\n# two\n" + _BAD})
    bundle = _run(root, tmp_path / "out", base)
    assert _statuses(bundle) == {("src/a.py", 4): ("pre_existing", "advisory")}
    result = evaluate_gate(bundle)
    assert result.status is GateStatus.PASS
    (summary,) = [
        i for i in bundle.limitations if i.startswith(f"baseline {base[:12]}:")
    ]
    assert (
        "0 new, 1 pre-existing (1 blocking reported as advisory), 0 unknown" in summary
    )
    assert bundle.provider_failures == ()


@_needs_semgrep
def test_an_unresolvable_base_blocks(tmp_path: Path) -> None:
    root, _ = _repository(tmp_path / "repo", {"src/a.py": _BAD})
    _commit(root, {"src/a.py": "# one\n" + _BAD})
    bundle = _run(root, tmp_path / "out", "0" * 40)
    assert _statuses(bundle) == {("src/a.py", 3): ("unknown", "blocking")}
    (failure,) = bundle.provider_failures
    assert failure.required and failure.fatal
    assert "is not in this repository" in failure.message
    assert evaluate_gate(bundle).status is GateStatus.INCOMPLETE


@_needs_semgrep
def test_a_base_missing_from_a_shallow_clone_blocks(tmp_path: Path) -> None:
    source, base = _repository(tmp_path / "source", {"src/a.py": _BAD})
    _commit(source, {"src/a.py": "# one\n" + _BAD})
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{source}", str(shallow)],
        check=True,
        capture_output=True,
    )
    bundle = _run(shallow, tmp_path / "out", base)
    assert {status for status, _ in _statuses(bundle).values()} == {"unknown"}
    assert evaluate_gate(bundle).status is GateStatus.INCOMPLETE


@_needs_semgrep
def test_tracked_changes_make_the_base_comparison_unknown(tmp_path: Path) -> None:
    """Semgrep 1.171.0 does not abort on unstaged changes; the SDK refuses."""
    root, base = _repository(tmp_path / "repo", {"src/a.py": _BAD})
    _commit(root, {"src/b.py": _OTHER_BAD})
    (root / "src" / "a.py").write_text("# local edit\n" + _BAD, encoding="utf-8")
    bundle = _run(root, tmp_path / "out", base)
    assert {status for status, _ in _statuses(bundle).values()} == {"unknown"}
    (failure,) = bundle.provider_failures
    assert "clean working tree" in failure.message
    assert evaluate_gate(bundle).status is GateStatus.INCOMPLETE


def _partial(result):  # type: ignore[no-untyped-def]
    return replace(
        result, coverage=replace(result.coverage, status=CoverageStatus.PARTIAL)
    )


def _run_in_process(
    monkeypatch: pytest.MonkeyPatch, root: Path, out: Path, baseline: str, partial: int
):  # type: ignore[no-untyped-def]
    """Run the CLI in process; scan number ``partial`` (0 head, 1 base) is incomplete.

    Semgrep reports a timeout as incomplete coverage, but a real timeout cannot
    be produced deterministically here, so the real scan's coverage is marked
    partial. Everything else, both scans included, is real.
    """
    from l9_ci import __main__ as entry
    from l9_ci.pipeline import semgrep as pipeline

    real = pipeline.execute_and_normalize
    calls: list[int] = []

    def execute(provider, *, request, context):  # type: ignore[no-untyped-def]
        result = real(provider, request=request, context=context)
        calls.append(len(calls))
        return _partial(result) if len(calls) - 1 == partial else result

    monkeypatch.setattr(pipeline, "execute_and_normalize", execute)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l9-ci",
            "semgrep",
            "run",
            "--language",
            "python",
            "--profile",
            "l9-baseline",
            "--root",
            str(root),
            "--snapshot-id",
            "witness",
            "--policy",
            str(POLICY),
            "--required",
            "--baseline-commit",
            baseline,
            "--output",
            str(out / "bundle.json"),
            "--raw-output",
            str(out / "raw" / "report.json"),
            "--format",
            "json",
        ],
    )
    assert entry.main() == 0
    assert calls == [0, 1]  # both scans ran
    return load_and_validate_bundle(out / "bundle.json")


@_needs_semgrep
def test_an_incomplete_head_result_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every finding is pre-existing, yet an incomplete head scan never passes."""
    root, base = _repository(tmp_path / "repo", {"src/a.py": _BAD})
    _commit(root, {"src/a.py": "# one\n" + _BAD})
    bundle = _run_in_process(monkeypatch, root, tmp_path / "out", base, partial=0)
    assert _statuses(bundle) == {("src/a.py", 3): ("pre_existing", "advisory")}
    assert evaluate_gate(bundle).status is GateStatus.INCOMPLETE


@_needs_semgrep
def test_an_incomplete_base_scan_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, base = _repository(tmp_path / "repo", {"src/a.py": _BAD})
    _commit(root, {"src/a.py": "# one\n" + _BAD})
    bundle = _run_in_process(monkeypatch, root, tmp_path / "out", base, partial=1)
    assert _statuses(bundle) == {("src/a.py", 3): ("unknown", "blocking")}
    (failure,) = bundle.provider_failures
    assert "baseline scan is incomplete" in failure.message
    assert evaluate_gate(bundle).status is GateStatus.INCOMPLETE


@_needs_semgrep
def test_a_renamed_file_stays_pre_existing(tmp_path: Path) -> None:
    root, base = _repository(tmp_path / "repo", {"src/a.py": _BAD})
    _git(root, "mv", "src/a.py", "src/renamed.py")
    _git(root, "commit", "-q", "-m", "rename")
    bundle = _run(root, tmp_path / "out", base)
    assert _statuses(bundle) == {("src/renamed.py", 2): ("pre_existing", "advisory")}
    assert evaluate_gate(bundle).status is GateStatus.PASS


@_needs_semgrep
def test_without_a_baseline_nothing_changes(tmp_path: Path) -> None:
    root, _ = _repository(tmp_path / "repo", {"src/a.py": _BAD})
    command = [
        sys.executable,
        "-m",
        "l9_ci",
        "semgrep",
        "run",
        "--language",
        "python",
        "--profile",
        "l9-baseline",
        "--root",
        str(root),
        "--snapshot-id",
        "witness",
        "--policy",
        str(POLICY),
        "--required",
        "--output",
        str(tmp_path / "out" / "bundle.json"),
        "--format",
        "json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    bundle = load_and_validate_bundle(tmp_path / "out" / "bundle.json")
    assert _statuses(bundle) == {("src/a.py", 2): ("none", "blocking")}
    payload = json.loads((tmp_path / "out" / "bundle.json").read_text("utf-8"))
    assert all("baseline_status" not in item for item in payload["classifications"])


def test_a_baseline_requires_a_full_commit_id_and_a_policy(tmp_path: Path) -> None:
    root, _ = _repository(tmp_path / "repo", {"src/a.py": "x = 1\n"})
    for extra, message in (
        (["--policy", str(POLICY), "--baseline-commit", "main"], "full lowercase"),
        (["--baseline-commit", "a" * 40], "requires a finding policy"),
    ):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "l9_ci",
                "semgrep",
                "run",
                "--language",
                "python",
                "--root",
                str(root),
                "--snapshot-id",
                "witness",
                "--output",
                str(tmp_path / "out.json"),
                "--format",
                "json",
                *extra,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode != 0
        assert message in (completed.stdout + completed.stderr)
