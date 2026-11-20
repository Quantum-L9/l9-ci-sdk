"""Validation of a donor-rule harvest ledger (L9-CI-SDK-004).

A harvest ledger has one row per donor rule. A row is what stands between a
specialized rule and its silent loss, so the validator refuses the shortcuts:
a row with no exact donor revision, a second row for the same rule, a
disposition that consolidates a rule (promotes it, calls it already satisfied,
or retires it) without a named central rule and a known-bad and known-good
witness, and a deferral with no stated next proof.

The validator reads rows; it does not run a scanner and it does not decide a
disposition. It returns every problem it finds, or an empty list.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

HARVEST_LEDGER_SCHEMA = "l9.semgrep-harvest-ledger/v1"

HARVEST_DISPOSITIONS = (
    "already_satisfied",
    "promote_global",
    "promote_language",
    "promote_framework",
    "retain_domain",
    "retire_duplicate",
    "defer_unknown",
)
# A disposition that says a central rule now carries the donor's behaviour.
_CONSOLIDATING = frozenset(
    {
        "already_satisfied",
        "promote_global",
        "promote_language",
        "promote_framework",
        "retire_duplicate",
    }
)
_SHA = re.compile(r"^[0-9a-f]{40}$")
_WITNESS_NAMES = {
    "known_bad": "known-bad",
    "known_good": "known-good",
    "non_target": "non-target",
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_harvest_ledger(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return every defect in ``rows``; an empty list means the ledger holds."""
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        rule_id = row.get("rule_id")
        donor = row.get("donor")
        label = f"row {index} ({rule_id!r})"
        if not _text(rule_id):
            errors.append(f"row {index}: missing rule_id")
        if not isinstance(donor, Mapping):
            errors.append(f"{label}: missing donor")
            donor = {}
        for field in ("repository", "path"):
            if not _text(donor.get(field)):
                errors.append(f"{label}: donor.{field} is missing")
        for field in ("head", "blob"):
            if not _SHA.match(str(donor.get(field, ""))):
                errors.append(f"{label}: donor.{field} is not a 40-hex git object id")
        key = (str(donor.get("repository")), str(rule_id))
        if key in seen:
            errors.append(f"{label}: a second row for the same donor rule")
        seen.add(key)

        disposition = row.get("disposition")
        if disposition not in HARVEST_DISPOSITIONS:
            errors.append(f"{label}: unknown disposition {disposition!r}")
        if not _text(row.get("behavior")):
            errors.append(f"{label}: behavior is not described")
        if not _text(row.get("rationale")):
            errors.append(f"{label}: disposition has no rationale")

        witnesses = row.get("witnesses")
        if not isinstance(witnesses, Mapping):
            witnesses = {}
        for field, name in _WITNESS_NAMES.items():
            witness = witnesses.get(field)
            if not isinstance(witness, Mapping) or not _text(witness.get("evidence")):
                errors.append(f"{label}: no {name} witness")

        if disposition in _CONSOLIDATING and not _text(row.get("sdk_rule")):
            errors.append(
                f"{label}: {disposition} names no central rule that carries the "
                "behaviour"
            )
        if disposition == "defer_unknown" and not _text(row.get("next_proof")):
            errors.append(f"{label}: defer_unknown states no next proof")
        if disposition == "retire_duplicate" and not _text(row.get("parity_receipt")):
            errors.append(
                f"{label}: retire_duplicate carries no parity receipt from a live "
                "central run"
            )
    return errors
