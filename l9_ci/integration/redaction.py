"""Canonical artifact redaction validation."""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_SECRET_KEY_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key)",
    re.IGNORECASE,
)
_ABSOLUTE_UNIX_PATH = re.compile(r"^/")
_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(frozen=True, slots=True)
class RedactionResult:
    valid: bool
    errors: tuple[str, ...]

    def require_valid(self) -> None:
        if self.errors:
            joined = "\n".join(f"- {error}" for error in self.errors)
            raise ValueError(f"redaction validation failed:\n{joined}")


def validate_redaction(payload: Mapping[str, Any]) -> RedactionResult:
    errors: list[str] = []
    _walk(payload, path="<root>", errors=errors)
    return RedactionResult(
        valid=not errors,
        errors=tuple(sorted(set(errors))),
    )


def _walk(value: Any, *, path: str, errors: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if _SECRET_KEY_PATTERN.search(key_text):
                errors.append(f"{child_path}: secret-like property name is forbidden")
            if key_text in {"lines", "matched_source", "metavars"}:
                errors.append(f"{child_path}: raw source material is forbidden")
            _walk(child, path=child_path, errors=errors)
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for index, child in enumerate(value):
            _walk(child, path=f"{path}[{index}]", errors=errors)
        return
    if isinstance(value, str):
        if _ABSOLUTE_UNIX_PATH.match(value):
            errors.append(f"{path}: absolute Unix path is forbidden")
        if _WINDOWS_DRIVE_PATH.match(value):
            errors.append(f"{path}: absolute Windows path is forbidden")
