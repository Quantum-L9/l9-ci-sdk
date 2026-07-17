# Semgrep Provider
## Status
Experimental.
## Supported input
Semgrep JSON output produced by:
```bash
semgrep scan \
  --json-output artifacts/raw/semgrep/results.json \
  --config <configuration> \
  .

The SDK does not parse terminal output.

Native identity

check_id is preserved exactly as provider_rule_id.

Canonical identity is accepted only from:

1. trusted extra.metadata.l9.canonical_rule_id; or
2. the versioned SDK identity map.

No fallback canonical identity is generated.

Severity

The adapter preserves the original Semgrep severity in attributes and maps it
to the canonical severity enum.

Unrecognized values map to unknown and create a limitation.

Redaction

The adapter does not retain:

* matched source lines;
* metavariable contents;
* full raw findings;
* environment values;
* absolute repository paths.

Only allowlisted metadata is retained.

Errors

Malformed report structure becomes report_malformed.

Entries in the report’s top-level errors array become structured execution
failures and partial coverage.

Strict mode

Strict mode fails when:

* a finding has unresolved canonical identity;
* a finding has unresolved policy;
* findings exist but no policy was supplied;
* bundle validation fails.

Coverage limitation

Until Semgrep target statistics are modeled through a verified versioned
contract, coverage counts unique paths represented by findings. This is not a
complete measure of all files scanned.

The limitation must remain documented until a real report fixture confirms a
stable scanned-path field.

---
# `pyproject.toml` additions
Merge these with existing dependencies:
```toml
dependencies = [
  "jsonschema>=4.23,<5",
  "pyyaml>=6.0,<7",
]

Optional Semgrep execution dependency:

[project.optional-dependencies]
semgrep = [
  "semgrep>=1.100"
]

Do not make the Semgrep Python package a mandatory SDK dependency when import-only mode is used.
