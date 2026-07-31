# ADR 0014: Deterministic Governance-Evidence and Policy Evaluation

## Status

Proposed.

## Decision

Add an SDK-owned, offline governance-evidence layer containing pure validation and comparison functions for contract digests, promotion evidence, runtime attestations, authority deltas, and governed reports.

## Boundaries

The SDK observes and evaluates supplied data. It does not collect historical observations, orchestrate workflows, approve transitions, mutate repositories, publish artifacts, or make release decisions.

## Consequences

- Core and consumer repositories can share stable evidence contracts without duplicating evaluation logic.
- Authority changes become normalized observations rather than hidden prose differences.
- Runtime attestation drift becomes machine-detectable.
- Promotion eligibility is distinct from promotion approval.
- New schemas and tests become part of the SDK protocol surface and therefore require version discipline.
