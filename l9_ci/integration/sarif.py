"""Deterministic projection from a canonical finding bundle to a SARIF 2.1.0
subset.

The projector maps the SDK's own canonical `FindingBundle` — never a raw
provider report — onto the small, well-defined slice of SARIF that GitHub code
scanning ingests. It is a pure, deterministic transform: identical input
bundles yield byte-identical SARIF, and it never performs a network call,
mutates the bundle, changes a gate verdict, or discloses source lines or
secrets (only redaction-safe canonical fields are emitted).
"""

from __future__ import annotations

from typing import Any

from l9_ci.contracts import Finding, FindingBundle

SARIF_VERSION = "2.1.0"
# The public SARIF 2.1.0 schema GitHub code scanning validates against. This is
# an identifier in the emitted log, not a local file path.
SARIF_SCHEMA_URI = "https://json.schemastore.org/sarif-2.1.0.json"
# The SDK subset schema this projection is validated against.
SARIF_LOG_SUBSET_SCHEMA = "l9.sarif-log/v1"
TOOL_NAME = "l9-ci-sdk"
TOOL_INFORMATION_URI = "https://github.com/Quantum-L9/l9-ci-sdk"

# Canonical severity -> SARIF result level. Deterministic and total: any value
# outside the map (including a finding with no severity) falls back to
# ``warning`` so a finding is surfaced, never silently dropped or escalated.
_SEVERITY_TO_LEVEL: dict[str, str] = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "informational": "note",
    "unknown": "warning",
}
_DEFAULT_LEVEL = "warning"

_REGION_FIELDS: tuple[tuple[str, str], ...] = (
    ("start_line", "startLine"),
    ("start_column", "startColumn"),
    ("end_line", "endLine"),
    ("end_column", "endColumn"),
)


def _rule_id(finding: Finding) -> str:
    """Prefer the canonical rule id; fall back to the provider rule id.

    The provider rule id is always present on a canonical finding, so a SARIF
    result always carries a non-empty ruleId.
    """
    return finding.canonical_rule_id or finding.provider_rule_id


def _level(finding: Finding) -> str:
    severity = finding.severity.value if finding.severity else None
    return _SEVERITY_TO_LEVEL.get(severity or "", _DEFAULT_LEVEL)


def _region(location: dict[str, Any]) -> dict[str, int]:
    region: dict[str, int] = {}
    for source_key, sarif_key in _REGION_FIELDS:
        value = location.get(source_key)
        if value is not None:
            region[sarif_key] = value
    return region


def _result(finding: Finding) -> dict[str, Any]:
    locations: list[dict[str, Any]] = []
    for location in finding.locations:
        location_dict = location.to_dict()
        physical: dict[str, Any] = {
            "artifactLocation": {"uri": location_dict["normalized_path"]},
        }
        region = _region(location_dict)
        if region:
            physical["region"] = region
        locations.append({"physicalLocation": physical})
    return {
        "ruleId": _rule_id(finding),
        "level": _level(finding),
        "message": {"text": finding.message},
        "locations": locations,
        # Stable, non-sensitive correlation id — the canonical fingerprint, not
        # a secret and not raw source. Lets GitHub de-duplicate across runs.
        "partialFingerprints": {"l9/fingerprint": finding.fingerprint},
    }


def project_sarif_log(bundle: FindingBundle, *, strict: bool) -> dict[str, Any]:
    """Project ``bundle`` onto a deterministic SARIF 2.1.0 subset log.

    Findings are emitted in canonical ``finding_id`` order and driver rules in
    sorted ``ruleId`` order, so the output is stable. In ``strict`` mode a
    finding without a canonical rule id (unresolved identity) is rejected rather
    than projected under its provider rule id.
    """
    findings = sorted(bundle.findings, key=lambda item: item.finding_id)
    if strict:
        unresolved = [f.finding_id for f in findings if not f.canonical_rule_id]
        if unresolved:
            raise ValueError(
                "strict SARIF projection rejected findings without canonical "
                f"identity: {', '.join(unresolved)}"
            )
    results = [_result(finding) for finding in findings]
    rules = [{"id": rule_id} for rule_id in sorted({_rule_id(f) for f in findings})]
    return {
        "version": SARIF_VERSION,
        "$schema": SARIF_SCHEMA_URI,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "informationUri": TOOL_INFORMATION_URI,
                        "version": bundle.SDK_version,
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }


__all__ = [
    "SARIF_LOG_SUBSET_SCHEMA",
    "SARIF_SCHEMA_URI",
    "SARIF_VERSION",
    "project_sarif_log",
]
