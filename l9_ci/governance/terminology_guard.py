from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from l9_ci.utils.files import FileMode, iter_files, scan_anchor

DEFAULT_PATTERNS = {
    r"\bprint\(": "Use structured logging instead of print().",
    r"\bOptional\[": "Use T | None.",
    r"\bList\[": "Use list[T].",
    r"\bDict\[": "Use dict[K, V].",
}

@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    pattern: str
    message: str


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _normalize_prefix(prefix: str, root: Path) -> str:
    """Make an ``include`` prefix comparable to root-relative file paths.

    Accepts both root-relative prefixes (``"engine"``) and absolute prefixes
    (``"/abs/engine"``); absolute prefixes are re-expressed relative to the scan
    anchor so matching stays correct regardless of the caller's convention.
    """
    candidate = Path(prefix)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return prefix.replace("\\", "/")
    return prefix.replace("\\", "/")


def collect(
    paths: list[Path],
    include_prefixes: list[str] | None = None,
    *,
    exclude: list[str] | None = None,
    file_mode: FileMode = "auto",
) -> list[Path]:
    include_prefixes = include_prefixes or []
    files = iter_files(paths, suffixes={".py"}, exclude=exclude or [], file_mode=file_mode)
    if not include_prefixes:
        return files
    root = scan_anchor(paths)
    normalized = [_normalize_prefix(prefix, root) for prefix in include_prefixes]
    selected: list[Path] = []
    for path in files:
        rel = _rel(path, root)
        if any(rel.startswith(prefix.rstrip("/") + "/") or rel == prefix for prefix in normalized):
            selected.append(path)
    return selected


def scan(
    paths: list[Path],
    include_prefixes: list[str] | None = None,
    patterns: dict[str, str] | None = None,
    *,
    exclude: list[str] | None = None,
    file_mode: FileMode = "auto",
) -> list[Violation]:
    patterns = patterns or DEFAULT_PATTERNS
    violations: list[Violation] = []
    root = scan_anchor(paths)
    for path in collect(paths, include_prefixes, exclude=exclude, file_mode=file_mode):
        rel = _rel(path, root)
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pattern, message in patterns.items():
                if re.search(pattern, line):
                    violations.append(Violation(rel, lineno, pattern, message))
    return violations
