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
## Runtime packaging
The SDK ships no build manifest and is executed from source over `PYTHONPATH`
by `l9-ci-core`'s `provision-sdk` action. Because of that:
- runtime third-party dependencies are declared in `requirements.txt`
  (`jsonschema`, `referencing`, `PyYAML`) and installed into the provisioning
  venv; adding a new runtime import requires updating that file;
- the canonical version is `l9_ci.__version__`, which must match
  `.l9/integration-contract.yaml` `metadata.version` — the source-run fallback
  the compatibility contract negotiates against.
## Continuous integration & self-analysis
This repository consumes `l9-ci-core` v2 to analyze its own changes; Core is
pinned by immutable commit SHA in every `.github/workflows/l9-analysis*.yml`
caller (never a branch or tag). The callers cover all five governance profiles
declared in `.github/governance/execution-profiles.yaml`:
- `pr_fast` runs on pull requests; `merge` on push to `main`; `nightly` and
  `supply_chain` on schedule; `release` on tag push. Each is also
  `workflow_dispatch`-able for on-demand smoke tests.
- Every profile runs the same path: `semgrep (--config p/python)` ->
  provision-sdk -> `semgrep normalize` -> validate-bundle -> agent payload ->
  route -> manifest -> upload -> Core's `publish-analysis.yml`.
Governance notes:
- All profiles are currently `advisory` and non-strict. Community `p/python`
  rules carry no L9 canonical rule identity, so strict identity resolution would
  reject any finding at `semgrep normalize`; advisory-first surfaces findings
  without blocking. Promote to `blocking` only after adopting L9-authored rules
  (which embed `metadata.l9.canonical_rule_id`) or an explicit identity map,
  per `.github/governance/promotion-policy.yaml`.
- Governance files use a `.yaml` extension but are parsed as JSON — keep them
  valid JSON (no comments, no trailing commas).
