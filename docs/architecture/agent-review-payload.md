# Agent-Review Payload
The agent-review payload is a projection of the canonical finding bundle.
It is not the canonical source of truth.
## Buckets
Findings are projected into:
- blocking
- advisory
- shadow
- unresolved
- disabled
- autofix candidates
## Autofix candidates
A finding is an autofix candidate only when:
- its classification is neither disabled nor unresolved; and
- its canonical `remediation_class` is `safe-autofix` or `mechanical`.
The Semgrep provider does not infer remediation safety from Semgrep metadata.
## Strict projection
Strict projection fails when unresolved findings exist.
## Traceability
Every projected finding retains:
- finding ID;
- provider ID;
- provider rule ID;
- canonical rule ID when resolved;
- policy key when resolved;
- source locations;
- canonical fingerprint;
- limitations.
