# ADR 0022: A packaged L9 rule supersedes a registry rule only at the sites it covers

## Status
Accepted (lane L1, CTO item 1, 2026-11-21).

**Decision owner:** `Quantum-L9/l9-ci-sdk`. **Related:** ADR 0009 (packaged
Semgrep rules), ADR 0020 (lossless provider facts; mutable remote registry
labels alone do not make a composition reproducible).

## Context

A `semgrep run` under profile `l9-standard` composes the community registry
ruleset (`p/python`) with the packaged L9 ruleset. Two rules then report the
same `shell=True` call: `l9.baseline.python.subprocess-shell-true` and
`python.lang.security.audit.subprocess-shell-true.subprocess-shell-true`. On
Cursor-Governance run 44848823829, 12 of 29 blocking findings were these pairs.

The first version of this change skipped the registry rule with Semgrep's
`--exclude-rule`, on the strength of a witness that the L9 rule matches every
site the registry rule matches. Codex review on #143 found the gap: `p/python`
is fetched unpinned, so a later revision of the registry rule can match a site
the packaged L9 rule does not, and an up-front exclusion would drop that
finding from a required run with nothing recorded.

## Decision

1. `l9_ci/rulesets/semgrep/rule-overlaps.yaml` (`l9.semgrep-rule-overlaps/v1`)
   declares which registry rule each packaged L9 rule supersedes. An entry is
   admitted only with a real-Semgrep witness that every registry match lies
   inside an L9 match (`tests/rulesets/test_semgrep_rule_overlaps.py`).
2. Nothing is excluded before the scan. Both rules run.
3. After normalization, `l9_ci.pipeline.overlaps.supersede_findings` withdraws
   a registry finding only when a finding of its superseding L9 rule is in the
   same file and its span contains the registry finding's start line. A
   registry finding no L9 finding covers stays and is classified as usual.
4. A withdrawn finding's evidence record stays in the bundle, and the bundle
   records one limitation per withdrawn registry rule with every site.
5. A required run records the supersessions it applied in its scan-scope
   evidence: `rule_overlaps`, with the registry's version and SHA-256 and
   `applied: covered_sites_only`.

## Compatibility and version decision

- `rule_overlaps` is a new optional property of `l9.semgrep-scan-scope/v1`
  evidence, so the change is additive within the major (COMPAT-002): schema
  version 1.1.0 -> 1.2.0. A tolerant reader ignores it; no field is removed or
  renamed and no identity input changes.
- The finding bundle protocol and schema are unchanged. A withdrawn registry
  finding is absent from `findings`, which a reader already handles; its
  evidence and a limitation stay, so no evidence is lost (AGENTS.md section 5:
  missing required evidence is never equivalent to PASS).
- The archived-scope change (#142) also moves scan-scope evidence from 1.1.0
  to 1.2.0 for a different additive field. Whichever of the two merges second
  takes 1.3.0 when it merges the base; the two fields do not interact.

## Consequences

- A `shell=True` site is reported once, under `L9-PYTHON-SUBPROCESS-SHELL-TRUE`.
- A registry rule revision that widens what it matches surfaces its new sites
  instead of hiding them.
- Both rules cost scan time; that is the price of not pinning `p/python`.
