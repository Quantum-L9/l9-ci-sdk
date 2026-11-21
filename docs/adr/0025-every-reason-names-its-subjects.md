# ADR 0025: Every failure reason names its subjects

## Status
Accepted (operator directive under `Quantum-L9/.github` L9-SIGNAL-001, CTO
task 2026-11-21).

**Decision owner:** `Quantum-L9/l9-ci-sdk` for the reasons it emits and the
`reason_details` field of `l9.gate-result/v1`. Core's workflow-side outcomes
(the required-instances aggregate) are Core's.

## Context

A remediation agent reading a red CI run had to re-run it to learn what failed.
The SDK emitted count- or status-only reasons, for example:

- `"2 tracked file(s) differ from HEAD"` (which files?);
- `"blocking findings exist: fn_semgrep_<hash>"` (which rule, where?);
- `"Semgrep exited unsuccessfully"` (exit code? stderr?);
- `"finding IDs must be unique"` (which IDs?).

## Decision

1. Every failure, incomplete or unresolved reason the SDK emits names its
   subjects:

   | Reason class | Subject |
   |---|---|
   | blocking, unresolved, unclassified finding | `<canonical or provider rule ID> at <path>:<line>` |
   | required provider failure (fatal or not) | `<provider>: <failure type>: <message>` |
   | incomplete required coverage | `<provider>: coverage <status>: <limitations>`, or `<provider>: no coverage record` |
   | provider execution failure | exit code and the last stderr line |
   | runner failure | the executable, the report path, the configuration or report-shape errors |
   | baseline refusal (ADR 0023) | the changed paths, the resolved commit, the baseline scan's failures or limitations |
   | bundle validation | each duplicated ID with its count |
   | compatibility | the received value and its type |

2. Subjects are sorted, de-duplicated and capped at 20, the rest counted as
   `(+N more)`: `l9_ci.contracts.subject_reason` / `format_subjects`. Building a
   reason with no subject raises.
3. No absolute path enters a reason: paths are repository-relative, and tool
   output (stderr, exception text) has absolute paths shortened to `…/<name>`
   (`l9_ci.contracts.subjects.strip_absolute_paths`, `display_path`,
   `text_tail`).
4. `l9.gate-result/v1` gains `reason_details`: one entry per reason with
   `code`, `subjects` (at most 20) and `omitted`. Codes:
   `missing_classifications`, `required_provider_failed`,
   `required_provider_nonfatal_failure`, `required_coverage_incomplete`,
   `blocking_findings`, `unresolved_findings`. `reasons` keeps the same
   subjects as text; `blocking_finding_ids` and the other ID lists stay
   complete and uncapped.
5. `tests/gates/test_reason_subjects.py` holds one witness per reason class and
   a static invariant: in `l9_ci/gates`, `pipeline`, `providers` and
   `artifacts`, no `reasons`, `errors` or `limitations` append and no provider
   failure message may be a literal without an interpolated subject.

## Source snippets: rendered by the SDK, never stored (CTO decision A)

An agent needs the offending line, not only its location. The canonical
finding bundle still carries no source content (AGENTS.md; `.l9/release-policy.yaml`
"no raw secret or source snippet leakage"; the redaction validator): a finding
names its rule, path, line, end line and message only.

6. `l9_ci.signal.render_snippet(root, path, line, end_line, *, sensitive)` reads
   the offending lines from `root`, a checkout of the scanned revision, with two
   lines of context, line-numbered and the offending lines marked (`>`). An
   absolute or escaping path, a symlink, a missing, binary, non-UTF-8 or
   oversized file, or a line outside the file yields `status: unavailable`
   with the reason. A sensitive provider (`SENSITIVE_PROVIDERS`: gitleaks,
   trufflehog, detect-secrets, secret-scan) yields `status: masked` without
   the file being read, so no byte of a detected secret can leave this way.
7. `report_findings(root, findings)` returns at most 20 located findings,
   sorted by path and line, plus how many more, each as
   `{rule_id, path, line, end_line, message, snippet}` with
   `snippet = {path, line, end_line, status, lines: [{line, text, offending}], reason?}`.
   A sensitive provider's message is masked too. `render_findings` renders the
   same as text: `rule_id path:line` and the snippet per finding, then
   `+N more`. Core builds its agent-review payload, CI log and step summary
   from these; the field names are the payload contract agreed with Core.

## Compatibility and version decision

- `reason_details` is a new property of the gate result: gate-result schema
  version 1.0.0 -> 1.1.0 (additive, COMPAT-002). A 1.0.0 reader that rejects
  unknown properties rejects a 1.1.0 result; Core adopts the reader with the
  SDK pin that writes it.
- Reason and message texts changed: each keeps its old wording as a prefix
  (two coverage limitations drop their sentence-final period) and appends its
  subjects, so a reader that matched a prefix still matches.
  Nothing should parse the text: `reason_details` is the machine form.
- The finding bundle protocol and schema are unchanged.
