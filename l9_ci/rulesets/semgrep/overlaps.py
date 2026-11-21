"""Registry rules superseded by SDK-packaged L9 rules (``rule-overlaps.yaml``).

A run that composes both the community registry ruleset and the packaged L9
ruleset reports one site once, under its L9 canonical rule. Both rules run; the
registry finding is withdrawn after the scan, and only where the superseding L9
rule reported the same call (same file, registry start line inside the L9
span). The registry evidence record is kept and the bundle says what was
withdrawn (``l9_ci.pipeline.overlaps``).

Nothing is excluded before the scan. The registry ruleset (``p/python``) is
fetched unpinned, so a later revision of a superseded rule may match a site the
packaged L9 rule does not; that finding has no covering L9 finding and stays
(Codex review on #143). See the packaged file for the admission rule and the
witness.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.resources
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

RULE_OVERLAPS_SCHEMA = "l9.semgrep-rule-overlaps/v1"
_RULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class RuleOverlapError(ValueError):
    """The packaged overlap registry is malformed."""


@dataclass(frozen=True, slots=True)
class RuleOverlap:
    language: str
    rule_id: str
    canonical_rule_id: str
    supersedes: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "rule_id": self.rule_id,
            "canonical_rule_id": self.canonical_rule_id,
            "supersedes": list(self.supersedes),
        }


@dataclass(frozen=True, slots=True)
class RuleOverlaps:
    version: str
    sha256: str
    overlaps: tuple[RuleOverlap, ...]

    def for_language(self, language: str) -> tuple[RuleOverlap, ...]:
        return tuple(item for item in self.overlaps if item.language == language)

    def supersessions(self, language: str) -> dict[str, str]:
        """Registry rule ID -> the packaged L9 rule ID that supersedes it."""
        return {
            rule: item.rule_id
            for item in self.for_language(language)
            for rule in item.supersedes
        }

    def superseded_rule_ids(self, language: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    rule
                    for item in self.for_language(language)
                    for rule in item.supersedes
                }
            )
        )


def rule_overlaps_path() -> Path:
    return Path(str(importlib.resources.files(__package__) / "rule-overlaps.yaml"))


def load_rule_overlaps(path: Path | None = None) -> RuleOverlaps:
    source = path if path is not None else rule_overlaps_path()
    raw = source.read_bytes()
    document = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(document, dict) or set(document) != {
        "schema",
        "version",
        "overlaps",
    }:
        raise RuleOverlapError("rule overlaps hold exactly schema, version, overlaps")
    if document["schema"] != RULE_OVERLAPS_SCHEMA:
        raise RuleOverlapError(f"rule overlaps schema must be {RULE_OVERLAPS_SCHEMA}")
    entries = document["overlaps"]
    if not isinstance(entries, list):
        raise RuleOverlapError("overlaps must be a list")
    overlaps = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        keys = {"language", "rule_id", "canonical_rule_id", "supersedes", "reason"}
        if not isinstance(entry, dict) or set(entry) != keys:
            raise RuleOverlapError(f"overlap {index} must carry exactly {sorted(keys)}")
        supersedes = entry["supersedes"]
        if not isinstance(supersedes, list) or not supersedes:
            raise RuleOverlapError(
                f"overlap {index}: supersedes must be a non-empty list"
            )
        for rule in [entry["rule_id"], *supersedes]:
            if not isinstance(rule, str) or not _RULE_ID.fullmatch(rule):
                raise RuleOverlapError(f"overlap {index}: malformed rule id {rule!r}")
        for rule in supersedes:
            if rule in seen:
                raise RuleOverlapError(f"{rule} is superseded twice")
            if rule.startswith("l9."):
                raise RuleOverlapError(f"{rule}: only registry rules can be superseded")
            seen.add(rule)
        overlaps.append(
            RuleOverlap(
                language=str(entry["language"]),
                rule_id=entry["rule_id"],
                canonical_rule_id=str(entry["canonical_rule_id"]),
                supersedes=tuple(sorted(supersedes)),
                reason=str(entry["reason"]).strip(),
            )
        )
    return RuleOverlaps(
        version=str(document["version"]),
        sha256=hashlib.sha256(raw).hexdigest(),
        overlaps=tuple(overlaps),
    )


@functools.lru_cache(maxsize=1)
def packaged_rule_overlaps() -> RuleOverlaps:
    return load_rule_overlaps()


__all__ = [
    "RULE_OVERLAPS_SCHEMA",
    "RuleOverlap",
    "RuleOverlapError",
    "RuleOverlaps",
    "load_rule_overlaps",
    "packaged_rule_overlaps",
    "rule_overlaps_path",
]
