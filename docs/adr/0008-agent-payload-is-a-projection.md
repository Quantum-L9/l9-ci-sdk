# ADR 0008: Agent Payload Is a Projection
## Status
Accepted
## Context
The finding bundle is the canonical SDK artifact.
Agent consumers benefit from a smaller categorized view, but a second
canonical protocol would create competing sources of truth.
## Decision
The agent-review payload is a deterministic projection.
It must retain source finding IDs and may always be regenerated from the
canonical finding bundle.
## Consequences
- The finding bundle remains authoritative.
- Projection schemas may evolve independently.
- Consumers must not use the projection as canonical storage.
