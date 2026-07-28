"""Deterministic repository manifest generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .enumerator import enumerate_repository_files
from .git import inspect_git_repository, is_git_repository

DEFAULT_MANIFEST_PATH = Path("MANIFEST.md")
_DEFAULT_EXCLUDED_PATHS = {
    DEFAULT_MANIFEST_PATH.as_posix(),
}


@dataclass(frozen=True, slots=True)
class RepositoryManifest:
    """Canonical repository file inventory."""

    files: tuple[str, ...]

    @property
    def file_count(self) -> int:
        return len(self.files)

    def render_markdown(self) -> str:
        lines = [
            "# Consolidated Manifest",
            "",
            f"Files: {self.file_count}",
            "",
            "## Contents",
            "",
        ]
        lines.extend(f"- `{path}`" for path in self.files)
        return "\n".join(lines) + "\n"


def build_repository_manifest(
    root: Path,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    include_untracked: bool = True,
    excluded_paths: Iterable[str] = (),
    excluded_directories: Iterable[str] = (),
) -> RepositoryManifest:
    """Build a deterministic inventory from repository truth.

    The generated manifest excludes itself so generation is idempotent and does
    not create a self-referential digest problem.
    """

    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")

    if manifest_path.is_absolute():
        try:
            relative_manifest = manifest_path.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("manifest path must be inside repository root") from exc
    else:
        relative_manifest = manifest_path.as_posix()

    excluded = _DEFAULT_EXCLUDED_PATHS | {relative_manifest} | set(excluded_paths)

    if is_git_repository(root):
        state = inspect_git_repository(root, include_untracked=include_untracked)
        candidates = state.all_files
    else:
        candidates = enumerate_repository_files(
            root,
            include_untracked=include_untracked,
            excluded_directories=excluded_directories,
        )

    excluded_directory_names = set(excluded_directories)
    files = tuple(
        sorted(
            path
            for path in candidates
            if path not in excluded
            and not any(part in excluded_directory_names for part in Path(path).parts)
        )
    )
    return RepositoryManifest(files=files)


def write_repository_manifest(
    root: Path,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    include_untracked: bool = True,
    excluded_paths: Iterable[str] = (),
    excluded_directories: Iterable[str] = (),
) -> tuple[RepositoryManifest, bool]:
    """Atomically write the canonical manifest and report whether it changed."""

    root = root.resolve()
    output = manifest_path if manifest_path.is_absolute() else root / manifest_path
    manifest = build_repository_manifest(
        root,
        manifest_path=output,
        include_untracked=include_untracked,
        excluded_paths=excluded_paths,
        excluded_directories=excluded_directories,
    )
    rendered = manifest.render_markdown()
    previous = output.read_text(encoding="utf-8") if output.exists() else None
    changed = previous != rendered
    if changed:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp")
        temporary.write_text(rendered, encoding="utf-8", newline="\n")
        temporary.replace(output)
    return manifest, changed
