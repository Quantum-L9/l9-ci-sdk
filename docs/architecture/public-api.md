# Public Python API

The supported public Python surface is **defined authoritatively in
`.l9/public-api.yaml`**. The root package re-exports every public package
(`l9_ci.__all__`), and `tests/architecture/test_public_api.py` asserts each
package's `__all__` equals the manifest exactly, so this document cannot drift
from the enforced surface.

Consumers must not import private implementation modules whose names begin with
an underscore.

## Public packages (11)

Each is stable within a major SDK version:

- `l9_ci.contracts` — canonical models, enums, invariants, `SemanticVersion`
- `l9_ci.repository` — repository enumeration, git inspection, snapshot identity
- `l9_ci.capabilities` — repository capability detection
- `l9_ci.providers` — provider SPI, metadata, registry, `SemgrepProvider`
- `l9_ci.identity` — canonical rule-identity resolution
- `l9_ci.policy` — policy loading and finding classification
- `l9_ci.execution` — execution profiles and provider selection
- `l9_ci.artifacts` — deterministic serialization, schema/semantic validation
- `l9_ci.gates` — gate evaluation
- `l9_ci.integration` — operational limits, compatibility negotiation, redaction,
  agent-review projection
- `l9_ci.cli` — stable exit codes, structured diagnostics, output formatting

## Canonical symbols

The exact exported symbol set per package is listed in `.l9/public-api.yaml`.
Example imports:

```python
from l9_ci.contracts import FindingBundle, GateStatus, SemanticVersion
from l9_ci.providers import Provider, ProviderRegistry, SemgrepProvider
from l9_ci.artifacts import load_and_validate_bundle, validate_bundle
from l9_ci.gates import evaluate_gate
from l9_ci.cli import Diagnostic, ExitCode, OutputFormat
```

Note: `SemanticVersion` has a single public home — `l9_ci.contracts`. It is used
internally by `l9_ci.integration` but is not re-exported there.

## Stability

Canonical contracts and the Provider SPI are stable within a major SDK version.
Adding or removing a public symbol is a versioned compatibility decision:
update `.l9/public-api.yaml` (and, for intentional temporary deviations, its
`compatibility_allowlist`) so the change is reviewed. Internal helpers are not
part of the compatibility guarantee.
