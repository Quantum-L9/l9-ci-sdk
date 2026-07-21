"""Provider service-provider interface."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable
from l9_ci.contracts import (
    Coverage,
    EvidenceRecord,
    Finding,
    ProviderFailure,
)


@dataclass(frozen=True, slots=True)
class ProviderExecutionRequest:
    """Execution request passed to a provider adapter."""

    repository_root: Path
    output_path: Path
    timeout_seconds: int
    output_size_limit_bytes: int
    environment: Mapping[str, str] = field(default_factory=dict)
    arguments: tuple[str, ...] = ()
    # NOTE: a `network_allowed` flag was removed (DWA-008). The SDK executes
    # providers via subprocess and cannot enforce network isolation, so the flag
    # was inert and created false assurance. Network isolation is an explicit
    # l9-ci-core execution-environment guarantee, not an SDK-owned control.

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.output_size_limit_bytes <= 0:
            raise ValueError("output_size_limit_bytes must be positive")
        object.__setattr__(self, "arguments", tuple(self.arguments))


@dataclass(frozen=True, slots=True)
class ProviderExecutionResult:
    """Raw provider process result."""

    exit_code: int
    report_path: Path | None
    stdout: str
    stderr: str
    timed_out: bool = False
    output_limit_exceeded: bool = False


@dataclass(frozen=True, slots=True)
class ProviderNormalizationContext:
    """Context required to normalize one provider report."""

    snapshot_id: str
    repository_root: Path
    provider_version: str | None
    required: bool


@dataclass(frozen=True, slots=True)
class ProviderNormalizationResult:
    """Canonical output produced by one provider adapter."""

    evidence: tuple[EvidenceRecord, ...]
    findings: tuple[Finding, ...]
    coverage: Coverage
    failures: tuple[ProviderFailure, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "failures", tuple(self.failures))
        object.__setattr__(self, "limitations", tuple(self.limitations))


@runtime_checkable
class Provider(Protocol):
    """Contract implemented by every scanner provider adapter."""

    @property
    def metadata(self) -> Any:
        """Return ProviderMetadata."""

    def detect(self, repository_root: Path) -> bool:
        """Return whether the provider is available for this repository."""

    def detect_version(self) -> str | None:
        """Return the provider version when detectable."""

    def validate_configuration(
        self,
        repository_root: Path,
    ) -> Sequence[str]:
        """Return configuration errors without executing the provider."""

    def build_execution_plan(
        self,
        request: ProviderExecutionRequest,
    ) -> Sequence[str]:
        """Return the provider command as an argument vector."""

    def execute(
        self,
        request: ProviderExecutionRequest,
    ) -> ProviderExecutionResult:
        """Execute the provider using bounded process controls."""

    def execution_failure(
        self,
        result: ProviderExecutionResult,
        *,
        required: bool,
        provider_version: str | None,
    ) -> ProviderFailure | None:
        """Classify a raw execution result into a structured failure, or None."""

    def validate_report_shape(
        self,
        report: Mapping[str, Any],
    ) -> Sequence[str]:
        """Return structural report validation errors."""

    def import_report(
        self,
        report_path: Path,
    ) -> Mapping[str, Any]:
        """Load a provider-native report without normalizing it."""

    def normalize(
        self,
        report: Mapping[str, Any],
        context: ProviderNormalizationContext,
    ) -> ProviderNormalizationResult:
        """Normalize a validated native report into canonical records."""
