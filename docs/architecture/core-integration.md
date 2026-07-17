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
upload raw and canonical artifacts
    ↓
publish gate result

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
* stable exit codes.

Prohibited behavior

Core must not:

* reconstruct findings;
* create synthetic rule IDs;
* downgrade provider failures;
* bypass bundle validation;
* edit canonical artifacts after generation.
