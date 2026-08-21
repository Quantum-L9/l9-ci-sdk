# AGENTS.md — l9-ci-sdk

Operating law for coding agents in `Quantum-L9/l9-ci-sdk`.
Machine-readable `.l9/*` contracts and ADRs are authoritative when prose diverges.

## 1. Constellation role

> **CI Core orchestrates. CI SDK observes. Debt Resolver diagnoses. PR Repair mutates. Debt Intelligence learns. Debt LSP prevents. Assurance decides.**

This repository is the canonical **CI observation and analysis semantics SDK**.

It owns:

- repository capability detection;
- provider SPI/execution/import and provider-native parsing;
- canonical evidence, findings, coverage, failures, identity, classification;
- deterministic bundles and validation;
- technical gate evaluation;
- agent/SARIF projections;
- `l9.observation/v1` construction and validation;
- exact-revision mandatory-findings observation projection;
- stable Python/CLI integration contracts.

It does not own:

- GitHub organization targeting or required-workflow enforcement;
- GitHub Actions orchestration/permissions/artifact upload;
- organization rollout or provider requiredness;
- final Assurance decisions;
- repository/PR mutation;
- fleet learning/corpus;
- LSP/editor prevention loops.

## 2. Authority boundaries

### Core
`Quantum-L9/l9-ci-core` centrally owns organization CI orchestration,
governance defaults, SDK/tool pins, workflow permissions, enforcement, artifact
routing, and publication.

Core may invoke the SDK public CLI. Core must not parse provider-native reports,
reconstruct findings, synthesize rule identity, mutate canonical bundles, or
construct `l9.observation/v1` itself.

### Assurance
`Quantum-L9/l9-assurance` owns producer admission, control evaluation, and the
final organization policy verdict.

SDK `gate evaluate` emits a **technical gate result only**. Never call it an
Assurance decision and never add a final `verdict` field to an SDK observation.

### `.github`
`Quantum-L9/.github` is not an SDK/Core CI distribution plane. Do not publish
copy-in CI workflows or governance packs there.

## 3. Canonical flow

```text
repository
  → capabilities
  → execution selection primitives
  → providers
  → identity
  → policy classification
  → technical gate
  → canonical artifacts
  → observations / projections
```

Dependency direction remains one way: consumers depend on SDK public
contracts; SDK never imports Core, Assurance runtime, Repair, LSP, or corpus
internals.

## 4. Observation v2 contract

Package version `2.0.0` introduces the explicit observation boundary.

Protocol:

- `schema`: `l9.observation`
- `schemaVersion`: `1.0.0`
- producer: `l9-ci-sdk`
- subject kind: exact `git-revision`

Supported checks:

- `l9.repository-metadata`
- `l9.transport-packet`
- `l9.sdk-validation`
- `l9.lint`
- `l9.tests`
- `l9.mandatory-findings`

Observation invariants:

1. exact repository + revision binding;
2. configuration SHA-256 digest required;
3. run ID + attempt required;
4. started/completed timestamps required;
5. deterministic observation ID for identical inputs;
6. no final organization verdict;
7. unknown finding severity is never silently downgraded;
8. mandatory-findings projection retains all canonical findings;
9. Assurance, not SDK, decides which finding severities violate policy.

Public implementation:

- `l9_ci.integration.build_observation`
- `l9_ci.integration.validate_observation`
- `l9_ci.integration.project_mandatory_findings_observation`
- `l9_ci/schemas/v1/observation.schema.json`

CLI:

```text
l9-ci observation build ...
l9-ci observation project-mandatory-findings ...
```

Core supplies factual execution status for centrally orchestrated stages. The
SDK canonicalizes/validates the observation. This keeps workflow logic out of
the SDK and observation semantics out of Core.

## 5. Canonical analysis contracts

Finding bundle:

- protocol `l9.finding-bundle/v1`;
- canonical evidence and findings are separate;
- provider-native rule IDs are always preserved;
- canonical rule IDs require explicit trusted resolution;
- provider facts never embed organization policy verdicts;
- missing required evidence is never equivalent to PASS.

Technical gate states remain `pass | fail | incomplete | invalid`.
They are useful execution signals, not the final Assurance verdict.

## 6. Provider rules

Provider parsing is policy-independent.

Providers must:

- prefer machine-readable provider formats over console output;
- preserve provider IDs and provenance;
- normalize repository-relative paths;
- retain limitations and failures explicitly;
- never produce PR/org rollout policy;
- never invent autofix safety or canonical identity.

Semgrep is the only active in-tree provider until its promotion requirements are met.
Do not introduce a second provider opportunistically.

## 7. Public API and versions

Authoritative public API manifest: `.l9/public-api.yaml`.
Architecture test: `tests/architecture/test_public_api.py`.

Version identity must be equal across:

- `l9_ci.__version__`
- `pyproject.toml` project version
- `.l9/integration-contract.yaml` `metadata.version`

`tests/architecture/test_version_alignment.py` enforces this.

The public CLI currently includes:

- `providers list|detect`
- `semgrep detect|run|normalize`
- `bundle validate|project-agent-payload|project-sarif`
- `gate evaluate`
- `observation build|project-mandatory-findings`
- compatibility / baseline / manifest commands

Exit-code authority remains `l9_ci/cli/exit_codes.py` and the integration contract.

## 8. Contract-change checklist

Any canonical model/protocol/public-surface change must include:

1. owning Python implementation;
2. schema update;
3. `.l9` architecture/ownership/integration update;
4. compatibility assessment;
5. model/schema/integration tests;
6. public API manifest update when exports change;
7. version decision;
8. packaging/lock reconciliation;
9. runtime fixture only when it is real, never fabricated.

## 9. Local validation

Mechanical configuration remains in the repository SSOTs.

Before declaring work complete:

```bash
make bootstrap   # once per clone
make fmt         # only for intentional autofix
make check
```

Also run the full pytest suite when changing contracts, observations, providers,
gates, schemas, packaging, or the CLI.

Do not bypass pre-commit/push checks with `--no-verify`.

## 10. Repository inventory

`MANIFEST.md` is repository inventory reconciled from tracked truth by the SDK
manifest command. It is distinct from Core analysis-artifact manifests.

`memory-bank/` is scratch/history and is not product authority.

## 11. Prohibited shortcuts

Do not:

- fabricate provider fixtures or successful execution evidence;
- turn unknown severity into a supported severity;
- silently discard malformed records;
- retain secret material or absolute host paths in exported artifacts;
- relabel SDK technical gate output as an Assurance decision;
- construct observation IDs from nondeterministic object ordering;
- import Core/Assurance runtime/Repair/LSP/Corpus internals;
- float Core pins on branch names in SDK dogfood workflows;
- claim a release or production trust state that has not been observed.

## 12. Git hygiene

Preserve user work. Do not switch/reset/stash over valuable uncommitted edits.
Keep changes on the assigned branch and push work that must survive.

README is human-facing. Update it only when the task explicitly owns README
realignment or a changed install/CLI path would otherwise make it materially false.
`AGENTS.md`, `.l9/*`, architecture docs, and ADRs carry implementation law.
