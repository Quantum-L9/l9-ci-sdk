# ADR 0009: Ship a Global, Versioned Semgrep Ruleset and Identity Map as SDK Package Data
## Status
Accepted
## Context
L9-authored Semgrep rules were originally written with `metadata.l9_rule_id`,
a flat key the identity resolver never reads; ADR-0003 requires
`metadata.l9.canonical_rule_id`. Every finding from those rules silently fell
through to unresolved identity instead of erroring. Separately, each
downstream repository was expected to author and maintain its own
`semgrep --config` ruleset list per language in its caller workflow, and
community registry rulesets (`p/python`, `p/typescript`) carry no L9
canonical identity at all, so strict identity resolution was not enforceable
for the most widely used rules.
## Decision
- The SDK ships one versioned Semgrep ruleset per supported language
  (`l9_ci/rulesets/semgrep/{python,typescript}/`) and one packaged identity
  map (`l9_ci/rulesets/semgrep/identity-map.yaml`, a mirrored copy of the
  human-reviewed `.l9/semgrep-identity-map.yaml`) as installable package
  data, resolved through `importlib.resources` so lookup is identical
  whether the SDK runs from a source checkout or an installed wheel.
- Every L9-authored rule embeds trusted `metadata.l9.canonical_rule_id` per
  ADR-0003. The packaged identity map exists only to resolve third-party
  registry `check_id`s the SDK does not author.
- `l9-ci semgrep run --language {python,typescript}` composes
  `provider.execute()` (community registry ruleset + packaged L9 ruleset)
  and `run_semgrep_pipeline()` (normalization against the packaged identity
  map) into one CLI verb, replacing a caller-authored `semgrep scan --config
  ...` step followed by a separate `l9-ci semgrep normalize` step.
- A caller selects a language with one `--language` flag (`env.L9_LANGUAGE`
  in the reference workflow templates); it does not author or maintain a
  `--config` list.
## Consequences
- A downstream repository inherits ruleset and identity-map updates by
  upgrading the SDK version; it does not fork or hand-maintain `--config`
  lists.
- Community registry findings with no packaged identity-map entry remain
  `UNRESOLVED` per ADR-0003, not silently misclassified.
- A packaging regression that drops ruleset or identity-map files from the
  wheel is caught by `tests/rulesets/test_packaging.py` rather than
  surfacing only in a downstream consumer's CI.
- `--extra-config` and `--no-registry-config` remain available for a caller
  that needs to add to or replace the packaged default ruleset.
