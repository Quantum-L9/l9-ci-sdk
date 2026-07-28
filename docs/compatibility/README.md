# Compatibility Fixtures

This directory documents the immutable compatibility fixtures under
`tests/compatibility/fixtures`.

- `finding-bundle-v1-minimal.json` verifies the smallest valid v1 bundle.
- `finding-bundle-v1-semgrep.json` is generated deterministically from the
  redacted Semgrep fixture and explicit identity and policy mappings.
- `unsupported-bundle-v2.json` verifies rejection of unsupported major versions.

Compatibility fixtures are test inputs, not evidence of a live Semgrep capture.
