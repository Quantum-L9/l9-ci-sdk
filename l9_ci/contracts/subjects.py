"""Reasons that name their subjects (L9-SIGNAL-001, ADR 0025).

Every failure, incomplete or unresolved reason the SDK emits names what it is
about, so a remediation agent can act without re-running: paths, rule ID plus
``path:line`` per finding, provider IDs with their error text. Subjects are
sorted, de-duplicated and capped at :data:`SUBJECT_CAP`; the rest is counted as
``+N more``. A reason without a subject cannot be built.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

SUBJECT_CAP = 20
_TEXT_CAP = 300
_ABSOLUTE_PATH = re.compile(r"(?<![\w.])(?:/|[A-Za-z]:[\\/])[^\s'\":,;()]+")


def strip_absolute_paths(text: str) -> str:
    """Shorten every absolute path in ``text`` to ``…/<name>``.

    Canonical artifacts never carry absolute paths (AGENTS.md), but tool
    output that names a failure often does; the file name stays as the subject.
    """
    return _ABSOLUTE_PATH.sub(
        lambda match: (
            "…/" + (re.split(r"[\\/]", match.group(0).rstrip("/\\"))[-1] or ".")
        ),
        text,
    )


def display_path(path: Path, root: Path) -> str:
    """``path`` relative to ``root``, else ``…/<name>``: never an absolute path."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return f"…/{path.name}"


def text_tail(text: str, cap: int = _TEXT_CAP) -> str:
    """The last non-empty line of ``text`` without absolute paths, or ``no output``."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "no output"
    tail = strip_absolute_paths(lines[-1])
    return tail if len(tail) <= cap else tail[: cap - 1] + "…"


def cap_subjects(
    subjects: Iterable[str], cap: int = SUBJECT_CAP
) -> tuple[tuple[str, ...], int]:
    """The first ``cap`` sorted, unique, non-empty subjects and how many were omitted."""
    unique = sorted({item.strip() for item in subjects if item and item.strip()})
    return tuple(unique[:cap]), max(0, len(unique) - cap)


def format_subjects(subjects: Iterable[str], cap: int = SUBJECT_CAP) -> str:
    """``a, b, c`` or ``a, b, c (+N more)``; refuses an empty list."""
    shown, omitted = cap_subjects(subjects, cap)
    if not shown:
        raise ValueError("a reason must name at least one subject")
    text = ", ".join(shown)
    return f"{text} (+{omitted} more)" if omitted else text


def subject_reason(text: str, subjects: Iterable[str], cap: int = SUBJECT_CAP) -> str:
    """``<text>: <subjects>``; refuses an empty text or subject list."""
    if not text.strip():
        raise ValueError("a reason must have text")
    return f"{text}: {format_subjects(subjects, cap)}"


__all__ = [
    "SUBJECT_CAP",
    "cap_subjects",
    "display_path",
    "format_subjects",
    "strip_absolute_paths",
    "subject_reason",
    "text_tail",
]
