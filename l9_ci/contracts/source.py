"""Canonical source-location contracts."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


def normalize_repository_path(path: str) -> str:
    """Normalize and validate a repository-relative POSIX path.
    Absolute paths, empty paths, and traversal paths are rejected.
    """
    raw = path.replace("\\", "/").strip()
    if not raw:
        raise ValueError("source path must not be empty")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute():
        raise ValueError("source path must be repository-relative")
    if any(part == ".." for part in candidate.parts):
        raise ValueError("source path must not contain traversal segments")
    normalized = candidate.as_posix()
    if normalized in {"", "."}:
        raise ValueError("source path must identify a repository file")
    return normalized


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A normalized repository-relative source location."""

    normalized_path: str
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    byte_start: int | None = None
    byte_end: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "normalized_path",
            normalize_repository_path(self.normalized_path),
        )
        for field_name in (
            "start_line",
            "start_column",
            "end_line",
            "end_column",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 1:
                raise ValueError(f"{field_name} must be positive")
        for field_name in ("byte_start", "byte_end"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if (
            self.start_line is not None
            and self.end_line is not None
            and self.end_line < self.start_line
        ):
            raise ValueError("end_line must be greater than or equal to start_line")
        if (
            self.byte_start is not None
            and self.byte_end is not None
            and self.byte_end < self.byte_start
        ):
            raise ValueError("byte_end must be greater than or equal to byte_start")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible representation."""
        payload: dict[str, Any] = {
            "normalized_path": self.normalized_path,
        }
        for key in (
            "start_line",
            "start_column",
            "end_line",
            "end_column",
            "byte_start",
            "byte_end",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceLocation":
        """Create a source location from canonical JSON-compatible data."""
        return cls(
            normalized_path=str(payload["normalized_path"]),
            start_line=payload.get("start_line"),
            start_column=payload.get("start_column"),
            end_line=payload.get("end_line"),
            end_column=payload.get("end_column"),
            byte_start=payload.get("byte_start"),
            byte_end=payload.get("byte_end"),
        )
