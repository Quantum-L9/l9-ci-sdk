# l9-ci-core Integration Contract
`l9-ci-core` consumes `l9-ci-sdk` only through the public CLI and validated
artifact protocol.
Core must not import SDK internals or parse Semgrep JSON.
## Recommended flow
```text
Core workflow
    ↓
capture repository snapshot identity
    ↓
run Semgrep or acquire Semgrep JSON
    ↓
invoke l9-ci semgrep normalize
    ↓
invoke l9-ci bundle validate
    ↓
invoke l9-ci bundle project-agent-payload
    ↓
invoke l9-ci gate evaluate
    ↓
upload raw and canonical artifacts
    ↓
publish gate result (Core publishes the SDK-emitted gate-result.json)

Required inputs

Core supplies:

* repository root;
* repository revision;
* deterministic snapshot ID;
* Semgrep report path;
* Semgrep version;
* identity map;
* policy;
* provider requiredness;
* strict-mode decision;
* SDK version pin.

Required outputs

The SDK produces:

* finding-bundle.json;
* agent-review-payload.json;
* gate-result.json (the canonical gate decision; Core publishes this rather
  than reconstructing a verdict);
* stable exit codes.

Prohibited behavior

Core must not:

* reconstruct findings;
* create synthetic rule IDs;
* downgrade provider failures;
* bypass bundle validation;
* edit canonical artifacts after generation.

## SARIF projection (`bundle project-sarif`)

The SDK owns deterministic projection of a canonical finding bundle onto the
supported SARIF 2.1.0 subset (`l9_ci/schemas/v1/sarif-log.schema.json`, schema
id `l9.sarif-log/v1`) that GitHub code scanning ingests. Core invokes it and
uploads the result; Core never builds SARIF itself.

```
l9-ci bundle project-sarif --input BUNDLE --output SARIF [--strict]
```

### Ownership

* **SDK owns**: the bundle → SARIF mapping, the subset schema, determinism, and
  redaction of the projected log.
* **Core owns**: uploading the SARIF file to GitHub code scanning. The SDK
  makes no GitHub API call and performs no upload.

### Deterministic mapping

* Input is the SDK's own `FindingBundle` — never a raw provider report.
* Results are emitted in canonical `finding_id` order; `tool.driver.rules` in
  sorted `ruleId` order. Identical bundles produce byte-identical SARIF.
* `ruleId` is the finding's `canonical_rule_id`, falling back to its
  `provider_rule_id`. Canonical severity maps to SARIF `level`
  (critical/high → error, medium → warning, low/informational → note, unknown
  and unset → warning). The canonical `fingerprint` is emitted as
  `partialFingerprints["l9/fingerprint"]` for cross-run de-duplication.
* `--strict` rejects findings that have no canonical identity rather than
  projecting them under a provider rule id.

### Redaction

The projection carries only redaction-safe canonical fields: rule id, level,
message, repository-relative path, and line/column region. It never emits
source lines, code snippets, metavariable contents, secrets, or absolute paths
— the subset schema sets `additionalProperties: false` everywhere (so a
`region.snippet` cannot appear) and forbids absolute `artifactLocation.uri`
values, and the shared `validate_redaction` guard runs over the projected log
before it is written.
