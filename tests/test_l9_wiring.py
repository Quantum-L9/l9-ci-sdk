"""Guardrails over the SDK's thin l9-ci-core workflow callers."""

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
CORE_PREFIX = "Quantum-L9/l9-ci-core/.github/workflows/analyze-semgrep.yml@"
FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
EXPECTED = {
    "l9-analysis.yml": ("pr_fast", "pr-semgrep"),
    "l9-analysis-merge.yml": ("merge", "merge-semgrep"),
    "l9-analysis-nightly.yml": ("nightly", "nightly-semgrep"),
    "l9-analysis-release.yml": ("release", "release-semgrep"),
    "l9-analysis-supply-chain.yml": ("supply_chain", "supply-chain-semgrep"),
}


class L9WiringTests(unittest.TestCase):
    def test_expected_thin_callers_exist(self) -> None:
        self.assertEqual(set(EXPECTED), {path.name for path in CALLERS})

    def test_each_caller_is_one_reusable_workflow_job(self) -> None:
        for caller in CALLERS:
            with self.subTest(caller=caller.name):
                data = yaml.safe_load(caller.read_text(encoding="utf-8"))
                jobs = data.get("jobs", {})
                self.assertEqual(["analysis"], list(jobs))
                job = jobs["analysis"]
                ref = job.get("uses", "")
                self.assertTrue(ref.startswith(CORE_PREFIX), ref)
                self.assertRegex(ref.removeprefix(CORE_PREFIX), FULL_SHA)
                self.assertNotIn("steps", job)
                self.assertNotIn("run:", caller.read_text(encoding="utf-8"))

    def test_profile_matrix_and_sdk_pin_are_explicit(self) -> None:
        for caller in CALLERS:
            with self.subTest(caller=caller.name):
                data = yaml.safe_load(caller.read_text(encoding="utf-8"))
                values = data["jobs"]["analysis"]["with"]
                profile, matrix = EXPECTED[caller.name]
                self.assertEqual(profile, values.get("profile"))
                self.assertEqual(matrix, values.get("matrix-id"))
                self.assertRegex(str(values.get("sdk-revision", "")), FULL_SHA)
                configs = json.loads(values["semgrep-configs-json"])
                self.assertTrue(configs)

    def test_permissions_are_least_privilege_for_publication(self) -> None:
        for caller in CALLERS:
            with self.subTest(caller=caller.name):
                data = yaml.safe_load(caller.read_text(encoding="utf-8"))
                self.assertEqual("read", data["permissions"]["contents"])
                permissions = data["jobs"]["analysis"]["permissions"]
                self.assertEqual(
                    {"actions": "read", "checks": "write", "contents": "read"},
                    permissions,
                )

    def test_caller_profiles_are_declared_in_governance(self) -> None:
        profiles = json.loads(
            (GOVERNANCE / "execution-profiles.yaml").read_text(encoding="utf-8")
        )["profiles"]
        for profile, _ in EXPECTED.values():
            self.assertIn(profile, profiles)


if __name__ == "__main__":
    unittest.main()
