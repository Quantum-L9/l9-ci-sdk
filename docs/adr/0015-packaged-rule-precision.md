# ADR 0015: A Packaged Rule Must Constrain What It Claims to Match
## Status
Accepted
## Context
ADR-0009 made the packaged Semgrep ruleset a public SDK contract: every
downstream repository inherits these rules by upgrading the SDK, and does not
author a `--config` list of its own. That makes rule *precision* part of the
contract too — a rule that over-matches costs every consumer a suppression,
and a suppression records nothing about the risk the rule exists to find.

Two packaged rules over-matched, for two different reasons, and a fleet scan
across ten repositories attributed 79 of 183 findings to them. Not one was a
true positive.

`l9.logging.forbidden-secret-field` and
`l9.handler.missing-transportpacket-return` each declared `metavariable-regex`
as a sibling of `pattern` / `pattern-either`. Semgrep honours that operator
only as an item of a `patterns` list; at rule top level it is silently
dropped, and `semgrep --validate` still reports the configuration valid. The
constraint therefore never applied: the logging rule matched every `logger.*`
or `logging.*` call carrying at least one argument, `logging.getLogger(...)`
included, and the handler rule would have flagged the compliant
`-> TransportPacket` signature it exists to require.

`l9.routing.gateclient-bypass-execute` was authored as
`pattern-regex: '/v1/execute|/execute'`. A `pattern-regex` rule searches raw
file text with no syntactic context, so it matched every mention of the path
in any position — a filename ending in `execute.md`, CLI help text about
skipping a paste step, an error string naming `execute_via` frontmatter, and
docstrings that merely describe the Gate-routed endpoint. The rule's own
message is about raw `/execute` *calls* bypassing GateClient.

## Decision
- A constraint operator (`metavariable-regex`, `metavariable-pattern`,
  `metavariable-comparison`, `metavariable-type`, `metavariable-analysis`,
  `focus-metavariable`, `pattern-inside`, `pattern-not`, `pattern-not-inside`,
  `pattern-not-regex`) is nested under `patterns` in every packaged rule.
  `semgrep --validate` does not enforce this, so
  `tests/rulesets/test_packaged_rule_metadata_shape.py` does, over the whole
  operator class rather than the two rules that were wrong.
- A `pattern-regex` rule scopes its match to the syntax it claims to govern.
  `gateclient-bypass-execute` now requires a string literal that ends at the
  `/execute` path, which still catches a request URL, a routing constant, and
  an f-string building either, while ignoring prose. Direct dispatch by any
  path remains covered structurally by AST-ROUTING-001/002.
- The boundary cases for a regex rule are pinned as test data asserted against
  the pattern loaded from the packaged YAML, not restated in a comment, so the
  rule cannot drift back to a text search unnoticed.

## Consequences
- Rule identity is unaffected. No `id` or `metadata.l9.canonical_rule_id`
  changed, so the packaged identity map, the repo-local mirror it must stay
  byte-identical to, and every consumer's finding-policy key keep resolving as
  before. This is a precision change, not an ADR-0003 identity change.
- Consumers inherit the correction by upgrading the SDK, per ADR-0009. A
  consumer that suppressed one of these rules to silence the false positives
  can drop the suppression; one that did not will see its finding count fall.
- `gateclient-bypass-execute` will not flag an `/execute` path assembled
  entirely from variables. That is accepted: the previous behaviour caught it
  only as a side effect of matching everything, and AST-ROUTING-001/002 flag
  the dispatch itself regardless of how the path was built.
- A rule promoted past `shadow` under `.github/governance/promotion-policy.yaml`
  is only as trustworthy as its precision. Observation runs collected against
  an over-matching rule do not evidence readiness to promote it.
