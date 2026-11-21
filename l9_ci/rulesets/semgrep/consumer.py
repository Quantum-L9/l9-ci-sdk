"""Scoped consumer rulepack binding (ADR 0021).

A consumer repository opts its own Semgrep rules into central CI with one
declaration file, ``.l9/semgrep-consumer-rules.yaml``
(``l9.semgrep-consumer-rulepack/v1``)::

    schema: l9.semgrep-consumer-rulepack/v1
    owner: Quantum-L9/Cursor-Governance
    rule_files:
      - .semgrep/l9-pr.yml

Only the listed files are loaded. This module validates the declaration and
every rule in it before anything runs. Any violation raises
:class:`ConsumerRulepackError`, which fails the consumer execution and never
the central one:

* every rule ID carries the consumer's prefix (``rule_id_prefix``, default
  ``l9.``) and is not one of the SDK's packaged rule IDs;
* every rule declares its own non-empty ``paths.include``;
* every rule carries ``metadata.l9.canonical_rule_id`` in the consumer
  namespace ``CONSUMER-<REPOSITORY>-<NAME>``, so a consumer rule can never
  claim a central canonical ID (the provider trusts that metadata field);
* every rule uses only per-rule keys from an allow-list, and a rule file
  holds nothing but ``rules``.

The consumer execution keeps the consumer's own ``.semgrepignore`` and inline
``nosemgrep``; only central required runs disable them. A Semgrep rule cannot
suppress another rule's finding, so consumer rules only ever add findings.
"""

from __future__ import annotations

import functools
import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from l9_ci.rulesets.semgrep.composition import (
    RulepackCompositionError,
    _compose_pack,
    rulepack_definitions,
)

CONSUMER_DECLARATION_PATH = ".l9/semgrep-consumer-rules.yaml"
CONSUMER_DECLARATION_SCHEMA = "l9.semgrep-consumer-rulepack/v1"
CONSUMER_EVIDENCE_SCHEMA = "l9.semgrep-consumer-rulepack-evidence/v1"
CONSUMER_EVIDENCE_SCHEMA_VERSION = "1.0.0"
DEFAULT_RULE_ID_PREFIX = "l9."
MAX_RULE_FILES = 32
MAX_RULES = 256

_DECLARATION_KEYS = frozenset({"schema", "owner", "rule_files", "rule_id_prefix"})
_OWNER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")
_PREFIX = re.compile(r"^[a-z0-9][a-z0-9_-]*\.$")
_CANONICAL_NAME = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,99}$")

# Per-rule Semgrep keys a consumer rule may use. Anything else, including any
# key Semgrep adds later, is refused until reviewed.
_ALLOWED_RULE_KEYS = frozenset(
    {
        "id",
        "message",
        "severity",
        "languages",
        "metadata",
        "paths",
        "mode",
        "options",
        "pattern",
        "patterns",
        "pattern-either",
        "pattern-regex",
        "pattern-not",
        "pattern-not-regex",
        "pattern-inside",
        "pattern-not-inside",
        "pattern-sources",
        "pattern-sinks",
        "pattern-sanitizers",
        "pattern-propagators",
        "focus-metavariable",
        "metavariable-regex",
        "metavariable-pattern",
        "metavariable-comparison",
        "fix",
        "fix-regex",
    }
)
_PATH_KEYS = frozenset({"include", "exclude"})

# File suffixes Semgrep analyzes for each rule language. A language not listed
# here (``generic``, ``regex``, ...) can match any file.
_LANGUAGE_SUFFIXES: Mapping[str, tuple[str, ...]] = {
    "python": (".py", ".pyi"),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"),
    "typescript": (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"),
    "go": (".go",),
    "java": (".java",),
    "yaml": (".yml", ".yaml"),
    "json": (".json",),
    "bash": (".sh", ".bash"),
    "dockerfile": ("dockerfile",),
}


class ConsumerRulepackError(ValueError):
    """The consumer declaration or one of its rule files is not admissible."""


def _repository_token(owner: str) -> str:
    """``Quantum-L9/Cursor-Governance`` -> ``CURSOR-GOVERNANCE``."""
    name = owner.split("/", 1)[1]
    return re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")


def consumer_canonical_prefix(owner: str) -> str:
    """The canonical rule ID prefix every rule of ``owner`` must use."""
    return f"CONSUMER-{_repository_token(owner)}-"


def consumer_target_name(owner: str) -> str:
    """The inventory target name of ``owner``'s declaration (lower case)."""
    return re.sub(r"[^a-z0-9._-]+", "-", owner.lower().replace("/", "."))


@functools.lru_cache(maxsize=1)
def packaged_rule_ids() -> frozenset[str]:
    """Every rule ID the SDK packages, across all rulepacks."""
    identifiers: set[str] = set()
    for definition in rulepack_definitions():
        try:
            pack, _ = _compose_pack(definition)
        except RulepackCompositionError:
            continue
        identifiers.update(pack.rule_ids)
    return frozenset(identifiers)


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile one Semgrep ``paths`` pattern (gitignore style) to a regex.

    A leading ``/`` or any inner ``/`` anchors the pattern at the repository
    root; otherwise it matches at any depth. A trailing ``/`` names a
    directory and matches everything beneath it. ``**`` spans directories,
    ``*`` and ``?`` stay within one path component.
    """
    text = pattern.strip()
    directory = text.endswith("/")
    text = text.strip("/")
    anchored = pattern.strip().startswith("/") or "/" in text
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        if text.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
            continue
        if text.startswith("**", index):
            out.append(".*")
            index += 2
            continue
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        index += 1
    body = "".join(out)
    prefix = "" if anchored else "(?:.*/)?"
    suffix = "/.*" if directory else "(?:/.*)?"
    return re.compile(f"^{prefix}{body}{suffix}$")


@dataclass(frozen=True, slots=True)
class ConsumerRule:
    rule_id: str
    canonical_rule_id: str
    languages: tuple[str, ...]
    include: tuple[str, ...]
    exclude: tuple[str, ...]

    def matches(self, path: str) -> bool:
        """Whether this rule's own ``paths`` and languages admit ``path``."""
        if not any(_glob_regex(pattern).match(path) for pattern in self.include):
            return False
        if any(_glob_regex(pattern).match(path) for pattern in self.exclude):
            return False
        suffixes = [
            suffix
            for language in self.languages
            for suffix in _LANGUAGE_SUFFIXES.get(language.lower(), ("",))
        ]
        if "" in suffixes or not suffixes:
            return True
        name = PurePosixPath(path).name.lower()
        return any(name == suffix or name.endswith(suffix) for suffix in suffixes)


@dataclass(frozen=True, slots=True)
class ConsumerRuleFile:
    path: str
    sha256: str
    rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConsumerDeclaration:
    """A validated consumer rulepack declaration."""

    owner: str
    path: str
    sha256: str
    rule_id_prefix: str
    rule_files: tuple[ConsumerRuleFile, ...]
    rules: tuple[ConsumerRule, ...]

    @property
    def target_name(self) -> str:
        return consumer_target_name(self.owner)

    def config_paths(self, root: Path) -> tuple[Path, ...]:
        return tuple(root / item.path for item in self.rule_files)

    def matching_files(self, files: Sequence[str]) -> tuple[str, ...]:
        """The tracked files at least one declared rule's own scope admits."""
        return tuple(
            sorted(path for path in files if any(r.matches(path) for r in self.rules))
        )

    def to_evidence(self) -> dict[str, Any]:
        """The ``l9.semgrep-consumer-rulepack-evidence/v1`` record of a run."""
        return {
            "schema": CONSUMER_EVIDENCE_SCHEMA,
            "schema_version": CONSUMER_EVIDENCE_SCHEMA_VERSION,
            "owner": self.owner,
            "declaration": {"path": self.path, "sha256": self.sha256},
            "rule_id_prefix": self.rule_id_prefix,
            "canonical_rule_id_prefix": consumer_canonical_prefix(self.owner),
            "rule_files": [
                {
                    "path": item.path,
                    "sha256": item.sha256,
                    "rule_ids": list(item.rule_ids),
                }
                for item in self.rule_files
            ],
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "canonical_rule_id": rule.canonical_rule_id,
                    "include": list(rule.include),
                    "exclude": list(rule.exclude),
                }
                for rule in self.rules
            ],
            "nosem": "honored",
            "consumer_semgrepignore": "honored",
        }


def _relative_file(root: Path, value: object, what: str) -> tuple[str, Path]:
    if not isinstance(value, str) or not value.strip():
        raise ConsumerRulepackError(f"{what} must be a non-empty path")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or value.startswith("-")
        or str(relative) != value
    ):
        raise ConsumerRulepackError(
            f"{what} {value!r} must be a normalized repository-relative path"
        )
    path = root / value
    if path.is_symlink() or not path.is_file():
        raise ConsumerRulepackError(f"{what} {value!r} is not a regular file")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ConsumerRulepackError(f"{what} {value!r} leaves the repository") from exc
    return value, path


def _string_list(value: object, what: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ConsumerRulepackError(f"{what} must be a list of non-empty strings")
    return tuple(value)


def _load_yaml(path: Path, label: str) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ConsumerRulepackError(
            f"{label} could not be read: {type(exc).__name__}"
        ) from exc


def _validate_rule(
    rule: object,
    *,
    label: str,
    prefix: str,
    canonical_prefix: str,
    packaged: frozenset[str],
) -> ConsumerRule:
    if not isinstance(rule, dict):
        raise ConsumerRulepackError(f"{label}: every rule must be a mapping")
    rule_id = rule.get("id")
    if not isinstance(rule_id, str) or not rule_id:
        raise ConsumerRulepackError(f"{label}: a rule has no id")
    where = f"{label}: rule {rule_id!r}"
    unknown = sorted(set(rule) - _ALLOWED_RULE_KEYS)
    if unknown:
        raise ConsumerRulepackError(
            f"{where} uses keys outside the allow-list: {unknown}"
        )
    if not rule_id.startswith(prefix) or len(rule_id) == len(prefix):
        raise ConsumerRulepackError(f"{where} is not namespaced under {prefix!r}")
    if rule_id in packaged:
        raise ConsumerRulepackError(f"{where} redefines an SDK packaged rule")
    paths = rule.get("paths")
    if not isinstance(paths, dict) or set(paths) - _PATH_KEYS:
        raise ConsumerRulepackError(
            f"{where} must declare paths with only include and exclude"
        )
    include = _string_list(paths.get("include"), f"{where} paths.include")
    if not include:
        raise ConsumerRulepackError(f"{where} paths.include must not be empty")
    exclude = _string_list(paths.get("exclude", []), f"{where} paths.exclude")
    metadata = rule.get("metadata")
    l9 = metadata.get("l9") if isinstance(metadata, dict) else None
    canonical = l9.get("canonical_rule_id") if isinstance(l9, dict) else None
    if not isinstance(canonical, str) or not canonical.startswith(canonical_prefix):
        raise ConsumerRulepackError(
            f"{where} must carry metadata.l9.canonical_rule_id starting "
            f"{canonical_prefix!r}"
        )
    if not _CANONICAL_NAME.fullmatch(canonical[len(canonical_prefix) :]):
        raise ConsumerRulepackError(
            f"{where} canonical_rule_id {canonical!r} is malformed"
        )
    languages = _string_list(rule.get("languages"), f"{where} languages")
    if not languages:
        raise ConsumerRulepackError(f"{where} languages must not be empty")
    return ConsumerRule(
        rule_id=rule_id,
        canonical_rule_id=canonical,
        languages=languages,
        include=include,
        exclude=exclude,
    )


def load_consumer_declaration(root: Path) -> ConsumerDeclaration | None:
    """Load and validate ``root``'s declaration; ``None`` when there is none.

    Raises :class:`ConsumerRulepackError` on any violation. Nothing is run.
    """
    root = root.resolve()
    declaration_path = root / CONSUMER_DECLARATION_PATH
    if not declaration_path.exists() and not declaration_path.is_symlink():
        return None
    _relative_file(root, CONSUMER_DECLARATION_PATH, "declaration")
    document = _load_yaml(declaration_path, CONSUMER_DECLARATION_PATH)
    if not isinstance(document, dict):
        raise ConsumerRulepackError(f"{CONSUMER_DECLARATION_PATH} must be a mapping")
    unknown = sorted(set(document) - _DECLARATION_KEYS)
    if unknown:
        raise ConsumerRulepackError(f"declaration has unknown keys: {unknown}")
    if document.get("schema") != CONSUMER_DECLARATION_SCHEMA:
        raise ConsumerRulepackError(
            f"declaration schema must be {CONSUMER_DECLARATION_SCHEMA}"
        )
    owner = document.get("owner")
    if not isinstance(owner, str) or not _OWNER.fullmatch(owner):
        raise ConsumerRulepackError("declaration owner must be <owner>/<repository>")
    prefix = document.get("rule_id_prefix", DEFAULT_RULE_ID_PREFIX)
    if not isinstance(prefix, str) or not _PREFIX.fullmatch(prefix):
        raise ConsumerRulepackError(
            "rule_id_prefix must be a lower-case token ending in '.'"
        )
    listed = _string_list(document.get("rule_files"), "rule_files")
    if not listed or len(listed) > MAX_RULE_FILES:
        raise ConsumerRulepackError(
            f"rule_files must list between 1 and {MAX_RULE_FILES} files"
        )
    if len(set(listed)) != len(listed):
        raise ConsumerRulepackError("rule_files lists a file twice")

    canonical_prefix = consumer_canonical_prefix(owner)
    packaged = packaged_rule_ids()
    files: list[ConsumerRuleFile] = []
    rules: list[ConsumerRule] = []
    seen_ids: dict[str, str] = {}
    seen_canonical: dict[str, str] = {}
    for value in sorted(listed):
        relative, path = _relative_file(root, value, "rule file")
        content = _load_yaml(path, relative)
        if not isinstance(content, dict) or set(content) != {"rules"}:
            raise ConsumerRulepackError(
                f"{relative}: a consumer rule file holds exactly one key, 'rules'"
            )
        entries = content["rules"]
        if not isinstance(entries, list) or not entries:
            raise ConsumerRulepackError(
                f"{relative}: expected a non-empty 'rules' list"
            )
        file_ids = []
        for entry in entries:
            rule = _validate_rule(
                entry,
                label=relative,
                prefix=prefix,
                canonical_prefix=canonical_prefix,
                packaged=packaged,
            )
            if rule.rule_id in seen_ids:
                raise ConsumerRulepackError(
                    f"rule {rule.rule_id!r} is defined in both "
                    f"{seen_ids[rule.rule_id]} and {relative}"
                )
            if rule.canonical_rule_id in seen_canonical:
                raise ConsumerRulepackError(
                    f"canonical_rule_id {rule.canonical_rule_id!r} is used by both "
                    f"{seen_canonical[rule.canonical_rule_id]} and {rule.rule_id!r}"
                )
            seen_ids[rule.rule_id] = relative
            seen_canonical[rule.canonical_rule_id] = rule.rule_id
            rules.append(rule)
            file_ids.append(rule.rule_id)
        files.append(
            ConsumerRuleFile(
                path=relative,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                rule_ids=tuple(sorted(file_ids)),
            )
        )
        if len(rules) > MAX_RULES:
            raise ConsumerRulepackError(
                f"a declaration admits at most {MAX_RULES} rules"
            )
    return ConsumerDeclaration(
        owner=owner,
        path=CONSUMER_DECLARATION_PATH,
        sha256=hashlib.sha256(declaration_path.read_bytes()).hexdigest(),
        rule_id_prefix=prefix,
        rule_files=tuple(files),
        rules=tuple(sorted(rules, key=lambda item: item.rule_id)),
    )


__all__ = [
    "CONSUMER_DECLARATION_PATH",
    "CONSUMER_DECLARATION_SCHEMA",
    "CONSUMER_EVIDENCE_SCHEMA",
    "CONSUMER_EVIDENCE_SCHEMA_VERSION",
    "ConsumerDeclaration",
    "ConsumerRule",
    "ConsumerRuleFile",
    "ConsumerRulepackError",
    "consumer_canonical_prefix",
    "consumer_target_name",
    "load_consumer_declaration",
    "packaged_rule_ids",
]
