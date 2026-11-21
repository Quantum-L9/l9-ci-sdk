"""Git-backed repository inspection."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Git hooks (and some CI wrappers) export GIT_DIR / GIT_WORK_TREE. Those override
# `git -C <root>` and make inspection of an unrelated directory report the hook's
# repository instead. Strip them so `-C` is authoritative.
_GIT_ENV_OVERRIDE_KEYS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


def _git_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in _GIT_ENV_OVERRIDE_KEYS:
        env.pop(key, None)
    return env


@dataclass(frozen=True, slots=True)
class GitRepositoryState:
    revision: str
    dirty: bool
    tracked_files: tuple[str, ...]
    untracked_files: tuple[str, ...]

    @property
    def all_files(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.tracked_files) | set(self.untracked_files)))


def inspect_git_repository(
    root: Path,
    *,
    include_untracked: bool = True,
) -> GitRepositoryState:
    root = root.resolve()
    revision = _run_git(root, "rev-parse", "HEAD").strip()
    status_output = _run_git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    tracked_output = _run_git(
        root,
        "ls-files",
        "-z",
    )
    tracked_files = tuple(sorted(item for item in tracked_output.split("\0") if item))
    untracked_files: tuple[str, ...] = ()
    if include_untracked:
        untracked_files = tuple(
            sorted(
                line[3:]
                for line in status_output.splitlines()
                if line.startswith("?? ")
            )
        )
    return GitRepositoryState(
        revision=revision,
        dirty=bool(status_output.strip()),
        tracked_files=tracked_files,
        untracked_files=untracked_files,
    )


def is_git_repository(root: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
        env=_git_subprocess_env(),
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def resolve_commit(root: Path, revision: str) -> str | None:
    """The full commit ID ``revision`` names in ``root``'s repository, or ``None``.

    ``None`` when the object is absent (an unknown hash, or a shallow clone that
    does not hold it) or is not a commit.
    """
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            f"{revision}^{{commit}}",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=_git_subprocess_env(),
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def tracked_changes(root: Path) -> tuple[str, ...]:
    """Tracked paths whose working-tree or index content differs from HEAD."""
    output = _run_git(root, "status", "--porcelain=v1", "--untracked-files=no")
    return tuple(sorted(line[3:] for line in output.splitlines() if line.strip()))


def _run_git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=_git_subprocess_env(),
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"git command failed: {' '.join(arguments)}: {message}")
    return completed.stdout
