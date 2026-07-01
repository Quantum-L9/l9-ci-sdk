from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re


def parse_matrix_pairs(values: list[str]) -> dict[str, str]:
    matrix: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"Invalid matrix value {raw!r}; expected key=value")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid matrix key in {raw!r}")
        matrix[key] = value.strip()
    return matrix


def normalize_matrix_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "default"


def derive_matrix_id(matrix: dict[str, str], explicit: str | None = None, *, ci: str | None = None) -> str:
    if explicit:
        return normalize_matrix_id(explicit)
    if matrix:
        parts = [f"{key}={matrix[key]}" for key in sorted(matrix)]
        return normalize_matrix_id("_".join(parts))
    if ci == "github":
        py = os.environ.get("MATRIX_PYTHON") or os.environ.get("PYTHON_VERSION")
        os_name = os.environ.get("MATRIX_OS") or os.environ.get("RUNNER_OS")
        env_matrix = {k: v for k, v in {"os": os_name, "python": py}.items() if v}
        if env_matrix:
            return derive_matrix_id(env_matrix)
    return "default"


@dataclass(frozen=True)
class PipelineContext:
    root: Path
    stage: str
    ci: str | None = None
    matrix: dict[str, str] = field(default_factory=dict)
    matrix_id: str = "default"
    emit_json: Path | None = None
    emit_dir: Path | None = None

    def output_path(self) -> Path | None:
        if self.emit_dir:
            return self.emit_dir / f"{self.stage}_{self.matrix_id}_ci_summary.json"
        if self.emit_json:
            if self.matrix_id != "default" and self.matrix_id not in self.emit_json.stem:
                raise ValueError(
                    "Matrix execution requires unique artifact output path. Add --matrix-id to the filename or use --emit-dir."
                )
            return self.emit_json
        return None
