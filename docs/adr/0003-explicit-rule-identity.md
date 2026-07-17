# ADR 0003: Require Explicit Rule Identity Resolution
## Status
Accepted
## Context
Synthetic rule identifiers derived from provider names, severity, confidence,
or messages are unstable and can silently misclassify findings.
## Decision
The SDK always preserves `provider_rule_id`.
`canonical_rule_id` and `policy_key` require trusted metadata or an explicit
versioned mapping.
Unresolved identity remains explicit.
## Consequences
- Unknown mappings cannot silently block changes.
- Mapping changes are reviewable.
- Strict mode can reject unresolved identities.
