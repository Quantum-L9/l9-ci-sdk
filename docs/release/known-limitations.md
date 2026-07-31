# Known Limitations

## Semgrep fixture

A runtime-captured, provenance-bound Semgrep report lives at
`tests/fixtures/semgrep/runtime/` (`verification_status: runtime_captured`).
Representative fixtures under `tests/fixtures/semgrep/` remain for unit and
malformed-report edges. The provider must not be promoted to **supported**
until Path B (shadow observation + release-policy promotion) completes.

## Semgrep version range

Enforced on the canonical path via `SemgrepVersionPolicy`:
`>=1.100.0,<2.0.0` (`l9_ci/providers/semgrep/versioning.py`). Analysis callers
pin `semgrep-version: "1.171.0"`. Unsupported versions fail closed in
`validate_configuration`.

## Coverage

Coverage depends on Semgrep's `paths.scanned` and `paths.skipped` fields when
present. When those fields are absent, coverage is derived from finding paths
and is marked limited / incomplete as appropriate — never equivalent to PASS
for required providers.

## Policy format

The Phase 2 example policy format may require an adapter before consuming the
existing Core governance file directly. Core policy files must not be assumed
compatible solely because both use YAML.

## Autofix

The SDK does not infer safe autofix eligibility from Semgrep metadata. A
finding requires an explicit canonical remediation class before projection as
an autofix candidate.

## Execution isolation

Provider execution is bounded by timeout and output size but is not sandboxed
at the operating-system level.

## Network

`network_allowed` was removed from the Provider SPI (DWA-008). Network access
is a caller/runtime concern, not an SDK control flag.
