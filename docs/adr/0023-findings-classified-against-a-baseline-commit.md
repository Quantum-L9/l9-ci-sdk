# ADR 0023: Findings are classified new or pre-existing against a baseline commit

## Status
Accepted (CTO ASSIGN CENTRAL-DIFF, 2026-11-21).

**Decision owner:** `Quantum-L9/l9-ci-sdk` for the classification, the bundle
field and the fail-closed rules; `Quantum-L9/l9-ci-core` for choosing the
baseline commit and passing it (see "Core inputs"). **Related:** ADR 0022
(supersession), the finding-waiver ledger (`l9.finding-waivers/v1`). Not
related to the `l9-ci baseline` command group, which compares scanner output
against a ledger of accepted debt, not against a git commit.

## Context

SDK #134 put `tests/` into required scope. Pinning that SDK in Core (canary run
44864948490) turned findings that already existed in `tests/` into blockers in
every repository: SDK 104, CEG 91, EIE 19, Core 1. A precision change to what
is scanned must not make a pull request fail for code it did not touch. Core
therefore needs to tell findings a change introduced from findings already on
the target branch.

## Decision

1. `l9-ci semgrep run --baseline-commit SHA` (a full commit ID; Core passes
   the merge-base with the target branch) runs the scan twice: the full scan
   as before, then the same command with Semgrep's own `--baseline-commit`.
   Semgrep documents that option as "Only show results that are not found in
   this commit hash" and decides it by re-scanning the baseline in a git
   worktree. Verified on Semgrep 1.171.0: a finding that moved lines or whose
   file was renamed (with or without edits) is not reported by the baseline
   scan.
2. A finding of the full scan is `new` when the baseline scan reports a result
   with the same fingerprint (both scans read the same working tree, so the
   match is exact), and `pre_existing` otherwise.
3. `FindingClassification.baseline_status` records `new`, `pre_existing` or
   `unknown`. A `pre_existing` finding whose policy mode is `blocking` is
   reported as `advisory`, keeping its policy key, version and any waiver. A
   `new` finding keeps its policy mode, so a new blocking finding fails the
   gate. The bundle states the counts in one limitation:
   `baseline <sha>: N new, M pre-existing (K blocking reported as advisory), U unknown`.
4. Fail closed (L9-UNKNOWN-001). The baseline is `unknown` when the commit does
   not resolve (an unknown hash, or a shallow clone without it), when a tracked
   file differs from HEAD (Semgrep 1.171.0 does not abort on unstaged changes,
   although its documentation says it does, so the SDK refuses), or when the
   baseline scan failed or is incomplete. Then every finding is `unknown` and
   keeps its policy mode, and the bundle carries a required, fatal provider
   failure, so the gate is INCOMPLETE and never PASS.
5. An incomplete head scan stays INCOMPLETE whatever the classification: the
   gate checks coverage before findings.
6. Without `--baseline-commit` nothing changes and no `baseline_status` is
   written. The option requires `--policy`.

## Core inputs

Core checks out enough history for the merge-base to exist (`fetch-depth: 0`,
or a fetch of the base commit) and passes
`--baseline-commit "$(git merge-base origin/<base> HEAD)"` on pull requests.
On a push to the default branch it omits the option, so every finding is
judged by policy alone. The baseline scan roughly doubles scan time on pull
requests; Semgrep limits it to files that have findings.

## Compatibility and version decision

- `baseline_status` is a new optional property of `FindingClassification`, and
  `BaselineStatus` a new public contract enum. Additive within the major
  (COMPAT-002, COMPAT-004): finding-bundle schema version 1.1.0 -> 1.2.0. A
  tolerant reader ignores the field; no field is removed or renamed and no
  identity input changes (fingerprints are untouched).
- A strict 1.1.0 reader that rejects unknown properties rejects a 1.2.0 bundle
  that carries the field. That is only written when Core passes the new
  option, so Core adopts the reader and the option together.
