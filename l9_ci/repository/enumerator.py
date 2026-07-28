"""Repository file enumeration."""

from __future__ import annotations
from pathlib import Path
from typing import Iterable

_DEFAULT_EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
}


def enumerate_repository_files(
    root: Path,
    *,
    include_untracked: bool = True,
    excluded_directories: Iterable[str] = (),
) -> tuple[str, ...]:
    """Enumerate deterministic repository-relative files.
    The generic fallback is filesystem-based. Git-aware enumeration is
    provided by ``l9_ci.repository.git``.
    """
    root = root.resolve()
    if not root.exists():
        raise ValueError(f"repository root does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")
    excluded = _DEFAULT_EXCLUDED_DIRECTORIES | set(excluded_directories)
    files: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        files.append(relative.as_posix())
    del include_untracked
    return tuple(sorted(files))
