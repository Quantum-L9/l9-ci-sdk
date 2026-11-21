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

Entries in the report’s top-level errors array follow Semgrep's own `level`:

* `level: error`, or a missing or unknown level, becomes a structured execution
  failure (fatal when the provider is required), and coverage is partial.
* `level: warn` stays a limitation and is not a failure (SDK #83).
* Except: a warn entry whose `type` is `Timeout`, `FixpointTimeout`,
  `OutOfMemory` or `StackOverflow` means a rule started on a file and did not
  finish. It is still not a failure, but coverage is partial: the file is not
  counted as analyzed, and the limitation names the rule and the file
  (`incomplete analysis: rule <id> did not finish on <path> (<type>)`). A
  required provider's gate is therefore `incomplete`, never `pass`. Found on
  Cursor-Governance run 44819081765, where 5 rule timeouts on 4 files were
  reported as a complete pass (lane L1-CANARY-FIXES, B5). Witnesses:
  `tests/providers/semgrep/test_provider.py`, including the real captured
  report `tests/fixtures/semgrep/report-timeout-captured.json`.

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

## Packaged execution: `l9-ci semgrep run`

`l9-ci semgrep run --language {python,typescript}` executes Semgrep with the
SDK's packaged global ruleset for one language and normalizes the report in a
single step. Downstream consumers inherit one versioned ruleset per language
with no per-repository `--config` authoring.

The `--config` arguments passed to Semgrep are composed deterministically, in
this order:

1. the community registry ruleset for the language (`p/python` or
   `p/typescript`), when the selected profile includes it and
   `--no-registry-config` is not set;
2. the SDK-packaged L9 baseline ruleset directory for the language
   (`l9_ci/rulesets/semgrep/<language>/`), when the selected profile includes
   it;
3. each caller-supplied `--extra-config` value, in the order given.

`--profile <name>` selects a versioned entry from the packaged profile
registry (`l9_ci/rulesets/semgrep/profiles.yaml`) that decides which of the two
packaged config sources participate. When `--profile` is omitted the registry's
`default_profile` applies, which reproduces the pre-profile composition
(registry ruleset + L9 ruleset). Profiles only choose among already-packaged
configs; they never add a second scanner, SARIF projection, GitHub upload, or
promotion of a rule to blocking. An unknown profile fails closed at argument
parsing. See [`semgrep-ruleset-profiles.md`](semgrep-ruleset-profiles.md) for
the registry contract and the shipped profiles.

Identity resolution is unchanged by profile selection: L9-authored rules carry
trusted `metadata.l9.canonical_rule_id`, and third-party registry rules resolve
through the versioned SDK identity map.

## Execution argv

`SemgrepProvider.execute` runs Semgrep as an argv list with no shell. The
environment is an allowlist (PATH, HOME, TMPDIR, TEMP, TMP). The argv is:

- the resolved executable, `scan` and `--json-output <path>`;
- the caller's options;
- the end-of-options marker `--`;
- the targets (`.` or a required run's declared files).

Target names can come from the repository under analysis.
`ProviderExecutionRequest` refuses:

- a NUL in any element;
- an empty argument;
- an argument equal to `--`;
- an absolute, parent-relative or `-`-prefixed target.

The declared scope rewrites `-x` to `./-x`. The marker keeps any target from
being read as an option. Witnesses:

- `tests/rulesets/test_semgrep_scan_scope.py`
  (`test_provider_request_refuses_unsafe_argv_elements`);
- `tests/commands/test_semgrep_required_scope_e2e.py`
  (`test_dash_named_file_is_scanned_as_a_path_not_read_as_an_option`).

## Required central runs: `--disable-nosem` and the declared scan scope

Core passes `--required` to `l9-ci semgrep run` when governance marks the
provider required. A required run differs from any other run in three ways
(lanes L1f and B5, 2026-11-20), and nothing else changes:

1. **`--disable-nosem`.** Semgrep honours an inline `# nosemgrep` comment by
   default, so a consumer could silence a required central rule line by line.
   A required run passes `--disable-nosem`, and the annotated line yields its
   finding. Waiving a finding is a decision for the finding policy, not a
   source comment.
2. **Declared scan scope.** Semgrep otherwise takes scope from a consumer's
   root `.semgrepignore`, which replaces Semgrep's built-in default list
   entirely, or from that built-in list when no `.semgrepignore` exists.
   Neither was declared by Core or the SDK, and the first let a consumer drop
   any path, `src/` included. A required run resolves its targets from the
   SDK-packaged policy
   [`l9_ci/rulesets/semgrep/scan-scope.yaml`](../../l9_ci/rulesets/semgrep/scan-scope.yaml)
   (`l9.semgrep-scan-scope-policy/v1`): every Git-tracked file at the analyzed
   snapshot, minus the declared exclusions, which reproduce Semgrep's
   documented default list plus `.l9/runtime`. Each resolved file is passed to
   Semgrep as an explicit target. Semgrep applies `.semgrepignore` patterns
   only while expanding a folder scan root, never to an explicit file, so
   neither a consumer `.semgrepignore` nor the built-in list applies.

   `tests/`, `test/` and `testsuite/` stay out of required scope by an explicit
   policy entry, matching the default that applied before. Bringing tests into
   scope is an organization policy decision and an edit to that list.
3. **Declared analysis budget.** Semgrep's defaults give each rule 5 s per
   file and, after 3 timeouts on one file, silently skip every remaining rule
   on it. A required run passes `--timeout 30 --timeout-threshold 0`
   (`REQUIRED_RULE_TIMEOUT_SECONDS`, `REQUIRED_RULE_TIMEOUT_THRESHOLD` in
   `l9_ci/rulesets/semgrep/scope.py`): 30 s per rule and file, and no per-file
   cut-off. A rule/file pair that still times out under that budget was not
   analysed; the provider removes the file from the scanned paths, records
   the pair as a limitation and reports coverage `partial`, so the gate ends
   `incomplete`, never `pass` (#131).

The effective scope is written beside the raw report as `<stem>.scope.json`
(`l9.semgrep-scan-scope/v1`,
[`semgrep-scan-scope.schema.json`](../../l9_ci/schemas/v1/semgrep-scan-scope.schema.json)):
the policy version and digest, the tracked and in-scope file counts, a digest
of the in-scope path list, every exclusion with its exact count and a bounded
sample, any consumer `.semgrepignore` found (`honored: false`), `nosem: disabled` and
the `analysis_budget` (schema 1.1.0). Core already uploads the raw-report directory, so the record
reaches the analysis artifact set. It is written before Semgrep starts.

A required run fails closed, before Semgrep starts, when the root is not a Git
work tree, when the scope is empty, or when the explicit targets would exceed
the argv bound (`MAX_TARGET_ARGUMENT_BYTES`, 1,000,000 bytes). A run without
`--required` keeps Semgrep's own scope and `nosem` handling.

Witnesses: `tests/rulesets/test_semgrep_scan_scope.py` (no Semgrep needed) and
`tests/commands/test_semgrep_required_scope_e2e.py` (real Semgrep; run by the
`semgrep rule fixtures` step of `.github/workflows/ci.yml`).

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
