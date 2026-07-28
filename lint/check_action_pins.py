#!/usr/bin/env python3
"""Workflow semantic guards that yamllint structurally cannot express.

Assert every `uses:` is SHA-pinned, every literal l9-ci-core pin in a file is
identical, and every workflow declares a non-empty `permissions:` block.

Two invariants, both already asserted informally in l9-ci-core prose:

1. External actions must be pinned to a full 40-character commit SHA
   (mirrors tests/architecture/test_external_action_pins.py).
2. `uses:` does not support expression interpolation, so the Core SHA is
   duplicated literally on every Quantum-L9/l9-ci-core@... line. This checker
   fails when those literals drift apart within one file, which is the exact
   failure mode the workflow comments warn about.

3. A `permissions:` key with nothing under it parses as null, not as an empty
   permission set. yamllint's empty-values rule cannot enforce this in workflow
   files because bare `pull_request:` under `on:` is valid syntax and would be
   flagged identically. This checker distinguishes the two.

Exit 0 = valid. Exit 1 = violation. Stdlib only.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

USES = re.compile(r"^\s*(?:-\s+)?uses:\s*['\"]?([^'\"\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
CORE_REPO = "Quantum-L9/l9-ci-core"
SEARCH_GLOBS = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".github/actions/*/action.yml",
    "presets/*/.github/workflows/*.yml",
    "docs/templates/*.yml",
    "starter-workflows/*/*.yml",
)
# Local composite actions / reusable workflows are referenced by path.
LOCAL_PREFIXES = ("./", "docker://")

PERMISSIONS_KEY = re.compile(r"^(\s*)permissions:(.*)$")


def check_permissions(path: Path, errors: list[str]) -> None:
    """Flag null permissions blocks and, in workflows, a missing top-level block."""
    lines = path.read_text(encoding="utf-8").splitlines()
    is_workflow = path.parent.name == "workflows"
    has_top_level = False
    for index, line in enumerate(lines):
        match = PERMISSIONS_KEY.match(line)
        if match is None:
            continue
        indent, inline = match.group(1), match.group(2).strip()
        if not indent:
            has_top_level = True
        if inline and not inline.startswith("#"):
            continue  # e.g. `permissions: {}` or `permissions: read-all`
        # Look ahead for at least one more-indented, non-comment scope line.
        populated = False
        for following in lines[index + 1 :]:
            if not following.strip() or following.lstrip().startswith("#"):
                continue
            following_indent = len(following) - len(following.lstrip())
            populated = following_indent > len(indent)
            break
        if not populated:
            errors.append(
                f"{path}:{index + 1}: `permissions:` is empty and parses as null; "
                f"write `permissions: {{}}` to grant nothing, or list explicit scopes"
            )
    if is_workflow and not has_top_level:
        errors.append(
            f"{path}: no top-level `permissions:` block; "
            f"declare least privilege explicitly rather than inheriting defaults"
        )


def check_file(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    core_pins: dict[str, list[str]] = defaultdict(list)
    for match in USES.finditer(text):
        ref = match.group(1)
        if ref.startswith(LOCAL_PREFIXES):
            continue
        if "@" not in ref:
            errors.append(f"{path}: `uses: {ref}` has no ref; pin to a full commit SHA")
            continue
        target, _, rev = ref.rpartition("@")
        if not FULL_SHA.match(rev):
            errors.append(
                f"{path}: `uses: {ref}` is not SHA-pinned "
                f"(refs must be a full 40-character lowercase commit SHA)"
            )
            continue
        if target.startswith(CORE_REPO):
            core_pins[rev].append(target)
    if len(core_pins) > 1:
        listed = ", ".join(sorted(core_pins))
        errors.append(
            f"{path}: l9-ci-core is pinned to {len(core_pins)} different SHAs "
            f"in one file ({listed}); every literal must be bumped together"
        )


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    errors: list[str] = []
    checked = 0
    for pattern in SEARCH_GLOBS:
        for path in sorted(root.glob(pattern)):
            checked += 1
            check_file(path, errors)
            check_permissions(path, errors)
    for error in errors:
        print(f"::error::{error}")
    print(f"checked {checked} workflow/action file(s), {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
