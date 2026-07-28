# ADR 0001: Separate Evidence from Findings
## Status
Accepted
## Context
Provider reports contain observations, scanner metadata, source locations,
and tool-specific issue records. Downstream systems require stable findings
without losing the original factual basis.
## Decision
The SDK defines separate `EvidenceRecord` and `Finding` contracts.
A finding references one or more evidence records by ID.
## Consequences
- Facts remain traceable.
- Findings may aggregate multiple observations.
- Consumers can inspect supporting evidence.
- Referential integrity becomes a validation requirement.
