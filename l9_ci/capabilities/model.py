"""Repository capability contracts."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RepositoryCapabilities:
    root: str
    languages: tuple[str, ...]
    package_managers: tuple[str, ...]
    configuration_files: tuple[str, ...]
    provider_candidates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "languages": list(self.languages),
            "package_managers": list(self.package_managers),
            "configuration_files": list(self.configuration_files),
            "provider_candidates": list(self.provider_candidates),
        }
