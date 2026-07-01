from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from l9_ci.utils.files import FileMode, iter_files, scan_anchor

@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    module: str
    message: str


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _normalize_prefix(prefix: str, root: Path) -> str:
    """Make a path prefix comparable to root-relative file paths, accepting both
    root-relative and absolute prefixes (absolute ones re-expressed vs the anchor)."""
    candidate = Path(prefix)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return prefix.replace("\\", "/")
    return prefix.replace("\\", "/")


def scan(
    paths: list[Path],
    module: str,
    path_prefix: str | None = None,
    allow: list[str] | None = None,
    *,
    exclude: list[str] | None = None,
    file_mode: FileMode = "auto",
) -> list[Violation]:
    allow_set = {a.replace("\\", "/") for a in (allow or [])}
    root = scan_anchor(paths)
    prefix = _normalize_prefix(path_prefix, root) if path_prefix else None
    violations: list[Violation] = []
    needles = [f"import {module}", f"from {module} import"]
    for path in iter_files(paths, suffixes={".py"}, exclude=exclude or [], file_mode=file_mode):
        rel = _rel(path, root)
        if prefix and not rel.startswith(prefix.rstrip("/") + "/") and rel != prefix:
            continue
        if rel in allow_set:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if any(needle in stripped for needle in needles):
                violations.append(Violation(rel, lineno, module, f"Banned import: {module}"))
    return violations
