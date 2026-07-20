"""Guardrails over this repo's l9-ci-core wiring.

These tests keep the L9 analysis callers and governance honest so a careless edit
cannot silently drift the repo out of correctness with respect to l9-ci-core:

* every Core / external action reference is pinned to an immutable commit SHA;
* non-actions references point only at l9-ci-core (no rogue third-party org);
* least-privilege permissions (contents: read; only a publishing job writes);
* each caller's profile / matrix id are consistent with what it hands to
  publish-analysis.yml (a silent mismatch breaks publication);
* governance files parse as JSON and declare the profiles the callers use;
* semgrep is actually configured.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
GOVERNANCE = ROOT / ".github" / "governance"
CALLERS = sorted(WORKFLOWS.glob("l9-analysis*.yml"))

CORE_REPO = "Quantum-L9/l9-ci-core"
_USES = re.compile(r"^\s*uses:\s*(?P<ref>\S+)")
_SHA_PIN = re.compile(r"@[0-9a-fA-F]{40}$")
_WRITE_SCOPE = re.compile(
    r"(?m)^\s+(actions|checks|contents|deployments|discussions|"
    r"id-token|issues|packages|pages|pull-requests|"
    r"repository-projects|security-events|statuses):\s+write"
)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _uses_refs(path: Path):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _USES.match(line)
        if not match:
            continue
        ref = match.group("ref").split("#", 1)[0].strip()
        yield number, ref


class L9WiringTests(unittest.TestCase):
    def test_analysis_callers_exist(self) -> None:
        self.assertTrue(
            CALLERS, "expected .github/workflows/l9-analysis*.yml caller(s)"
        )

    def test_every_action_reference_is_sha_pinned(self) -> None:
        offenders = [
            f"{caller.name}:{number}:{ref}"
            for caller in CALLERS
            for number, ref in _uses_refs(caller)
            if not ref.startswith("./") and not _SHA_PIN.search(ref)
        ]
        self.assertEqual(
            [], offenders, f"unpinned refs (need @<40-hex sha>): {offenders}"
        )

    def test_non_action_references_target_core_only(self) -> None:
        offenders = [
            f"{caller.name}:{number}:{ref}"
            for caller in CALLERS
            for number, ref in _uses_refs(caller)
            if not ref.startswith("./")
            and not ref.startswith("actions/")
            and not ref.startswith(f"{CORE_REPO}/")
        ]
        self.assertEqual([], offenders, f"non-Core, non-actions refs: {offenders}")

    def test_least_privilege_permissions(self) -> None:
        for caller in CALLERS:
            with self.subTest(caller=caller.name):
                text = caller.read_text(encoding="utf-8")
                self.assertRegex(text, re.compile(r"(?m)^\s*contents:\s+read\s*$"))
                scopes = set(_WRITE_SCOPE.findall(text))
                self.assertEqual(
                    set(),
                    scopes - {"checks"},
                    f"{caller.name} requests forbidden write scopes: "
                    f"{sorted(scopes - {'checks'})}",
                )

    def test_profile_and_matrix_are_consistent_with_publish(self) -> None:
        for caller in CALLERS:
            with self.subTest(caller=caller.name):
                data = _load(caller)
                env = data.get("env", {})
                profile = env.get("L9_PROFILE")
                matrix = env.get("L9_MATRIX_ID")
                self.assertIsNotNone(profile, f"{caller.name} missing env.L9_PROFILE")
                self.assertIsNotNone(matrix, f"{caller.name} missing env.L9_MATRIX_ID")
                publish_with = data["jobs"]["publish"].get("with", {})
                self.assertEqual(
                    profile,
                    publish_with.get("profile"),
                    f"{caller.name}: L9_PROFILE != publish 'profile' input",
                )
                self.assertEqual(
                    matrix,
                    publish_with.get("matrix-id"),
                    f"{caller.name}: L9_MATRIX_ID != publish 'matrix-id' input",
                )

    def test_semgrep_config_is_present(self) -> None:
        for caller in CALLERS:
            with self.subTest(caller=caller.name):
                self.assertIn(
                    "--config",
                    caller.read_text(encoding="utf-8"),
                    f"{caller.name} runs semgrep without --config",
                )

    def test_governance_files_are_valid_json(self) -> None:
        files = sorted(GOVERNANCE.glob("*.yaml"))
        self.assertTrue(files, "no .github/governance/*.yaml files found")
        for path in files:
            with self.subTest(path=path.name):
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:  # noqa: PERF203
                    self.fail(f"{path.name} is not valid JSON: {error}")

    def test_caller_profiles_are_declared_in_governance(self) -> None:
        profiles = json.loads(
            (GOVERNANCE / "execution-profiles.yaml").read_text(encoding="utf-8")
        )["profiles"]
        for caller in CALLERS:
            profile = _load(caller).get("env", {}).get("L9_PROFILE")
            with self.subTest(caller=caller.name, profile=profile):
                self.assertIn(
                    profile,
                    profiles,
                    f"{caller.name} uses profile {profile!r} absent from "
                    f"execution-profiles.yaml",
                )


if __name__ == "__main__":
    unittest.main()
