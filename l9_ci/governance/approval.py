"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
layer: [governance, approval]
tags: [L9_CI, trio, policy-approval, fail-closed]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED_APPROVAL_LABEL = "l9-validated:approve"
PROTECTED_PATH_PREFIXES = (
    ".github/governance/",
    ".github/scripts/",
    "l9-ci-core/.github/governance/",
    "l9-ci-core/.github/workflows/",
    "l9-ci-core/.github/scripts/",
)
PROTECTED_EXACT_PATHS = {
    ".github/workflows/trio-governance.yml",
    ".github/workflows/pr-pipeline.yml",
    "l9-ci-core/.github/workflows/trio-governance.yml",
    "l9-ci-core/.github/workflows/pr-pipeline.yml",
}


@dataclass(frozen=True)
class GovernanceApprovalResult:
    passed: bool
    protected_changed: list[str]
    labels: list[str]
    required_label: str
    reason: str


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_labels(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        labels: list[str] = []
        for item in raw:
            if isinstance(item, str):
                labels.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                labels.append(item["name"])
        return labels
    if isinstance(raw, dict) and isinstance(raw.get("labels"), list):
        return [str(item) for item in raw["labels"]]
    raise ValueError("PR labels JSON must be a list or {labels: [...]} mapping")


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_protected_path(path: str) -> bool:
    normalized = _normalize_path(path)
    if normalized in PROTECTED_EXACT_PATHS:
        return True
    return any(normalized.startswith(prefix) for prefix in PROTECTED_PATH_PREFIXES)


def evaluate_governance_approval(
    changed_files: list[str],
    labels: list[str] | None,
    *,
    required_label: str = REQUIRED_APPROVAL_LABEL,
    labels_known: bool = True,
) -> GovernanceApprovalResult:
    protected = sorted({_normalize_path(p) for p in changed_files if is_protected_path(p)})
    observed_labels = labels or []
    if not protected:
        return GovernanceApprovalResult(True, [], observed_labels, required_label, "no governance files changed")
    if not labels_known:
        return GovernanceApprovalResult(False, protected, observed_labels, required_label, "governance files changed but PR labels are unknown")
    if required_label not in set(observed_labels):
        return GovernanceApprovalResult(False, protected, observed_labels, required_label, "governance files changed without required approval label")
    return GovernanceApprovalResult(True, protected, observed_labels, required_label, "required governance approval label present")


def format_governance_approval(result: GovernanceApprovalResult) -> str:
    status = "passed" if result.passed else "failed"
    lines = [f"Governance approval {status}: {result.reason}"]
    if result.protected_changed:
        lines.append("protected files changed:")
        lines.extend(f"  {path}" for path in result.protected_changed)
    lines.append(f"required label: {result.required_label}")
    if result.labels:
        lines.append("observed labels:")
        lines.extend(f"  {label}" for label in sorted(result.labels))
    return "\n".join(lines)
