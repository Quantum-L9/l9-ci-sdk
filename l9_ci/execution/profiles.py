"""SDK execution profile definitions."""

from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ExecutionProfileName(StrEnum):
    NATIVE = "native"
    IMPORT_ONLY = "import_only"
    ALL_SUPPORTED = "all_supported"


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    name: ExecutionProfileName
    execute_providers: bool
    import_reports: bool
    supported_only: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "execute_providers": self.execute_providers,
            "import_reports": self.import_reports,
            "supported_only": self.supported_only,
        }


PROFILES = {
    ExecutionProfileName.NATIVE: ExecutionProfile(
        name=ExecutionProfileName.NATIVE,
        execute_providers=False,
        import_reports=False,
        supported_only=True,
    ),
    ExecutionProfileName.IMPORT_ONLY: ExecutionProfile(
        name=ExecutionProfileName.IMPORT_ONLY,
        execute_providers=False,
        import_reports=True,
        supported_only=False,
    ),
    ExecutionProfileName.ALL_SUPPORTED: ExecutionProfile(
        name=ExecutionProfileName.ALL_SUPPORTED,
        execute_providers=True,
        import_reports=True,
        supported_only=True,
    ),
}


def get_execution_profile(
    name: str | ExecutionProfileName,
) -> ExecutionProfile:
    profile_name = ExecutionProfileName(name)
    return PROFILES[profile_name]
