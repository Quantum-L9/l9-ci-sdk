# Known Limitations
## Semgrep fixture
The initial repository fixture is representative unless replaced by a
runtime-captured report with provenance.
The provider must not be promoted to supported while only representative
fixtures exist.
## Semgrep version range
The minimum and maximum supported Semgrep versions are not yet established.
The adapter records provider version but does not currently enforce a version
range.
## Coverage
Coverage depends on Semgrep's `paths.scanned` and `paths.skipped` fields when
present.
When those fields are absent, coverage is derived from finding paths and is
marked limited.
## Policy format
The Phase 2 example policy format may require an adapter before consuming the
existing Core governance file directly.
Core policy files must not be assumed compatible solely because both use YAML.
## Autofix
The SDK does not infer safe autofix eligibility from Semgrep metadata.
A finding requires an explicit canonical remediation class before projection
as an autofix candidate.
## Execution isolation
Provider execution is bounded by timeout and output size but is not sandboxed
at the operating-system level.
## Network controls
The SDK exposes a network-allowed flag, but enforcement depends on the caller
and runtime environment.
