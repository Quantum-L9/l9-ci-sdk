# ADR 0007: Derive Snapshot Identity in the SDK
## Status
Accepted
## Context
Evidence and finding identities depend on a deterministic repository snapshot.
Requiring every caller to construct snapshot identity creates inconsistent
identity semantics.
## Decision
The SDK provides Git-aware repository enumeration and snapshot construction.
Callers may provide an external snapshot ID, but the SDK can derive one from:
- revision;
- dirty state;
- normalized repository file inventory.
## Consequences
- Identity construction is consistent across consumers.
- Non-Git repositories remain supported through a filesystem fallback.
- Snapshot derivation is testable independently of providers.
