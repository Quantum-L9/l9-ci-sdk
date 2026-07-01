from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from l9_ci.utils.files import FileMode, iter_files
from l9_ci.utils.pysource import docstring_line_numbers, strip_string_and_comment_content

DEPRECATED_SYMBOL = "DomainSpecLoader"
REPLACEMENT_SYMBOL = "DomainPackLoader"

_IMPORT_PATTERN = re.compile(r"from\s+engine\.config\.loader\s+import\s+([^\n]*\bDomainSpecLoader\b[^\n]*)")
_CALL_PATTERN = re.compile(r"\bDomainSpecLoader\(([^)]*)\)")
DEFAULT_EXCLUDE_PATHS = ["l9_ci/scanners/deprecated_api.py"]

@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    text: str


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def collect_python_files(
    paths: list[Path],
    exclude: set[str] | list[str] | None = None,
    *,
    file_mode: FileMode = "auto",
) -> list[Path]:
    return iter_files(
        paths,
        suffixes={".py"},
        exclude=[*DEFAULT_EXCLUDE_PATHS, *list(exclude or [])],
        file_mode=file_mode,
    )


def _replace_import_line(match: re.Match[str]) -> str:
    symbols = match.group(1)
    replaced = re.sub(r"\bDomainSpecLoader\b", REPLACEMENT_SYMBOL, symbols)
    return f"from engine.config.loader import {replaced}"


def _replace_call(match: re.Match[str]) -> str:
    arg = match.group(1).strip()
    if not arg:
        return "DomainPackLoader()"
    if arg.startswith("config_path="):
        return f"DomainPackLoader({arg})"
    if arg.startswith("str("):
        return f"DomainPackLoader(config_path={arg})"
    return f"DomainPackLoader(config_path=str({arg}))"


def check_file(path: Path, root: Path | None = None) -> list[Violation]:
    root = root or Path.cwd()
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = _rel(path, root)
    docstring_lines = docstring_line_numbers(text)
    violations: list[Violation] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        # Ignore the symbol when it only appears in a comment or a string/docstring
        # literal (prose), so mentions don't produce false positives.
        if lineno in docstring_lines:
            continue
        if DEPRECATED_SYMBOL in strip_string_and_comment_content(line):
            violations.append(Violation(rel, lineno, line.rstrip()))
    return violations


def check(
    paths: list[Path],
    root: Path | None = None,
    exclude: list[str] | None = None,
    file_mode: FileMode = "auto",
) -> list[Violation]:
    root = root or Path.cwd()
    violations: list[Violation] = []
    for path in collect_python_files(paths, exclude, file_mode=file_mode):
        violations.extend(check_file(path, root))
    return violations


def fix_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8", errors="replace")
    text = _IMPORT_PATTERN.sub(_replace_import_line, original)
    text = _CALL_PATTERN.sub(_replace_call, text)
    if text == original:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def fix(
    paths: list[Path],
    exclude: list[str] | None = None,
    file_mode: FileMode = "auto",
) -> list[Path]:
    changed: list[Path] = []
    for path in collect_python_files(paths, exclude, file_mode=file_mode):
        if fix_file(path):
            changed.append(path)
    return changed


def format_violations(violations: list[Violation]) -> str:
    lines = ["ERROR: DomainSpecLoader is deprecated - use DomainPackLoader.", ""]
    for v in violations:
        lines.append(f"{v.file}:{v.line}: {v.text}")
    lines.append("Auto-fix: l9-ci fix-deprecated-api .")
    return "\n".join(lines)
