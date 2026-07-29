"""Stable contract-set digest calculation with no filesystem mutation."""
from __future__ import annotations

import hashlib
import unicodedata
from pathlib import PurePosixPath, PureWindowsPath
from typing import Mapping

PROTOCOL = "l9.contract-set-digest/v1"


def _safe_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("contract path must be a non-empty string")
    if "\x00" in value or any(ord(char) < 32 for char in value):
        raise ValueError(f"unsafe contract path: {value!r}")
    portable = unicodedata.normalize("NFC", value.replace("\\", "/"))
    windows = PureWindowsPath(value)
    path = PurePosixPath(portable)
    if path.is_absolute() or windows.is_absolute() or windows.drive or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe contract path: {value}")
    normalized = path.as_posix()
    if normalized in {"", "."}:
        raise ValueError(f"unsafe contract path: {value}")
    return normalized


def normalize_contract_bytes(content: bytes) -> bytes:
    """Normalize UTF-8 text newlines; preserve non-UTF-8 binary bytes."""
    if not isinstance(content, bytes):
        raise TypeError("contract content must be bytes")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def contract_file_hashes(files: Mapping[str, bytes]) -> dict[str, str]:
    if not isinstance(files, Mapping):
        raise TypeError("files must be a mapping of paths to bytes")
    normalized: dict[str, str] = {}
    original_paths: dict[str, str] = {}
    for raw_path, content in files.items():
        path = _safe_path(raw_path)
        if path in normalized:
            raise ValueError(
                "contract paths collide after normalization: "
                f"{original_paths[path]!r} and {raw_path!r}"
            )
        original_paths[path] = raw_path
        normalized[path] = "sha256:" + hashlib.sha256(normalize_contract_bytes(content)).hexdigest()
    return dict(sorted(normalized.items()))


def contract_set_digest(files: Mapping[str, bytes]) -> str:
    hashes = contract_file_hashes(files)
    framed = bytearray(PROTOCOL.encode("ascii") + b"\0")
    for path, digest in hashes.items():
        framed.extend(path.encode("utf-8"))
        framed.extend(b"\0")
        framed.extend(digest.encode("ascii"))
        framed.extend(b"\0")
    return "sha256:" + hashlib.sha256(bytes(framed)).hexdigest()
