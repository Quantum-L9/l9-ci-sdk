"""Registry-rule precision declarations (``rule-precision.yaml``, ADR 0024).

A declaration names a registry rule and the keyword whose literal ``False``
value declares the non-security use the rule cannot see. The pipeline applies
it after the scan (``l9_ci.pipeline.precision``); this module only loads and
validates the packaged file, so it depends on nothing but the standard library
and YAML.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.resources
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

RULE_PRECISION_SCHEMA = "l9.semgrep-rule-precision/v1"
_RULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_KEYWORD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ENTRY_KEYS = frozenset({"language", "rule_id", "not_when_keyword_false", "reason"})


class RulePrecisionError(ValueError):
    """The packaged rule-precision file is malformed."""


@dataclass(frozen=True, slots=True)
class RulePrecision:
    language: str
    rule_id: str
    keyword: str
    reason: str


@dataclass(frozen=True, slots=True)
class RulePrecisions:
    version: str
    sha256: str
    precisions: tuple[RulePrecision, ...]

    def keywords(self, language: str) -> dict[str, str]:
        """Registry rule ID -> the keyword whose literal False withholds it."""
        return {
            item.rule_id: item.keyword
            for item in self.precisions
            if item.language == language
        }


def rule_precision_path() -> Path:
    return Path(str(importlib.resources.files(__package__) / "rule-precision.yaml"))


def load_rule_precisions(path: Path | None = None) -> RulePrecisions:
    source = path if path is not None else rule_precision_path()
    raw = source.read_bytes()
    document = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(document, dict) or set(document) != {
        "schema",
        "version",
        "precisions",
    }:
        raise RulePrecisionError(
            "rule precision holds exactly schema, version, precisions"
        )
    if document["schema"] != RULE_PRECISION_SCHEMA:
        raise RulePrecisionError(
            f"rule precision schema must be {RULE_PRECISION_SCHEMA}"
        )
    entries = document["precisions"]
    if not isinstance(entries, list):
        raise RulePrecisionError("precisions must be a list")
    precisions: list[RulePrecision] = []
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
            raise RulePrecisionError(
                f"precision {index} must carry exactly {sorted(_ENTRY_KEYS)}"
            )
        rule_id = entry["rule_id"]
        keyword = entry["not_when_keyword_false"]
        language = entry["language"]
        reason = entry["reason"]
        if not isinstance(rule_id, str) or not _RULE_ID.fullmatch(rule_id):
            raise RulePrecisionError(
                f"precision {index}: malformed rule id {rule_id!r}"
            )
        if rule_id.startswith("l9."):
            raise RulePrecisionError(
                f"{rule_id}: a packaged L9 rule states its own precision in its pattern"
            )
        if not isinstance(keyword, str) or not _KEYWORD.fullmatch(keyword):
            raise RulePrecisionError(
                f"precision {index}: malformed keyword {keyword!r}"
            )
        if language != "python":
            raise RulePrecisionError(
                f"precision {index}: keyword precision is defined for python only"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise RulePrecisionError(f"precision {index}: reason must be non-empty")
        if (language, rule_id) in seen:
            raise RulePrecisionError(f"{rule_id} is declared twice")
        seen.add((language, rule_id))
        precisions.append(
            RulePrecision(
                language=language,
                rule_id=rule_id,
                keyword=keyword,
                reason=reason.strip(),
            )
        )
    return RulePrecisions(
        version=str(document["version"]),
        sha256=hashlib.sha256(raw).hexdigest(),
        precisions=tuple(precisions),
    )


@functools.lru_cache(maxsize=1)
def packaged_rule_precisions() -> RulePrecisions:
    return load_rule_precisions()


__all__ = [
    "RULE_PRECISION_SCHEMA",
    "RulePrecision",
    "RulePrecisionError",
    "RulePrecisions",
    "load_rule_precisions",
    "packaged_rule_precisions",
    "rule_precision_path",
]
