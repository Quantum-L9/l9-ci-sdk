# Capability Detection

Capability detection deterministically inventories repository languages, package managers, relevant configuration files, and candidate providers. Detection is advisory and never silently enables a provider.

## Capability inventory

`detect_repository_capabilities` lists what is present. `build_capability_inventory`
answers what a caller needs before it schedules analysis: for one exact
snapshot, every recognized language, every supported framework and one
prerequisite per analysis target, each in an explicit state. It realizes
`L9-CI-SDK-001` and `L9-CI-SDK-002` (ADR 0020, Proposed).

| State | Meaning |
| --- | --- |
| `applicable` | Positive evidence that the capability applies and a declared target serves it. |
| `not_applicable` | Positive evidence that it does not apply. The reason names how many files were examined. |
| `unsupported` | Present in the repository, and no declared target serves it. Never dropped, never a pass. |
| `incomplete` | Applies, but a probed prerequisite is missing, for example the provider executable. |
| `failed` | Evidence exists and cannot be trusted: a manifest that does not parse, or a rulepack that did not resolve. |

Rules the inventory holds:

- A mixed repository lists every language. There is no primary language.
- A malformed `pyproject.toml`, `package.json`, `Cargo.toml` or Odoo
  `__manifest__.py` is `failed`, never absence. The languages are still listed.
- Odoo is detected from a parsed addon manifest. Its Python and XML counts
  cover files inside addon directories only.
- The record is bound to the snapshot (`snapshot_id`, `revision`, `dirty`) and
  is a pure function of the snapshot's paths, the content of its manifests and
  the declared targets. The snapshot identity covers which paths exist, not
  what they contain, so each manifest entry carries the `sha256` of the bytes
  that were read.
- The record carries `SDK_version`, as every version-negotiated artifact does.
  The caller supplies it; this package does not guess it.
- Coverage is counted per file. Each target declares the file suffixes its
  tool analyzes; a file of a served language with another suffix, or outside
  the framework a framework target is scoped to, is counted in that
  language's `unanalyzed_file_count` and named in `reasons`. A language is
  `applicable` when at least one of its files is analyzed, `unsupported` when
  none is.
- JavaScript is served by the `semgrep` target `language:typescript`: the
  TypeScript rulepack declares `languages: [typescript, javascript]`, its
  fixture `tests/fixtures/semgrep/rules/typescript/l9-baseline-security.jsfixture`
  proves every rule on JavaScript in both directions, and
  `l9-ci semgrep run --language typescript` analyzes `.js`, `.jsx`, `.mjs`
  and `.cjs`. There is no separate JavaScript target, so a repository with
  both languages is scanned once.
- A Semgrep target counts only files inside the declared scan scope
  (`l9_ci/rulesets/semgrep/scan-scope.yaml`), the same scope
  `l9-ci semgrep run --required` passes to Semgrep. When every matching file
  is out of scope, the target is `not_applicable` and its reason names each
  excluding scope entry with a sample of the paths, so Core plans no instance
  the scan could never complete. Out-of-scope files stay counted in their
  language's `unanalyzed_file_count`; a language whose files are all out of
  scope is `unsupported` and says so. This was found on Cursor-Governance
  (2026-11-20), where every JavaScript file is a fixture under `tests/`:
  a required `language:typescript` instance was planned, scanned nothing and
  ended `incomplete`. Witness:
  `tests/capabilities/test_inventory_scan_scope.py`.
- The executable is a fact about the machine, so it is `not_probed` unless
  the caller asks (`--probe-executables`).
- The record carries no requiredness, enforcement mode or verdict. Core
  decides requiredness; Assurance decides policy.

This package does not import the provider or rulepack layers
(`.l9/architecture.yaml`). The composition layer declares the targets
(`AnalysisTarget`); `l9-ci providers inventory` declares one per packaged
Semgrep language rulepack.

Schema: `l9_ci/schemas/v1/capability-inventory.schema.json`
(`l9.capability-inventory/v1`). `validate_capability_inventory` checks the
schema and that `status` agrees with the entries.

### Known blind spots

- Languages are recognized by file suffix. A source file with no suffix or an
  unlisted suffix is counted in `unclassified_file_count` and not named.
- `requirements.txt`, `go.mod`, `pom.xml` and `build.gradle` are recorded as
  evidence and not parsed, so they cannot be reported malformed.
- Go, Java, Kotlin, Ruby, Rust, PHP, Swift, Scala, C#, C, C++, shell and XML
  are recognized and have no analysis target in this SDK build.
- Semgrep 1.171.0 does not scan `.mts` or `.cts`. Those TypeScript files are
  reported as not analyzed. `tests/rulesets/test_semgrep_target_suffixes.py`
  re-checks each target's declared suffixes against the real executable.
- Odoo is the only framework with a detector.
