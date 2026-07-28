# Public Python API
The supported public Python surface is exported from:
- `l9_ci.contracts`
- `l9_ci.providers`
- `l9_ci.artifacts`
Consumers must not import private implementation modules whose names begin
with an underscore.
## Canonical contracts
```python
from l9_ci.contracts import (
    Confidence,
    Coverage,
    CoverageStatus,
    EvidenceRecord,
    Finding,
    FindingBundle,
    FindingClassification,
    ProviderFailure,
    ProviderFailureType,
    ProviderRun,
    ResolutionStatus,
    RuleMode,
    Severity,
    SnapshotDescriptor,
    SourceLocation,
)

Provider extension API

from l9_ci.providers import (
    NetworkRequirement,
    Provider,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderMetadata,
    ProviderNormalizationContext,
    ProviderNormalizationResult,
    ProviderRegistry,
    ProviderState,
)

Artifact API

from l9_ci.artifacts import (
    bundle_bytes,
    check_bundle_compatibility,
    load_and_validate_bundle,
    validate_bundle,
    write_bundle_atomic,
)

Stability

Canonical contracts and the Provider SPI are stable within a major SDK
version.

Internal helpers are not part of the compatibility guarantee.
