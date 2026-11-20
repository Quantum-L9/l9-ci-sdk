"""Reproducible, monotonic composition of the packaged Semgrep rulepacks.

An effective rulepack is the organization baseline for each selected language,
plus the language and framework packs whose selector matches, plus any
product configuration the caller is authorized to add. This module resolves
that composition to exact content: every file by SHA-256, every rule ID, and
one digest over the whole.

Two properties are enforced here and nowhere else (L9-CI-SDK-003):

* Monotonic. Nothing a caller passes can remove or replace a baseline rule.
  An exclusion that names a baseline rule is refused, and so is a product
  configuration that defines a rule ID the packaged rules already use.
* Honest about reproducibility. A registry label such as ``p/python`` names
  mutable remote content. It is recorded, and the composition is then marked
  not reproducible. A label never contributes to the appearance of a pin.

Selection is by fact. The caller names languages and frameworks, which it
takes from a capability inventory; this module never looks at a repository.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.resources
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import yaml

RULEPACKS_SCHEMA = "l9.semgrep-rulepacks/v1"
RULEPACK_COMPOSITION_PROTOCOL = "l9.semgrep-rulepack-composition/v1"
RULEPACK_COMPOSITION_SCHEMA_VERSION = "1.0.0"

_KINDS = ("baseline", "language", "framework")
_STATUSES = ("active", "candidate")
_KIND_ORDER = {kind: index for index, kind in enumerate(_KINDS)}


class RulepackCompositionError(ValueError):
    """The requested composition is refused or cannot be resolved."""


@dataclass(frozen=True, slots=True)
class RulepackDefinition:
    """One entry of the packaged rulepack registry."""

    pack_id: str
    kind: str
    status: str
    directory: str
    selector_key: str
    selector_value: str
    description: str


@dataclass(frozen=True, slots=True)
class ComposedFile:
    path: str
    sha256: str
    rule_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "rule_ids": list(self.rule_ids),
        }


@dataclass(frozen=True, slots=True)
class ComposedPack:
    pack_id: str
    kind: str
    status: str
    files: tuple[ComposedFile, ...]

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(sorted(rule for file in self.files for rule in file.rule_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "kind": self.kind,
            "status": self.status,
            "files": [file.to_dict() for file in self.files],
        }


@dataclass(frozen=True, slots=True)
class RulepackComposition:
    """One resolved composition.

    The record names content, never a location: no path on this machine is in
    ``to_dict`` or in ``content_digest``. To execute a composition, call
    :meth:`materialize`, which writes exactly the rules this record lists.
    The source directories are not exposed, because scanning them would also
    run any rule the composition excluded.
    """

    SDK_version: str
    languages: tuple[str, ...]
    frameworks: tuple[str, ...]
    packs: tuple[ComposedPack, ...]
    product_configs: tuple[ComposedFile, ...]
    excluded_rule_ids: tuple[str, ...]
    unpinned_sources: tuple[str, ...]
    rule_ids: tuple[str, ...]
    content_digest: str
    _sources: tuple[tuple[str, Path], ...] = field(repr=False, compare=False)
    schema: str = RULEPACK_COMPOSITION_PROTOCOL
    schema_version: str = RULEPACK_COMPOSITION_SCHEMA_VERSION

    @property
    def reproducible(self) -> bool:
        return not self.unpinned_sources

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "SDK_version": self.SDK_version,
            "languages": list(self.languages),
            "frameworks": list(self.frameworks),
            "packs": [pack.to_dict() for pack in self.packs],
            "product_configs": [item.to_dict() for item in self.product_configs],
            "excluded_rule_ids": list(self.excluded_rule_ids),
            "unpinned_sources": list(self.unpinned_sources),
            "reproducible": self.reproducible,
            "rule_ids": list(self.rule_ids),
            "content_digest": self.content_digest,
        }

    def materialize(self, destination: Path) -> tuple[Path, ...]:
        """Write exactly the composed rules into ``destination``.

        One file per composed source, in composition order. A file with no
        excluded rule is copied byte for byte. A file with an excluded rule is
        rewritten without it, and a file left with no rule is not written.
        Raises if ``destination`` is not empty, or if a source no longer has
        the content this composition recorded.
        """
        destination.mkdir(parents=True, exist_ok=True)
        if any(destination.iterdir()):
            raise RulepackCompositionError(
                f"materialize destination is not empty: {destination.name}"
            )
        recorded = {
            file.path: file.sha256
            for file in (
                *(file for pack in self.packs for file in pack.files),
                *self.product_configs,
            )
        }
        excluded = set(self.excluded_rule_ids)
        written: list[Path] = []
        for index, (label, source) in enumerate(self._sources):
            content = source.read_bytes()
            if hashlib.sha256(content).hexdigest() != recorded[label]:
                raise RulepackCompositionError(
                    f"{label} changed after it was composed; compose again"
                )
            name = "".join(
                character if character.isalnum() or character in "-." else "_"
                for character in label
            )
            target = destination / f"{index:03d}-{name}"
            document = yaml.safe_load(content.decode("utf-8"))
            kept = [rule for rule in document["rules"] if rule["id"] not in excluded]
            if not kept:
                continue
            if len(kept) == len(document["rules"]):
                target.write_bytes(content)
            else:
                target.write_text(
                    yaml.safe_dump({**document, "rules": kept}, sort_keys=False),
                    encoding="utf-8",
                )
            written.append(target)
        return tuple(written)


def _package_root() -> Path:
    return Path(str(importlib.resources.files(__package__)))


def rulepacks_path() -> Path:
    """Return the packaged rulepack registry; fail closed if it is missing."""
    resolved = _package_root() / "packs.yaml"
    if not resolved.is_file():
        raise FileNotFoundError(f"packaged rulepack registry not found: {resolved}")
    return resolved


@functools.lru_cache(maxsize=1)
def _load_registry() -> tuple[RulepackDefinition, ...]:
    document = yaml.safe_load(rulepacks_path().read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != RULEPACKS_SCHEMA:
        raise RulepackCompositionError(
            f"rulepack registry: expected schema {RULEPACKS_SCHEMA!r}"
        )
    raw = document.get("packs")
    if not isinstance(raw, dict) or not raw:
        raise RulepackCompositionError("rulepack registry: 'packs' must be non-empty")
    definitions = []
    for pack_id, body in raw.items():
        if not isinstance(body, dict):
            raise RulepackCompositionError(f"rulepack {pack_id!r} must be a mapping")
        kind = body.get("kind")
        status = body.get("status")
        selector = body.get("selector")
        directory = body.get("directory")
        if kind not in _KINDS:
            raise RulepackCompositionError(f"rulepack {pack_id!r}: bad kind {kind!r}")
        if status not in _STATUSES:
            raise RulepackCompositionError(
                f"rulepack {pack_id!r}: bad status {status!r}"
            )
        if kind == "baseline" and status != "active":
            raise RulepackCompositionError(
                f"rulepack {pack_id!r}: a baseline pack is always active"
            )
        if not isinstance(directory, str) or not directory:
            raise RulepackCompositionError(f"rulepack {pack_id!r}: missing directory")
        if not isinstance(selector, dict) or len(selector) != 1:
            raise RulepackCompositionError(
                f"rulepack {pack_id!r}: selector must name exactly one fact"
            )
        ((key, value),) = selector.items()
        expected_key = "framework" if kind == "framework" else "language"
        if key != expected_key or not isinstance(value, str) or not value:
            raise RulepackCompositionError(
                f"rulepack {pack_id!r}: a {kind} pack selects on {expected_key!r}"
            )
        definitions.append(
            RulepackDefinition(
                pack_id=str(pack_id),
                kind=kind,
                status=status,
                directory=directory,
                selector_key=key,
                selector_value=value,
                description=" ".join(str(body.get("description", "")).split()),
            )
        )
    return tuple(
        sorted(definitions, key=lambda item: (_KIND_ORDER[item.kind], item.pack_id))
    )


def rulepack_definitions() -> tuple[RulepackDefinition, ...]:
    """Return every packaged rulepack definition, in composition order."""
    return _load_registry()


def _rule_ids(path: Path, label: str) -> tuple[str, ...]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise RulepackCompositionError(
            f"{label}: rule file could not be read: {type(exc).__name__}"
        ) from exc
    rules = document.get("rules") if isinstance(document, dict) else None
    if not isinstance(rules, list) or not rules:
        raise RulepackCompositionError(f"{label}: expected a non-empty 'rules' list")
    identifiers = []
    for rule in rules:
        rule_id = rule.get("id") if isinstance(rule, dict) else None
        if not isinstance(rule_id, str) or not rule_id:
            raise RulepackCompositionError(f"{label}: a rule has no id")
        identifiers.append(rule_id)
    return tuple(sorted(identifiers))


def _composed_file(path: Path, label: str) -> ComposedFile:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RulepackCompositionError(
            f"{label}: rule file could not be read: {type(exc).__name__}"
        ) from exc
    return ComposedFile(path=label, sha256=digest, rule_ids=_rule_ids(path, label))


def _compose_pack(
    definition: RulepackDefinition,
) -> tuple[ComposedPack, tuple[tuple[str, Path], ...]]:
    directory = _package_root() / definition.directory
    files = sorted(directory.glob("*.yml")) if directory.is_dir() else []
    if not files:
        raise RulepackCompositionError(
            f"rulepack {definition.pack_id!r}: no rule file in {definition.directory!r}"
        )
    labelled = tuple((f"{definition.directory}/{path.name}", path) for path in files)
    composed = tuple(_composed_file(path, label) for label, path in labelled)
    return (
        ComposedPack(
            pack_id=definition.pack_id,
            kind=definition.kind,
            status=definition.status,
            files=composed,
        ),
        labelled,
    )


def _unique_sorted(values: Sequence[str], what: str) -> tuple[str, ...]:
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise RulepackCompositionError(f"{what} must be non-empty strings")
    return tuple(sorted(set(values)))


def compose_rulepack(
    *,
    languages: Sequence[str],
    frameworks: Sequence[str] = (),
    include_candidates: bool = False,
    product_configs: Sequence[Path] = (),
    registry_rulesets: Sequence[str] = (),
    excluded_rule_ids: Sequence[str] = (),
    SDK_version: str,
) -> RulepackComposition:
    """Resolve the effective rulepack for the named languages and frameworks.

    Raises :class:`RulepackCompositionError` rather than returning a weaker
    composition: for a language with no baseline pack, an unknown framework, a
    restriction that names a baseline rule or an unknown rule, a product
    configuration that redefines a packaged rule ID, or two sources that
    define the same rule ID.

    ``SDK_version`` is the producing SDK version, carried on the record as on
    every version-negotiated artifact. It is not part of ``content_digest``:
    the digest names the rules, whichever SDK build resolved them.
    """
    if not isinstance(SDK_version, str) or not SDK_version.strip():
        raise RulepackCompositionError("SDK_version must be a non-empty string")
    selected_languages = _unique_sorted(languages, "languages")
    selected_frameworks = _unique_sorted(frameworks, "frameworks")
    if not selected_languages and not selected_frameworks:
        raise RulepackCompositionError("nothing selected: name a language or framework")
    definitions = rulepack_definitions()

    baseline_languages = {
        item.selector_value for item in definitions if item.kind == "baseline"
    }
    for language in selected_languages:
        if language not in baseline_languages:
            raise RulepackCompositionError(
                f"no baseline rulepack is packaged for language {language!r}"
            )
    known_frameworks = {
        item.selector_value for item in definitions if item.kind == "framework"
    }
    for framework in selected_frameworks:
        if framework not in known_frameworks:
            raise RulepackCompositionError(
                f"no rulepack is packaged for framework {framework!r}"
            )

    packs: list[ComposedPack] = []
    sources: list[tuple[str, Path]] = []
    for definition in definitions:
        wanted = (
            selected_frameworks
            if definition.selector_key == "framework"
            else selected_languages
        )
        if definition.selector_value not in wanted:
            continue
        if definition.status == "candidate" and not include_candidates:
            continue
        pack, pack_sources = _compose_pack(definition)
        packs.append(pack)
        sources.extend(pack_sources)

    owner: dict[str, str] = {}
    for pack in packs:
        for file in pack.files:
            for rule_id in file.rule_ids:
                if rule_id in owner:
                    raise RulepackCompositionError(
                        f"rule ID {rule_id!r} is defined by both {owner[rule_id]} "
                        f"and {file.path}"
                    )
                owner[rule_id] = file.path
    baseline_rule_ids = {
        rule_id
        for pack in packs
        if pack.kind == "baseline"
        for rule_id in pack.rule_ids
    }

    # Order by name and then by content, so that two product files with the
    # same name in different directories compose identically whichever order
    # the caller passed them in. The label carries a content prefix for the
    # same reason: a bare file name would not tell them apart.
    resolved = sorted(
        (
            (
                config.name,
                _composed_file(config, f"product:{config.name}").sha256,
                config,
            )
            for config in product_configs
        ),
        key=lambda item: (item[0], item[1]),
    )
    products: list[ComposedFile] = []
    for name, sha256, config in resolved:
        composed = _composed_file(config, f"product:{sha256[:12]}:{name}")
        for rule_id in composed.rule_ids:
            if rule_id in baseline_rule_ids:
                raise RulepackCompositionError(
                    f"{composed.path} redefines the organization baseline rule "
                    f"{rule_id!r}; a subordinate rule cannot replace the baseline"
                )
            if rule_id in owner:
                raise RulepackCompositionError(
                    f"rule ID {rule_id!r} is defined by both {owner[rule_id]} "
                    f"and {composed.path}"
                )
            owner[rule_id] = composed.path
        products.append(composed)
        sources.append((composed.path, config))

    excluded = _unique_sorted(excluded_rule_ids, "excluded rule IDs")
    for rule_id in excluded:
        if rule_id in baseline_rule_ids:
            raise RulepackCompositionError(
                f"cannot exclude {rule_id!r}: it is an organization baseline rule, "
                "and a restriction cannot suppress the baseline"
            )
        if rule_id not in owner:
            raise RulepackCompositionError(
                f"cannot exclude {rule_id!r}: no composed source defines it"
            )

    unpinned = _unique_sorted(registry_rulesets, "registry rulesets")
    rule_ids = tuple(sorted(rule for rule in owner if rule not in set(excluded)))
    identity = {
        "packs": [pack.to_dict() for pack in packs],
        "product_configs": [item.to_dict() for item in products],
        "excluded_rule_ids": list(excluded),
        "unpinned_sources": list(unpinned),
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return RulepackComposition(
        SDK_version=SDK_version,
        languages=selected_languages,
        frameworks=selected_frameworks,
        packs=tuple(packs),
        product_configs=tuple(products),
        excluded_rule_ids=excluded,
        unpinned_sources=unpinned,
        rule_ids=rule_ids,
        content_digest=f"sha256:{digest}",
        _sources=tuple(sources),
    )
