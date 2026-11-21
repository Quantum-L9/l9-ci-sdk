"""Central finding waivers (``l9.finding-waivers/v1``).

A waiver exempts exactly one finding of one repository from blocking the gate.
The ledger is central: Core supplies it next to the finding policy, and the
command refuses a ledger that sits inside the repository under analysis, so a
consumer cannot add entries.

Every entry names the finding it waives by every coordinate the SDK records:
repository, provider, provider rule ID, repository-relative path and the
finding fingerprint (``Finding.fingerprint``: provider, rule, path, exact span
and provider discriminator). A change to the waived code changes the
fingerprint, so the waiver stops matching and the finding blocks again.

An entry also carries an owner, a reason, a creation date and an expiry. On and
after the day after ``expires`` the entry stops applying automatically: the
finding keeps its policy classification and the bundle records why.

Applying a waiver changes only a ``blocking`` classification: its mode becomes
``advisory`` and ``waiver_id`` names the entry. The policy key, version and
resolution status are kept, so the record still shows what the policy said.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from l9_ci.contracts import Finding, FindingClassification, RuleMode

FINDING_WAIVERS_SCHEMA = "l9.finding-waivers/v1"

_ENTRY_KEYS = frozenset(
    {"id", "owner", "reason", "created", "expires", "scope", "fingerprint"}
)
_SCOPE_KEYS = frozenset({"repository", "provider_id", "provider_rule_id", "path"})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class FindingWaiverError(ValueError):
    """The waiver ledger is malformed; no waiver from it may apply."""


@dataclass(frozen=True, slots=True)
class FindingWaiver:
    waiver_id: str
    owner: str
    reason: str
    created: date
    expires: date
    repository: str
    provider_id: str
    provider_rule_id: str
    path: str
    fingerprint: str

    def is_active(self, on: date) -> bool:
        return self.created <= on <= self.expires

    def matches(self, finding: Finding, repository: str) -> bool:
        primary = finding.locations[0].normalized_path if finding.locations else None
        return (
            repository == self.repository
            and finding.provider_id == self.provider_id
            and finding.provider_rule_id == self.provider_rule_id
            and primary == self.path
            and finding.fingerprint == self.fingerprint
        )


@dataclass(frozen=True, slots=True)
class FindingWaiverLedger:
    waivers: tuple[FindingWaiver, ...]

    @classmethod
    def load(cls, path: Path) -> FindingWaiverLedger:
        text = path.read_text(encoding="utf-8")
        try:
            document = (
                json.loads(text)
                if path.suffix.lower() == ".json"
                else yaml.safe_load(text)
            )
        except (ValueError, yaml.YAMLError) as exc:
            raise FindingWaiverError(
                f"waiver ledger {path.name} is not valid: {type(exc).__name__}"
            ) from exc
        return cls.from_dict(document)

    @classmethod
    def from_dict(cls, document: object) -> FindingWaiverLedger:
        if not isinstance(document, Mapping):
            raise FindingWaiverError("waiver ledger must be a mapping")
        if set(document) != {"schema", "waivers"}:
            raise FindingWaiverError("waiver ledger holds exactly schema and waivers")
        if document["schema"] != FINDING_WAIVERS_SCHEMA:
            raise FindingWaiverError(
                f"waiver ledger schema must be {FINDING_WAIVERS_SCHEMA}"
            )
        entries = document["waivers"]
        if not isinstance(entries, list):
            raise FindingWaiverError("waivers must be a list")
        waivers = [_entry(index, entry) for index, entry in enumerate(entries)]
        ids = [item.waiver_id for item in waivers]
        if len(set(ids)) != len(ids):
            raise FindingWaiverError("waiver ids must be unique")
        return cls(waivers=tuple(sorted(waivers, key=lambda item: item.waiver_id)))


def _text(entry: Mapping[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FindingWaiverError(f"{where}: {key} must be a non-empty string")
    return value.strip()


def _date(entry: Mapping[str, Any], key: str, where: str) -> date:
    value = entry.get(key)
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise FindingWaiverError(f"{where}: {key} must be an ISO date (YYYY-MM-DD)")


def _entry(index: int, entry: object) -> FindingWaiver:
    where = f"waiver {index}"
    if not isinstance(entry, Mapping):
        raise FindingWaiverError(f"{where} must be a mapping")
    if set(entry) != _ENTRY_KEYS:
        missing = sorted(_ENTRY_KEYS - set(entry))
        unknown = sorted(set(entry) - _ENTRY_KEYS)
        raise FindingWaiverError(
            f"{where} must carry exactly {sorted(_ENTRY_KEYS)}; "
            f"missing {missing}, unknown {unknown}"
        )
    waiver_id = _text(entry, "id", where)
    if not _ID.fullmatch(waiver_id):
        raise FindingWaiverError(f"{where}: id {waiver_id!r} is malformed")
    where = f"waiver {waiver_id}"
    scope = entry["scope"]
    if not isinstance(scope, Mapping) or set(scope) != _SCOPE_KEYS:
        raise FindingWaiverError(
            f"{where}: scope must carry exactly {sorted(_SCOPE_KEYS)}"
        )
    repository = _text(scope, "repository", where)
    if not _REPOSITORY.fullmatch(repository):
        raise FindingWaiverError(f"{where}: repository must be <owner>/<name>")
    path = _text(scope, "path", where)
    if path.startswith(("/", "./")) or ".." in path.split("/") or "\\" in path:
        raise FindingWaiverError(f"{where}: path must be repository-relative")
    fingerprint = _text(entry, "fingerprint", where)
    if not _FINGERPRINT.fullmatch(fingerprint):
        raise FindingWaiverError(f"{where}: fingerprint must be 64 lowercase hex")
    created = _date(entry, "created", where)
    expires = _date(entry, "expires", where)
    if expires < created:
        raise FindingWaiverError(f"{where}: expires is before created")
    return FindingWaiver(
        waiver_id=waiver_id,
        owner=_text(entry, "owner", where),
        reason=_text(entry, "reason", where),
        created=created,
        expires=expires,
        repository=repository,
        provider_id=_text(scope, "provider_id", where),
        provider_rule_id=_text(scope, "provider_rule_id", where),
        path=path,
        fingerprint=fingerprint,
    )


@dataclass(frozen=True, slots=True)
class WaiverApplication:
    classifications: tuple[FindingClassification, ...]
    applied: tuple[str, ...]
    limitations: tuple[str, ...]


def apply_waivers(
    findings: Iterable[Finding],
    classifications: Iterable[FindingClassification],
    ledger: FindingWaiverLedger,
    *,
    repository: str,
    on: date,
) -> WaiverApplication:
    """Apply ``ledger`` to ``classifications`` for ``repository`` on day ``on``.

    Only an active waiver that matches a finding exactly turns that finding's
    ``blocking`` classification into ``advisory`` with ``waiver_id`` set. An
    expired waiver, a waiver not yet in force and a waiver that matches no
    finding apply to nothing and are recorded as limitations.
    """
    if not _REPOSITORY.fullmatch(repository):
        raise FindingWaiverError("repository must be <owner>/<name>")
    by_id = {finding.finding_id: finding for finding in findings}
    relevant = [item for item in ledger.waivers if item.repository == repository]
    limitations: list[str] = []
    active: list[FindingWaiver] = []
    for waiver in relevant:
        if on > waiver.expires:
            limitations.append(
                f"waiver {waiver.waiver_id} expired on {waiver.expires.isoformat()} "
                "and no longer applies"
            )
        elif on < waiver.created:
            limitations.append(
                f"waiver {waiver.waiver_id} is not in force until "
                f"{waiver.created.isoformat()}"
            )
        else:
            active.append(waiver)
    applied: list[str] = []
    matched: set[str] = set()
    result: list[FindingClassification] = []
    for classification in classifications:
        finding = by_id.get(classification.finding_id)
        hit = next(
            (
                item
                for item in active
                if finding is not None and item.matches(finding, repository)
            ),
            None,
        )
        if hit is not None:
            matched.add(hit.waiver_id)
        if hit is not None and classification.mode is RuleMode.BLOCKING:
            result.append(
                replace(
                    classification,
                    mode=RuleMode.ADVISORY,
                    waiver_id=hit.waiver_id,
                )
            )
            applied.append(classification.finding_id)
        else:
            result.append(classification)
    for pending in active:
        if pending.waiver_id not in matched:
            limitations.append(
                f"waiver {pending.waiver_id} matched no finding (rule "
                f"{pending.provider_rule_id} at {pending.path}); it applied to nothing"
            )
    return WaiverApplication(
        classifications=tuple(result),
        applied=tuple(sorted(applied)),
        limitations=tuple(sorted(limitations)),
    )


__all__ = [
    "FINDING_WAIVERS_SCHEMA",
    "FindingWaiver",
    "FindingWaiverError",
    "FindingWaiverLedger",
    "WaiverApplication",
    "apply_waivers",
]
