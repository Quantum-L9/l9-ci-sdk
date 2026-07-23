"""Fail-closed ledger file loading.

Ledgers are YAML documents with this shape:

.. code-block:: yaml

    schema_version: "1.0.0"
    gate: pre-commit/packet-envelope-prohibited
    entries:
      - id: packet-envelope/engine-chassis-adapter-import
        gate: pre-commit/packet-envelope-prohibited
        rule: packet-envelope-prohibited
        fingerprint: "<64-hex>"
        path: engine/chassis/adapter.py
        owner: "@cryptoxdog"
        issue: "Quantum-L9/Cognitive.Engine.Graphs#140"
        introduced_before: "8fe08c5"
        expires: "2026-09-30"
        removal_condition: "migrated-to:TransportPacket"

Loading never raises on malformed entries; it returns violations so
the comparator can fail the gate visibly. A ledger that cannot be
parsed at all is a hard error (fail-closed, exit INVALID_ARGUMENTS).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .comparator import load_entries_strict
from .comparison import BaselineViolation, ViolationKind
from .schemas import (
    BASELINE_SCHEMA_VERSION,
    BaselineEntry,
    RuleWaiverEntry,
    TestQuarantineEntry,
)


@dataclass(frozen=True, slots=True)
class LoadedLedger:
    """A parsed ledger plus any load-time violations."""

    schema_version: str
    gate: str
    entries: tuple[BaselineEntry | TestQuarantineEntry, ...]
    violations: tuple[BaselineViolation, ...]


def _read_yaml_document(path: Path) -> Mapping[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read ledger file {path}: {exc}") from exc
    try:
        document = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"ledger file {path} is not valid YAML: {exc}") from exc
    if document is None:
        document = {}
    if not isinstance(document, Mapping):
        raise ValueError(f"ledger file {path} must contain a YAML mapping")
    return document


def load_ledger(path: Path, *, entry_kind: str) -> LoadedLedger:
    """Load a baseline or quarantine ledger fail-closed.

    ``entry_kind`` is ``"test-quarantine"`` or ``"baseline"``.
    """
    document = _read_yaml_document(path)
    schema_version = str(document.get("schema_version", ""))
    gate = str(document.get("gate", ""))
    violations: list[BaselineViolation] = []
    if schema_version != BASELINE_SCHEMA_VERSION:
        violations.append(
            BaselineViolation(
                kind=ViolationKind.MALFORMED_BASELINE,
                gate=gate or entry_kind,
                rule="ledger",
                identity=str(path),
                detail=(
                    f"ledger schema_version {schema_version!r} is not supported; "
                    f"expected {BASELINE_SCHEMA_VERSION!r}"
                ),
            )
        )
    raw_entries = document.get("entries", [])
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
        violations.append(
            BaselineViolation(
                kind=ViolationKind.MALFORMED_BASELINE,
                gate=gate or entry_kind,
                rule="ledger",
                identity=str(path),
                detail="ledger entries must be a list",
            )
        )
        raw_entries = []
    entries, entry_violations = load_entries_strict(
        list(raw_entries), entry_kind=entry_kind
    )
    violations.extend(entry_violations)
    return LoadedLedger(
        schema_version=schema_version,
        gate=gate,
        entries=tuple(entries),
        violations=tuple(violations),
    )


def load_rule_waivers(
    path: Path,
) -> tuple[tuple[RuleWaiverEntry, ...], tuple[BaselineViolation, ...]]:
    """Load rule waivers fail-closed. Missing file means zero waivers."""
    if not path.exists():
        return (), ()
    document = _read_yaml_document(path)
    raw_entries = document.get("entries", [])
    violations: list[BaselineViolation] = []
    waivers: list[RuleWaiverEntry] = []
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
        violations.append(
            BaselineViolation(
                kind=ViolationKind.MALFORMED_BASELINE,
                gate="rule-waivers",
                rule="ledger",
                identity=str(path),
                detail="waiver entries must be a list",
            )
        )
        raw_entries = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, Mapping):
            violations.append(
                BaselineViolation(
                    kind=ViolationKind.MALFORMED_BASELINE,
                    gate="rule-waivers",
                    rule="ledger",
                    identity=f"entry[{index}]",
                    detail=f"waiver entry {index} is not a mapping",
                )
            )
            continue
        try:
            waiver = RuleWaiverEntry(
                id=str(raw.get("id", "")),
                gate=str(raw.get("gate", "")),
                rule=str(raw.get("rule", "")),
                path=str(raw.get("path", "")),
                owner=str(raw.get("owner", "") or ""),
                issue=str(raw.get("issue", "") or ""),
                expires=raw.get("expires", ""),  # type: ignore[arg-type]
                reason=str(raw.get("reason", "")),
                removal_condition=raw.get("removal_condition", ""),  # type: ignore[arg-type]
            )
        except ValueError as exc:
            message = str(exc)
            if message.startswith("owner"):
                kind = ViolationKind.MISSING_OWNER
            elif message.startswith("issue"):
                kind = ViolationKind.MISSING_ISSUE
            else:
                kind = ViolationKind.MALFORMED_BASELINE
            violations.append(
                BaselineViolation(
                    kind=kind,
                    gate="rule-waivers",
                    rule="ledger",
                    identity=str(raw.get("id", f"entry[{index}]")),
                    detail=f"invalid waiver entry: {message}",
                )
            )
            continue
        if waiver.id in seen_ids:
            violations.append(
                BaselineViolation(
                    kind=ViolationKind.MALFORMED_BASELINE,
                    gate="rule-waivers",
                    rule="ledger",
                    identity=waiver.id,
                    detail=f"duplicate waiver id {waiver.id!r}",
                    entry_id=waiver.id,
                )
            )
            continue
        seen_ids.add(waiver.id)
        waivers.append(waiver)
    return tuple(waivers), tuple(violations)
