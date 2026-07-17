## Repository purpose
`l9-ci-sdk` owns canonical analysis contracts, provider adapters, normalized
findings, validation, and deterministic artifact generation.
It does not own CI workflow orchestration.
## Architectural rules
1. Provider parsing must remain policy-independent.
2. Native provider rule IDs must always be preserved.
3. Canonical rule IDs require explicit resolution.
4. Unknown identities must remain unresolved.
5. Human-readable scanner output is not a supported integration contract.
6. Canonical bundle writes must be deterministic and atomic.
7. Schema validation and semantic validation are both required.
8. Required provider failures must never be converted into PASS.
9. SDK contracts must not import workflow or scanner implementation code.
10. Provider implementations must not import artifact internals.
## Phase 1 restrictions
Until Phase 1 is complete:
- do not add scanner providers;
- do not add Semgrep-specific code;
- do not modify `l9-ci-core`;
- do not add repair behavior;
- do not add LSP behavior;
- do not add corpus storage;
- do not add hosted-service dependencies.
## Contract changes
Any change to a canonical model must include:
- Python model update;
- JSON Schema update;
- compatibility assessment;
- model invariant tests;
- schema conformance tests;
- ADR update when architectural semantics change.
## Provider requirements
Every future provider must include:
- verified machine-readable format;
- real redacted fixture;
- provider version;
- invocation provenance;
- malformed-report tests;
- path-normalization tests;
- deterministic-output tests;
- provider failure tests;
- coverage behavior;
- identity-resolution behavior.
## Prohibited shortcuts
Do not:
- fabricate provider fixtures;
- parse console output when structured output exists;
- invent policy keys;
- derive canonical identity from severity;
- silently discard malformed records;
- retain secret material;
- use absolute source paths in canonical artifacts;
- claim successful validation without executing tests.
