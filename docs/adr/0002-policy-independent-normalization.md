# ADR 0002: Keep Normalization Policy-Independent
## Status
Accepted
## Context
Provider parsing and policy classification change at different rates and have
different ownership.
## Decision
Provider adapters normalize provider facts without assigning blocking,
advisory, shadow, or disabled modes.
Classification occurs after canonical findings exist.
## Consequences
- The same report can be evaluated under different policies.
- Core may supply policy without owning provider parsing.
- Provider tests remain independent of organizational governance.
