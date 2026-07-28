#!/usr/bin/env python3
"""Validate .github/governance/*.yaml as strict JSON documents.

Core's resolve-governance parses these files with json.loads. A YAML-valid but
JSON-invalid file (comments, trailing commas, single quotes) fails at runtime
inside the action, not at lint time. This closes that gap.

Additionally enforces the structural invariants that yamllint's key-duplicates
rule cannot see, because json.loads silently keeps the LAST duplicate key.

Self-CI companion documents that are real YAML (with comments) are fully
skipped — they are not part of the JSON governance pack.

Exit 0 = valid. Exit 1 = at least one violation. Stdlib only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

GOVERNANCE_GLOBS = (
    ".github/governance/*.yaml",
    "presets/*/.github/governance/*.yaml",
    "docs/templates/governance/*.yaml",
)

REQUIRED_PROFILES = {"pr_fast", "merge", "nightly", "release", "supply_chain"}
VALID_MODES = {"blocking", "advisory", "shadow", "disabled"}

# Real YAML documents (comments, unquoted keys). Do not json.loads these.
SKIP_JSON_PARSE = frozenset(
    {
        "l9-ci-shared-spec.yaml",
        "rule-modes.selfci.yaml",
    }
)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    seen: set[str] = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError(f"duplicate key: {key!r}")
        seen.add(key)
    return dict(pairs)


def load_strict(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return json.loads(text, object_pairs_hook=_reject_duplicate_keys)


def check_execution_profiles(doc: dict, errors: list[str], path: Path) -> None:
    profiles = doc.get("profiles")
    if not isinstance(profiles, dict):
        errors.append(f"{path}: profiles must be an object")
        return
    if set(profiles) != REQUIRED_PROFILES:
        errors.append(
            f"{path}: profile set must be exactly {sorted(REQUIRED_PROFILES)}, "
            f"got {sorted(profiles)}"
        )
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            errors.append(f"{path}: profile {name} must be an object")
            continue
        for key in ("sdk_profile", "strict", "default_mode", "providers", "allowed_events"):
            if key not in profile:
                errors.append(f"{path}: profile {name} missing {key}")
        if profile.get("sdk_profile") not in {"ci_fast", "ci_deep"}:
            errors.append(f"{path}: profile {name} sdk_profile must be ci_fast or ci_deep")
        if not isinstance(profile.get("strict"), bool):
            errors.append(f"{path}: profile {name} strict must be boolean")
        if profile.get("default_mode") not in VALID_MODES:
            errors.append(f"{path}: profile {name} default_mode invalid")
        providers = profile.get("providers")
        if not isinstance(providers, list) or not providers:
            errors.append(f"{path}: profile {name} providers must be a non-empty array")
        events = profile.get("allowed_events")
        if not isinstance(events, list) or not events:
            errors.append(f"{path}: profile {name} allowed_events must be a non-empty array")


def check_requiredness(doc: dict, errors: list[str], path: Path) -> None:
    profiles = doc.get("profiles")
    if not isinstance(profiles, dict):
        errors.append(f"{path}: profiles must be an object")
        return
    for name, mapping in profiles.items():
        if not isinstance(mapping, dict) or not mapping:
            errors.append(f"{path}: profile {name} must map providers to booleans")
            continue
        for provider, required in mapping.items():
            if not isinstance(required, bool):
                errors.append(f"{path}: {name}.{provider} must be boolean, got {required!r}")


def check_rule_modes(doc: dict, errors: list[str], path: Path) -> None:
    allowed = doc.get("allowed_modes")
    if allowed is not None and set(allowed) != VALID_MODES:
        errors.append(f"{path}: allowed_modes must equal {sorted(VALID_MODES)}")
    defaults = doc.get("defaults", {})
    if not isinstance(defaults, dict):
        errors.append(f"{path}: defaults must be an object")
        return
    for name, mode in defaults.items():
        if mode not in VALID_MODES:
            errors.append(f"{path}: defaults.{name} invalid mode {mode!r}")


def check_waivers(doc: dict, errors: list[str], path: Path) -> None:
    waivers = doc.get("waivers")
    if waivers is None:
        return
    if not isinstance(waivers, list):
        errors.append(f"{path}: waivers must be an array")
        return
    seen_ids: set[str] = set()
    for entry in waivers:
        if not isinstance(entry, dict):
            errors.append(f"{path}: each waiver must be an object")
            continue
        for key in ("id", "owner", "reason", "created", "expires", "scope"):
            if key not in entry:
                errors.append(f"{path}: waiver missing {key}")
        wid = entry.get("id")
        if isinstance(wid, str):
            if wid in seen_ids:
                errors.append(f"{path}: duplicate waiver id {wid}")
            seen_ids.add(wid)


CHECKS = {
    "execution-profiles.yaml": check_execution_profiles,
    "provider-requiredness.yaml": check_requiredness,
    "rule-modes.yaml": check_rule_modes,
    "waivers.yaml": check_waivers,
}


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    errors: list[str] = []
    checked = 0
    skipped = 0
    for pattern in GOVERNANCE_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.name in SKIP_JSON_PARSE:
                skipped += 1
                continue
            checked += 1
            try:
                doc = load_strict(path)
            except ValueError as exc:
                errors.append(f"{path}: not valid JSON ({exc})")
                continue
            if not isinstance(doc, dict):
                errors.append(f"{path}: top level must be a JSON object")
                continue
            if "schema" not in doc:
                errors.append(f"{path}: missing required 'schema' key")
            check = CHECKS.get(path.name)
            if check is not None:
                check(doc, errors, path)
    if checked == 0 and skipped == 0:
        print("notice: no governance documents found")
    for error in errors:
        print(f"::error file={error.split(':')[0]}::{error}")
    print(
        f"checked {checked} governance document(s), "
        f"skipped {skipped} real-YAML companion(s), "
        f"{len(errors)} error(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
