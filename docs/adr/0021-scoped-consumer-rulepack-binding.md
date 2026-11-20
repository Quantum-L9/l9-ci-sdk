# ADR 0021: Scoped consumer rulepack binding

## Status
Proposed. Design for review before implementation (lane L1-CANARY-FIXES, item
B3). No code ships with this ADR.

**Decision owner:** `Quantum-L9/l9-ci-sdk` for the declaration schema,
validation, composition, execution and evidence; `Quantum-L9/l9-ci-core` for
planning, requiredness and the workflow step (see "Core change"). **Related:**
ADR 0009 (packaged Semgrep rules), ADR 0016 (organization-managed CI), ADR 0020
(decision 3: monotonic composition, "authorized product-specific rules or
constrained extensions"), `l9_ci/rulesets/semgrep/composition.py`
(`product_configs`), `l9_ci/rulesets/semgrep/scan-scope.yaml` (#128).

## Context

Cursor-Governance's canary (`CURSOR_CANARY_RESULT.md`, item B3) found that the
four Cursor-owned rules in `.semgrep/l9-pr.yml` run in no CI job:

- `l9.no-semgrep-app-token-in-child-env`
- `l9.memory-boundary-no-network-or-provider-transport`
- `l9.memory-boundary-spawn-only-through-the-binding`
- `l9.memory-boundary-no-shell-string-spawn`

Central Semgrep never loads consumer rule files, and only the local `make pr`
gate (`ops/scripts/run_pr_security.sh`) runs them. Each rule already scopes
itself with Semgrep's own `paths.include` and `paths.exclude`, and each states
a domain invariant (INV-03) that belongs to Cursor-Governance, not to the SDK.

The constraints come from what is already decided. Central required coverage is
never reduced by consumer configuration (#128, ADR 0020 decision 3). Aggregating
arbitrary consumer `.semgrep` content is rejected (ADR 0020 alternatives). The
SDK does not take over a product's semantic ownership.

## Decision

1. **Consumers declare; they do not drop in.** A consumer opts in with one
   file, `.l9/semgrep-consumer-rules.yaml`:

   ```yaml
   schema: l9.semgrep-consumer-rulepack/v1
   owner: Quantum-L9/Cursor-Governance
   rule_files:
     - .semgrep/l9-pr.yml
   ```

   Only listed files are loaded. An undeclared `.semgrep/` directory stays
   unread, as it is today.

2. **The SDK validates before anything runs. Any violation fails the consumer
   instance, never the central one.** It checks that:

   - every rule ID is namespaced to the consumer (a declared prefix, `l9.` by
     default for Quantum-L9 repositories, and never one of the SDK's packaged
     IDs; `compose_rulepack` already refuses a product config that redefines a
     packaged rule, and this reuses that path);
   - every rule carries its own `paths.include`. A consumer rule with no path
     scope is refused, so a rule cannot claim the whole repository by accident;
   - every rule carries `metadata.l9.canonical_rule_id` in a consumer namespace
     (`CONSUMER-<OWNER>-<NAME>`), so strict identity resolution needs no map;
   - no rule uses the Semgrep-wide options that change other rules' behaviour;
     the allow-list is the per-rule keys only.

3. **Consumer rules only add findings, by construction.** They run as a
   separate execution, `l9-ci semgrep run --consumer-rules`, with its own
   bundle. The central required execution and its bundle, scope and gate are
   untouched. A Semgrep rule cannot suppress another rule's finding, so a
   consumer rule can neither subtract nor rewrite central evidence.

4. **Consumer scope is the consumer's.** The consumer execution keeps the
   consumer's `.semgrepignore` and inline `nosemgrep`, matching the CTO
   direction that consumer-owned rules keep consumer ignores, and each rule's
   own `paths` narrows it further. Its scope evidence (`.scope.json`) records
   which ignores were honoured, unlike the central record, which honours none.

5. **Evidence keeps ownership visible.** The consumer bundle names the
   declaration file and its SHA-256, every rule file by SHA-256, and the owner.
   Findings carry the consumer canonical IDs, never central ones, so Core's
   policy and Assurance can tell a domain rule from a central rule.

6. **The inventory reports the declaration as a target.** The analysis target
   is `semgrep consumer:<owner>`, with a new target scope `consumer`. It is:

   - `applicable` when the declaration validates and at least one declared
     rule's `paths.include` matches a tracked file;
   - `not_applicable` when no consumer declaration exists;
   - `failed` when the declaration does not validate.

   This adds a target scope value to `l9.capability-inventory/v1`, a minor
   schema bump.

## Core change (for L2)

1. Add `consumer` to `plan-required-instances/executable-targets.json` for
   `semgrep`, so the planner carries a `semgrep:consumer:<owner>` instance.
2. Add one step to `org-ci.yml` that runs the consumer execution for that
   instance, after the central one, with the same SDK and Semgrep pins, and
   uploads its bundle and scope record beside the central ones.
3. Decide requiredness. The SDK proposes the consumer instance as required for
   the declaring repository and advisory elsewhere, but requiredness is
   Core's.

No Core change is needed before the SDK side exists: until Core plans the
target, the inventory merely reports it.

## Alternatives considered and rejected

- **Load every `.semgrep/*.yml` into the central run:** consumer content would
  mix into the central bundle and could carry unscoped or colliding rules
  (ADR 0020, rejected alternative).
- **Copy the four rules into the SDK's packaged packs:** moves INV-03 ownership
  out of Cursor-Governance and makes every consumer run memory-path rules that
  only make sense in one repository.
- **Keep local `make pr` enforcement only:** the canary's B3. The rules never
  run in CI, so a push that bypasses the local gate is never checked.

## Consequences

- Cursor-Governance adds `.l9/semgrep-consumer-rules.yaml`, and its four rules
  gain `metadata.l9.canonical_rule_id`. Their existing `paths` already satisfy
  decision 2.
- Implementation is one SDK PR: the schema, validation, `--consumer-rules`
  execution, inventory target and witnesses. The witnesses are a consumer
  known-bad that fires only inside its declared paths, and an unscoped or
  colliding rule that is refused. One Core PR follows (the "Core change"
  above).
- Local `make pr` enforcement stays until the Core step is live and a canary
  re-run shows the four rules firing in CI (`L9-CI-CORE-004`).
