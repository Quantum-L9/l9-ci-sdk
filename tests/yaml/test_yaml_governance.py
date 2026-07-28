"""Tests for the L9 YAML governance tooling.

Run: pytest tests/yaml -q
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "lint"
GOV = TOOLS / "check_governance_json.py"
PINS = TOOLS / "check_action_pins.py"


def run(script: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def write_governance(root: Path, name: str, payload: object) -> None:
    directory = root / ".github" / "governance"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")


VALID_PROFILES = {
    "schema": "l9.execution-profiles/v1",
    "profiles": {
        name: {
            "sdk_profile": "ci_fast",
            "strict": False,
            "default_mode": "advisory",
            "providers": ["semgrep"],
            "policy": "",
            "allowed_events": ["pull_request", "workflow_dispatch"],
        }
        for name in ("pr_fast", "merge", "nightly", "release", "supply_chain")
    },
}


def test_valid_governance_passes(tmp_path: Path) -> None:
    write_governance(tmp_path, "execution-profiles.yaml", VALID_PROFILES)
    result = run(GOV, tmp_path)
    assert result.returncode == 0, result.stdout


def test_duplicate_key_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / ".github" / "governance"
    directory.mkdir(parents=True)
    (directory / "rule-modes.yaml").write_text(
        '{"schema": "l9.rule-modes/v1", "defaults": {"pr_fast": "advisory"}, '
        '"defaults": {"pr_fast": "disabled"}}',
        encoding="utf-8",
    )
    result = run(GOV, tmp_path)
    assert result.returncode == 1
    assert "duplicate key" in result.stdout


def test_yaml_comment_breaks_json_parse(tmp_path: Path) -> None:
    directory = tmp_path / ".github" / "governance"
    directory.mkdir(parents=True)
    (directory / "waivers.yaml").write_text(
        '# a YAML comment\n{"schema": "l9.waivers/v1", "waivers": []}',
        encoding="utf-8",
    )
    result = run(GOV, tmp_path)
    assert result.returncode == 1
    assert "not valid JSON" in result.stdout


def test_missing_profile_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(VALID_PROFILES))
    del payload["profiles"]["nightly"]
    write_governance(tmp_path, "execution-profiles.yaml", payload)
    result = run(GOV, tmp_path)
    assert result.returncode == 1
    assert "profile set must be exactly" in result.stdout


def test_non_boolean_requiredness_is_rejected(tmp_path: Path) -> None:
    write_governance(
        tmp_path,
        "provider-requiredness.yaml",
        {"schema": "l9.provider-requiredness/v1", "profiles": {"pr_fast": {"semgrep": "yes"}}},
    )
    result = run(GOV, tmp_path)
    assert result.returncode == 1
    assert "must be boolean" in result.stdout


def test_duplicate_waiver_id_is_rejected(tmp_path: Path) -> None:
    entry = {
        "id": "WAIVER-1",
        "owner": "platform",
        "reason": "r",
        "created": "2026-07-01",
        "expires": "2026-08-01",
        "scope": {},
    }
    write_governance(
        tmp_path, "waivers.yaml", {"schema": "l9.waivers/v1", "waivers": [entry, dict(entry)]}
    )
    result = run(GOV, tmp_path)
    assert result.returncode == 1
    assert "duplicate waiver id" in result.stdout


def test_selfci_yaml_companions_are_skipped(tmp_path: Path) -> None:
    """Real-YAML self-CI files must not be json.loads'd."""
    write_governance(tmp_path, "execution-profiles.yaml", VALID_PROFILES)
    directory = tmp_path / ".github" / "governance"
    (directory / "rule-modes.selfci.yaml").write_text(
        "# comment\nversion: 1\nmodes: {}\n",
        encoding="utf-8",
    )
    (directory / "l9-ci-shared-spec.yaml").write_text(
        "# comment\nversion: 1\nname: shared\n",
        encoding="utf-8",
    )
    result = run(GOV, tmp_path)
    assert result.returncode == 0, result.stdout
    assert "skipped 2" in result.stdout


def write_workflow(root: Path, name: str, body: str) -> None:
    directory = root / ".github" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(body, encoding="utf-8")


SHA_A = "f88116503430aa18992b70d8d31063e34ff97ef1"
SHA_B = "f7a4ee8c1f4e4413cb3645d088cafa3e9c798235"


def test_sha_pinned_workflow_passes(tmp_path: Path) -> None:
    write_workflow(
        tmp_path,
        "ok.yml",
        f"permissions:\n  contents: read\njobs:\n  a:\n    steps:\n"
        f"      - uses: Quantum-L9/l9-ci-core/.github/actions/x@{SHA_A}\n",
    )
    result = run(PINS, tmp_path)
    assert result.returncode == 0, result.stdout


def test_tag_pin_is_rejected(tmp_path: Path) -> None:
    write_workflow(
        tmp_path,
        "bad.yml",
        "permissions:\n  contents: read\njobs:\n  a:\n    steps:\n"
        "      - uses: actions/checkout@v4\n",
    )
    result = run(PINS, tmp_path)
    assert result.returncode == 1
    assert "not SHA-pinned" in result.stdout


def test_mixed_core_pins_in_one_file_are_rejected(tmp_path: Path) -> None:
    write_workflow(
        tmp_path,
        "drift.yml",
        "permissions:\n  contents: read\njobs:\n  a:\n    steps:\n"
        f"      - uses: Quantum-L9/l9-ci-core/.github/actions/x@{SHA_A}\n"
        f"      - uses: Quantum-L9/l9-ci-core/.github/actions/y@{SHA_B}\n",
    )
    result = run(PINS, tmp_path)
    assert result.returncode == 1
    assert "different SHAs" in result.stdout


def test_local_composite_reference_is_ignored(tmp_path: Path) -> None:
    write_workflow(
        tmp_path,
        "local.yml",
        "permissions:\n  contents: read\njobs:\n  a:\n    steps:\n"
        "      - uses: ./.github/actions/x\n",
    )
    result = run(PINS, tmp_path)
    assert result.returncode == 0, result.stdout


def test_null_permissions_block_is_rejected(tmp_path: Path) -> None:
    write_workflow(
        tmp_path,
        "nullperms.yml",
        "on:\n  pull_request:\npermissions:\njobs:\n  a:\n    steps:\n      - run: echo hi\n",
    )
    result = run(PINS, tmp_path)
    assert result.returncode == 1
    assert "parses as null" in result.stdout


def test_empty_mapping_permissions_is_accepted(tmp_path: Path) -> None:
    write_workflow(
        tmp_path,
        "emptymap.yml",
        "on:\n  pull_request:\npermissions: {}\njobs:\n  a:\n    steps:\n"
        "      - run: echo hi\n",
    )
    result = run(PINS, tmp_path)
    assert result.returncode == 0, result.stdout


def test_populated_permissions_is_accepted(tmp_path: Path) -> None:
    write_workflow(
        tmp_path,
        "good.yml",
        "on:\n  pull_request:\npermissions:\n  contents: read\njobs:\n"
        "  a:\n    steps:\n      - run: echo hi\n",
    )
    result = run(PINS, tmp_path)
    assert result.returncode == 0, result.stdout


def test_missing_top_level_permissions_is_rejected(tmp_path: Path) -> None:
    write_workflow(
        tmp_path,
        "noperms.yml",
        "on:\n  pull_request:\njobs:\n  a:\n    steps:\n      - run: echo hi\n",
    )
    result = run(PINS, tmp_path)
    assert result.returncode == 1
    assert "no top-level" in result.stdout


def test_bare_on_trigger_keys_are_not_flagged(tmp_path: Path) -> None:
    """`pull_request:` with no value is valid GitHub syntax and must not be an error."""
    write_workflow(
        tmp_path,
        "bare.yml",
        "on:\n  pull_request:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
        "jobs:\n  a:\n    steps:\n      - run: echo hi\n",
    )
    result = run(PINS, tmp_path)
    assert result.returncode == 0, result.stdout
