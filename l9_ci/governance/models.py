"""Canonical immutable result contracts for governance evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class EvaluationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_thaw(item) for item in value), key=repr)
    return value


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    path: str = ""
    severity: str = "error"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("diagnostic code must be non-empty")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("diagnostic message must be non-empty")
        if not isinstance(self.path, str):
            raise TypeError("diagnostic path must be a string")
        if self.severity not in {"info", "warning", "error"}:
            raise ValueError("unsupported diagnostic severity")
        if not isinstance(self.details, Mapping):
            raise TypeError("diagnostic details must be a mapping")
        object.__setattr__(self, "details", _freeze(self.details))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
            "details": _thaw(self.details),
        }


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    status: EvaluationStatus
    diagnostics: tuple[Diagnostic, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.status, EvaluationStatus):
            raise TypeError("status must be an EvaluationStatus")
        diagnostics = tuple(self.diagnostics)
        if any(not isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain Diagnostic values")
        if not isinstance(self.evidence, Mapping):
            raise TypeError("evidence must be a mapping")
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "evidence", _freeze(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "evidence": _thaw(self.evidence),
        }
