"""Deterministic repository capability detection."""

from __future__ import annotations
from pathlib import Path
from l9_ci.repository import enumerate_repository_files
from .model import RepositoryCapabilities

_LANGUAGE_SUFFIXES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
}
_PACKAGE_FILES = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "go.mod": "go",
    "Cargo.toml": "cargo",
    "pom.xml": "maven",
    "build.gradle": "gradle",
}
_CONFIGURATION_FILES = {
    ".semgrep.yml",
    ".semgrep.yaml",
    "semgrep.yml",
    "semgrep.yaml",
}


def detect_repository_capabilities(
    root: Path,
) -> RepositoryCapabilities:
    files = enumerate_repository_files(root)
    languages: set[str] = set()
    package_managers: set[str] = set()
    configuration_files: set[str] = set()
    for file_name in files:
        path = Path(file_name)
        language = _LANGUAGE_SUFFIXES.get(path.suffix.lower())
        if language:
            languages.add(language)
        package_manager = _PACKAGE_FILES.get(path.name)
        if package_manager:
            package_managers.add(package_manager)
        if path.name in _CONFIGURATION_FILES:
            configuration_files.add(file_name)
    provider_candidates: set[str] = set()
    if languages:
        provider_candidates.add("semgrep")
    return RepositoryCapabilities(
        root=".",
        languages=tuple(sorted(languages)),
        package_managers=tuple(sorted(package_managers)),
        configuration_files=tuple(sorted(configuration_files)),
        provider_candidates=tuple(sorted(provider_candidates)),
    )
