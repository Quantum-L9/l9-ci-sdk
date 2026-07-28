"""Deterministic repository snapshot identity."""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from .enumerator import enumerate_repository_files
from .git import inspect_git_repository, is_git_repository


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    snapshot_id: str
    revision: str | None
    dirty: bool
    files: tuple[str, ...]
    file_count: int
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "revision": self.revision,
            "dirty": self.dirty,
            "files": list(self.files),
            "file_count": self.file_count,
            "source": self.source,
        }


def build_repository_snapshot(
    root: Path,
    *,
    include_untracked: bool = True,
) -> RepositorySnapshot:
    root = root.resolve()
    if is_git_repository(root):
        state = inspect_git_repository(
            root,
            include_untracked=include_untracked,
        )
        files = state.all_files
        revision = state.revision
        dirty = state.dirty
        source = "git"
    else:
        files = enumerate_repository_files(
            root,
            include_untracked=include_untracked,
        )
        revision = None
        dirty = False
        source = "filesystem"
    digest = _snapshot_digest(
        revision=revision,
        dirty=dirty,
        files=files,
    )
    return RepositorySnapshot(
        snapshot_id=f"snapshot_{digest}",
        revision=revision,
        dirty=dirty,
        files=files,
        file_count=len(files),
        source=source,
    )


def _snapshot_digest(
    *,
    revision: str | None,
    dirty: bool,
    files: tuple[str, ...],
) -> str:
    payload = {
        "revision": revision,
        "dirty": dirty,
        "files": list(files),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
