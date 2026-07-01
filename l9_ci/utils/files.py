"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
layer: [utils, file-enumeration]
tags: [L9_CI, git-aware, scanner-primitive]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
import tomllib
from pathlib import Path
from typing import Literal

FileMode = Literal["auto", "git_tracked", "working_tree", "filesystem"]

DEFAULT_FALLBACK_EXCLUDES = (
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "build",
    "dist",
    "node_modules",
    "site-packages",
)


def iter_files(
    roots: list[Path],
    suffixes: set[str] | None = None,
    exclude: list[str] | None = None,
    file_mode: FileMode = "auto",
) -> list[Path]:
    """Return active repository files for scanners.

    Authority order:
    1. ``git ls-files`` for deterministic CI scans.
    2. ``git ls-files`` plus untracked non-ignored files for local working-tree scans.
    3. ``os.walk`` fallback for bootstrap directories or archives without ``.git``.

    Exclusions are centralized here so scanner modules do not carry language-specific
    path skip lists. ``.gitignore`` is honored by Git modes directly and is parsed for
    filesystem fallback. ``pyproject.toml`` may also provide ``[tool.l9-ci].exclude``.
    CLI ``--exclude`` patterns are applied last.
    """
    normalized_roots = [Path(r) for r in roots] or [Path(".")]
    # Git-awareness, config, and gitignore resolution are anchored to the path
    # being scanned rather than the process working directory. When the CLI is
    # invoked from a repository root scanning ``.`` these coincide, but scanning
    # a path outside the current repo (e.g. a temp directory) must not silently
    # fall back to ``git ls-files`` of an unrelated repo and find nothing.
    anchor = _scan_anchor(normalized_roots)
    configured_excludes = _load_config_excludes(anchor)
    all_excludes = [*configured_excludes, *(exclude or [])]
    resolved_mode: FileMode = _resolve_mode(file_mode, anchor)

    if resolved_mode in {"git_tracked", "working_tree"}:
        repo_root = _git_root(anchor)
        if repo_root is not None:
            files = _git_files(repo_root, include_untracked=resolved_mode == "working_tree")
            files = _filter_to_roots(files, normalized_roots, repo_root)
            return _finalize(files, suffixes, all_excludes, repo_root)
        if file_mode != "auto":
            raise RuntimeError(f"file mode {file_mode!r} requested, but no Git repository was found")

    fallback_files = _filesystem_files(normalized_roots, anchor)
    return _finalize(fallback_files, suffixes, all_excludes, anchor)


def _scan_anchor(roots: list[Path]) -> Path:
    """Resolve the directory that scan context (git repo, config, gitignore) is
    keyed to: the first root when it is a directory, otherwise its parent."""
    first = roots[0]
    base = first if first.is_absolute() else (Path.cwd() / first)
    base = base.resolve()
    return base if base.is_dir() else base.parent


def _resolve_mode(file_mode: FileMode, cwd: Path) -> FileMode:
    if file_mode != "auto":
        return file_mode
    return "git_tracked" if _git_root(cwd) is not None else "filesystem"


def _git_root(cwd: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    value = proc.stdout.strip()
    return Path(value).resolve() if value else None


def _git_files(repo_root: Path, *, include_untracked: bool) -> list[Path]:
    tracked = _run_git_lines(repo_root, ["git", "ls-files", "-z"])
    rels = list(tracked)
    if include_untracked:
        rels.extend(_run_git_lines(repo_root, ["git", "ls-files", "--others", "--exclude-standard", "-z"]))
    return [(repo_root / rel).resolve() for rel in rels if rel and (repo_root / rel).is_file()]


def _run_git_lines(repo_root: Path, command: list[str]) -> list[str]:
    proc = subprocess.run(
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    raw = proc.stdout.decode("utf-8", errors="replace")
    return [part for part in raw.split("\0") if part]


def _filter_to_roots(files: list[Path], roots: list[Path], repo_root: Path) -> list[Path]:
    resolved_roots = [_resolve_root(root, repo_root) for root in roots]
    selected: list[Path] = []
    for file_path in files:
        for root in resolved_roots:
            if root.is_file() and file_path == root.resolve():
                selected.append(file_path)
                break
            if root.is_dir() and _is_relative_to(file_path, root.resolve()):
                selected.append(file_path)
                break
    return selected


def _resolve_root(root: Path, repo_root: Path) -> Path:
    if root.is_absolute():
        return root
    cwd_candidate = (Path.cwd() / root).resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    return (repo_root / root).resolve()


def _filesystem_files(roots: list[Path], cwd: Path) -> list[Path]:
    gitignore_patterns = _load_gitignore_patterns(cwd)
    files: list[Path] = []
    for root in roots:
        base = root if root.is_absolute() else cwd / root
        if base.is_file():
            files.append(base.resolve())
            continue
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            current = Path(dirpath)
            dirnames[:] = [
                d for d in dirnames if not _fallback_excluded(current / d, cwd, gitignore_patterns)
            ]
            for filename in filenames:
                file_path = (current / filename).resolve()
                if not _fallback_excluded(file_path, cwd, gitignore_patterns):
                    files.append(file_path)
    return files


def _fallback_excluded(path: Path, root: Path, gitignore_patterns: list[str]) -> bool:
    rel = _rel_text(path, root)
    if any(part in DEFAULT_FALLBACK_EXCLUDES for part in path.parts):
        return True
    return _matches_any(rel, gitignore_patterns)


def _finalize(
    files: list[Path],
    suffixes: set[str] | None,
    exclude: list[str],
    root: Path,
) -> list[Path]:
    unique = sorted({path.resolve() for path in files if path.is_file()}, key=lambda p: _rel_text(p, root))
    output: list[Path] = []
    for path in unique:
        if suffixes and path.suffix not in suffixes:
            continue
        rel = _rel_text(path, root)
        if _matches_any(rel, exclude):
            continue
        output.append(path)
    return output


def _load_config_excludes(cwd: Path) -> list[str]:
    config_path = _find_upwards(cwd, "pyproject.toml")
    if config_path is None:
        return []
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    config = data.get("tool", {}).get("l9-ci", {})
    excludes = config.get("exclude", [])
    if isinstance(excludes, list):
        return [str(item) for item in excludes]
    return []


def _load_gitignore_patterns(cwd: Path) -> list[str]:
    gitignore = _find_upwards(cwd, ".gitignore")
    if gitignore is None:
        return []
    patterns: list[str] = []
    for raw in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        patterns.append(line)
    return patterns


def _find_upwards(start: Path, filename: str) -> Path | None:
    current = start.resolve()
    candidates = [current, *current.parents]
    for parent in candidates:
        path = parent / filename
        if path.is_file():
            return path
    return None


def _matches_any(rel: str, patterns: list[str]) -> bool:
    normalized = rel.replace("\\", "/")
    for pattern in patterns:
        clean = pattern.strip().replace("\\", "/")
        if not clean:
            continue
        if normalized == clean or normalized.endswith(clean):
            return True
        if clean.endswith("/") and normalized.startswith(clean.rstrip("/") + "/"):
            return True
        if "/" not in clean and any(part == clean for part in normalized.split("/")):
            return True
        if fnmatch.fnmatch(normalized, clean):
            return True
    return False


def _rel_text(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
