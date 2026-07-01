from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from l9_ci.utils.files import FileMode, iter_files

MESSAGE = "PacketEnvelope has been superseded by TransportPacket."

ALLOWED_DEFINITION_FILES = {
    "engine/packet/packet_envelope.py",
    "l9_core/models.py",
}

DEFAULT_EXCLUDE_PATHS = [
    "l9_ci/scanners/packet_envelope.py",
]

PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"from\s+[\w.]+\s+import\s+.*\bPacketEnvelope\b"), "PE-001", "Import of PacketEnvelope"),
    (re.compile(r"import\s+.*\bPacketEnvelope\b"), "PE-002", "Import of PacketEnvelope"),
    (re.compile(r":\s*PacketEnvelope\b"), "PE-003", "Type annotation using PacketEnvelope"),
    (re.compile(r"->\s*PacketEnvelope\b"), "PE-004", "Return type using PacketEnvelope"),
    (re.compile(r"\bPacketEnvelope\s*\("), "PE-005", "Instantiation of PacketEnvelope"),
    (re.compile(r"\bPacketEnvelope\s*\."), "PE-006", "Method/attribute access on PacketEnvelope"),
    (re.compile(r"(?<!class\s)\bPacketEnvelope\b(?!\s*[:\(])"), "PE-007", "Reference to PacketEnvelope"),
]
CLASS_DEFINITION_PATTERN = re.compile(r"^\s*class\s+PacketEnvelope\s*[\(:]")

@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    code: str
    message: str


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def is_allowed_definition_file(path: Path, root: Path) -> bool:
    return _rel(path, root) in ALLOWED_DEFINITION_FILES


def collect_python_files(
    paths: list[Path],
    exclude: set[str] | list[str] | None = None,
    *,
    file_mode: FileMode = "auto",
) -> list[Path]:
    return iter_files(
        paths,
        suffixes={".py"},
        exclude=[*DEFAULT_EXCLUDE_PATHS, *list(exclude or [])],
        file_mode=file_mode,
    )


def scan_file(file_path: Path, root: Path, exclude: set[str] | None = None) -> list[Violation]:
    # ``exclude`` is accepted for backward compatibility; collection owns exclusion.
    if exclude:
        rel = _rel(file_path, root)
        if any(rel == pattern or rel.endswith(pattern) for pattern in exclude):
            return []
    text = file_path.read_text(encoding="utf-8", errors="replace")
    rel = _rel(file_path, root)
    is_definition = is_allowed_definition_file(file_path, root)
    violations: list[Violation] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped[:3] in ('"""', chr(39) * 3):
            continue
        if "PacketEnvelope" in line and ('"PacketEnvelope' in line or "'PacketEnvelope" in line):
            continue
        if CLASS_DEFINITION_PATTERN.match(line):
            if not is_definition:
                violations.append(Violation(rel, lineno, "PE-DEF", "Class definition of PacketEnvelope is not allowed here"))
            continue
        if is_definition:
            continue
        for pattern, code, msg in PATTERNS:
            if pattern.search(line):
                violations.append(Violation(rel, lineno, code, msg))
                break
    return violations


def scan(
    paths: list[Path],
    root: Path | None = None,
    exclude: list[str] | None = None,
    file_mode: FileMode = "auto",
) -> list[Violation]:
    root = root or Path.cwd()
    exclude_set = set(exclude or [])
    violations: list[Violation] = []
    for path in collect_python_files(paths, exclude_set, file_mode=file_mode):
        violations.extend(scan_file(path, root, exclude_set))
    return violations


def format_violations(violations: list[Violation]) -> str:
    lines = [f"ERROR: PacketEnvelope PROHIBITED - {MESSAGE}", ""]
    for v in violations:
        lines.append(f"[{v.code}] {v.file}:{v.line} - {v.message}")
    lines.append(f"Total: {len(violations)} violation(s).")
    return "\n".join(lines)
