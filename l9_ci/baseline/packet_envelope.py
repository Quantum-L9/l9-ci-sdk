"""PacketEnvelope migration-debt scanner.

PacketEnvelope is deprecated and superseded by TransportPacket (see
the TRANSPORT_PACKET_SPEC). Every remaining reference to
PacketEnvelope in production code is migration debt that must be
ledgered with a machine-evaluable removal condition
(``migrated-to:TransportPacket``).

The scanner walks Python files at the AST level and reports:

- imports (``import x.PacketEnvelope`` / ``from m import PacketEnvelope``)
- attribute or name references (constructor calls, isinstance checks,
  annotations, runtime references)
- string-literal type annotations that mention PacketEnvelope

Excluded by design:

- documentation files (non-Python)
- the deprecation declaration site itself (a module can be listed in
  ``declaration_paths`` so the class definition and its ``__all__``
  export do not count as debt)
- comments (invisible at AST level)

Detection is purely syntactic and deterministic. No LLM participates.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from .comparison import ObservedFinding
from .fingerprint import scanner_finding_fingerprint

PACKET_ENVELOPE_GATE = "pre-commit/packet-envelope-prohibited"
PACKET_ENVELOPE_RULE = "packet-envelope-prohibited"
_TARGET = "PacketEnvelope"

_DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "docs",
    }
)


@dataclass(frozen=True, slots=True)
class PacketEnvelopeUsage:
    """A single AST-level PacketEnvelope reference."""

    path: str
    usage_kind: str
    context: str

    @property
    def normalized(self) -> str:
        return f"{self.usage_kind}:{self.context}"


def _iter_python_files(root: Path, excluded_dirs: frozenset[str]) -> Iterator[Path]:
    for path in sorted(root.rglob("*.py")):
        relative_parts = path.relative_to(root).parts
        if any(part in excluded_dirs for part in relative_parts[:-1]):
            continue
        yield path


class _PacketEnvelopeVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.usages: list[tuple[str, str]] = []
        self._class_stack: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if _TARGET in alias.name.split("."):
                self.usages.append(("import", alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            if alias.name == _TARGET or _TARGET in module.split("."):
                self.usages.append(("import-from", f"{module}.{alias.name}"))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == _TARGET:
            self.usages.append(("class-def", node.name))
        for base in node.bases:
            if _references_target(base):
                self.usages.append(("class-base", f"{node.name}({_TARGET})"))
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == _TARGET:
            self.usages.append(("name-ref", _TARGET))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == _TARGET:
            self.usages.append(("attr-ref", ast.unparse(node)))
            # Do not double-count the inner Name node.
            for child in ast.iter_child_nodes(node):
                if not isinstance(child, ast.Name) or child.id != _TARGET:
                    self.visit(child)
            return
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and _TARGET in node.value:
            # String annotations like "PacketEnvelope | None" are debt;
            # arbitrary prose strings mentioning the word are not. Keep
            # only plausible type-expression strings (short, no spaces
            # beyond type syntax).
            text = node.value.strip()
            if len(text) <= 120 and _looks_like_type_expression(text):
                self.usages.append(("string-annotation", text))
        self.generic_visit(node)


def _references_target(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == _TARGET
    if isinstance(node, ast.Attribute):
        return node.attr == _TARGET or _references_target(node.value)
    if isinstance(node, ast.Subscript):
        return _references_target(node.value)
    return False


def _looks_like_type_expression(text: str) -> bool:
    allowed = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.[]| ,'\""
    )
    return _TARGET in text and all(char in allowed for char in text)


def scan_file(path: Path, repository_root: Path) -> list[PacketEnvelopeUsage]:
    """Scan one Python file for PacketEnvelope references."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if _TARGET not in source:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Unparseable files are the lint gate's job; the scanner
        # reports a conservative single usage so debt cannot hide
        # behind a syntax error.
        return [
            PacketEnvelopeUsage(
                path=str(path.relative_to(repository_root)),
                usage_kind="unparseable-file",
                context="file mentions PacketEnvelope but failed to parse",
            )
        ]
    visitor = _PacketEnvelopeVisitor()
    visitor.visit(tree)
    relative = str(path.relative_to(repository_root))
    return [
        PacketEnvelopeUsage(path=relative, usage_kind=kind, context=context)
        for kind, context in visitor.usages
    ]


def scan_repository(
    repository_root: Path,
    *,
    declaration_paths: Iterable[str] = (),
    excluded_dirs: Iterable[str] = (),
) -> tuple[ObservedFinding, ...]:
    """Scan a repository tree and return deduplicated observed findings.

    Multiple identical usages within one file collapse into a single
    finding per (path, usage_kind, context) triple, with an occurrence
    count carried in attributes. ``declaration_paths`` are
    repository-relative Python files whose ``class-def`` and
    ``name-ref`` usages are the deprecation declaration itself and are
    not debt.
    """
    root = repository_root.resolve()
    declared = {str(Path(item)) for item in declaration_paths}
    excluded = _DEFAULT_EXCLUDED_DIRS | frozenset(excluded_dirs)

    counted: dict[tuple[str, str, str], int] = {}
    for file_path in _iter_python_files(root, excluded):
        for usage in scan_file(file_path, root):
            if usage.path in declared and usage.usage_kind in {
                "class-def",
                "name-ref",
                "string-annotation",
            }:
                continue
            key = (usage.path, usage.usage_kind, usage.context)
            counted[key] = counted.get(key, 0) + 1

    findings: list[ObservedFinding] = []
    for (path, usage_kind, context), count in sorted(counted.items()):
        normalized = f"{usage_kind}:{context}"
        fingerprint = scanner_finding_fingerprint(
            PACKET_ENVELOPE_RULE, path, normalized
        )
        findings.append(
            ObservedFinding(
                gate=PACKET_ENVELOPE_GATE,
                rule=PACKET_ENVELOPE_RULE,
                fingerprint=fingerprint,
                path=path,
                identity=f"{path}::{normalized}",
                message=(
                    f"PacketEnvelope {usage_kind} in {path}: {context} "
                    "(deprecated; migrate to TransportPacket)"
                ),
                attributes={"occurrences": count, "usage_kind": usage_kind},
            )
        )
    return tuple(findings)
