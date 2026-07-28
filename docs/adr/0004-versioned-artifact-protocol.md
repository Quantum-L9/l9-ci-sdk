# ADR 0004: Use a Versioned Finding-Bundle Protocol
## Status
Accepted
## Context
Core, repair systems, LSPs, and future consumers need a stable SDK output
contract.
## Decision
The SDK emits `l9.finding-bundle/v1`.
The protocol and schema version are declared in every artifact.
## Consequences
- Consumers can negotiate compatibility.
- Breaking changes require an explicit major version.
- Schema validation can occur before deserialization.
