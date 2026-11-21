"""Which web frameworks a repository actually uses (framework-scoped rules).

Registry rulesets such as ``p/python`` carry framework-specific rules, for
example ``python.django.*``. Those rules model a framework's request
objects and conventions. The Django ``subprocess-injection`` rule, for one,
treats any function parameter named ``request`` as an HTTP request. A finding
from such a rule is meaningful only where the framework is in use (CTO,
2026-11-21: "Framework rules must run only where that framework is
detected").

Detection is evidence based and deterministic: a tracked dependency
declaration that names the framework, or the framework's own entry point.
Nothing is imported or executed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from l9_ci.repository import build_repository_snapshot

_DEPENDENCY_FILES = frozenset(
    {"pyproject.toml", "setup.cfg", "setup.py", "Pipfile", "environment.yml"}
)
_REQUIREMENT_FILE = re.compile(r"^(?:requirements|constraints)[\w.-]*\.(?:txt|in)$")
# A requirement naming the package exactly: "django", "Django>=4", "django[argon2]",
# '"django~=5.0"' in a pyproject list. Not "django-environ" or "djangorestframework".
_DJANGO_REQUIREMENT = re.compile(
    r"""(?im)(?:^|["'\s,\[])django(?:\s*(?:[<>=!~;\[]|$)|["'])"""
)
# Django's generated manage.py imports its management entry point and sets
# the settings module; a file that merely mentions the word does not count.
_DJANGO_ENTRY_POINT = re.compile(r"django\.core\.management|DJANGO_SETTINGS_MODULE")
_MAX_BYTES = 1_000_000


@dataclass(frozen=True, slots=True)
class FrameworkDetection:
    framework: str
    detected: bool
    evidence: tuple[str, ...]


def _read(root: Path, relative: str) -> str:
    path = root / relative
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_django(
    root: Path, files: tuple[str, ...] | None = None
) -> FrameworkDetection:
    """Detect Django from a dependency declaration or a Django ``manage.py``."""
    root = root.resolve()
    tracked = files if files is not None else build_repository_snapshot(root).files
    evidence = []
    for relative in tracked:
        name = PurePosixPath(relative).name
        if name in _DEPENDENCY_FILES or _REQUIREMENT_FILE.match(name):
            if _DJANGO_REQUIREMENT.search(_read(root, relative)):
                evidence.append(relative)
        elif name == "manage.py" and _DJANGO_ENTRY_POINT.search(_read(root, relative)):
            evidence.append(relative)
    return FrameworkDetection(
        framework="django", detected=bool(evidence), evidence=tuple(sorted(evidence))
    )


def detect_frameworks(root: Path) -> Mapping[str, FrameworkDetection]:
    files = build_repository_snapshot(root.resolve()).files
    return {"django": detect_django(root, files)}


__all__ = ["FrameworkDetection", "detect_django", "detect_frameworks"]
