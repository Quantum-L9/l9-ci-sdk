# Deterministic Governance-Evidence Layer

## Purpose

This SDK layer validates and compares governance evidence without acquiring orchestration or decision authority.

It owns only deterministic, offline primitives:

- contract-set hashing and digesting;
- promotion-transition and supplied-evidence eligibility evaluation;
- constitution-to-attestation comparison;
- authority-surface delta observation;
- governed evidence-report validation;
- immutable diagnostics and evaluation results.

## Explicit exclusions

The layer must not:

- call GitHub, scanners, services, or network APIs;
- read workflow context or repository history;
- mutate repositories, PRs, ledgers, constitutions, or artifacts;
- approve promotions or authority changes;
- publish checks or artifacts;
- make assurance or release decisions.

Core collects inputs and orchestrates execution. Consumer repositories own policy and constitution instances. Assurance or a human authority decides. The SDK reports facts and deterministic evaluations.

## Status semantics

- `invalid`: malformed inputs or unsupported contract values;
- `incomplete`: required evidence is absent or a required dependency is not ready;
- `fail`: supplied evidence contradicts declared state;
- `pass`: evidence is structurally valid and consistent;
- `eligible`: a legal promotion transition satisfies supplied requirements;
- `ineligible`: the transition is legal but supplied evidence does not satisfy requirements.

Authority comparison intentionally returns `pass` with warning diagnostics when it successfully observes changes. It does not approve those changes.

## Dependency boundary

`l9_ci.governance` depends only on the Python standard library and its own immutable result models. It does not import Core, GitHub clients, provider execution, gates, repair systems, or publication code.
