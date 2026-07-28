# ADR 0005: Introduce an Explicit Provider SPI
## Status
Accepted
## Context
Scanner integrations require consistent execution, import, normalization,
failure, and coverage behavior.
## Decision
Every scanner integration implements the SDK Provider protocol.
Providers register explicitly through `ProviderRegistry`.
## Consequences
- Provider lifecycle becomes testable.
- Duplicate provider identities are rejected.
- Provider integrations can be promoted independently.
- Core does not require scanner-specific logic.
