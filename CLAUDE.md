<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: CLAUDE.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Agent Operating Contract

## Always

- Read `AGENTS.md`, `.l9/integration-contract.yaml`, and
  `.l9/architecture.yaml` before changing contracts.
- Preserve native provider rule IDs and explicit identity resolution.
- Update Python models, JSON Schemas, compatibility analysis, invariant tests,
  and schema tests together for canonical contract changes.
- Use real machine-readable, redacted provider fixtures.
- Keep outputs deterministic, atomic, repository-relative, and validated.
- Run `ruff check .`, `ruff format --check .`, `mypy l9_ci`, and `pytest -q`.
- Distinguish advisory CI from blocking CI in every review summary.
- Update an ADR when architectural semantics change.

## Never

- Parse human-readable scanner output when structured output exists.
- Derive canonical identity from severity or guess unknown identities.
- Convert required provider failures or missing evidence into PASS.
- Import workflow orchestration into the SDK.
- Import artifact internals into providers.
- Retain secrets or absolute source paths in canonical artifacts.
- Fabricate test fixtures, counts, validation results, or manifest freshness.
- Hand-edit generated evidence files.
- Change the Core SHA in only one profile caller.

## Live CI facts

- Self-CI has 9 jobs.
- New-secret scanning is the only default hard-blocking job.
- The final gate is rule-mode aware.
- Ruff, mypy, validation, Semgrep, audit, and SBOM are advisory.
- Five Core analysis profile callers are advisory/non-strict.
- Pre-commit has two hooks: `ruff --fix` and `ruff-format`.

## References

- Architecture: `ARCHITECTURE.md`
- Invariants: `INVARIANTS.md`
- Operations: `RUNBOOK.md`
- Validation: `VALIDATION.md`
- Alignment gaps: `ALIGNMENT.md`
- ADR ledger: `docs/adr/README.md`
- Compatibility: `docs/COMPATIBILITY_MATRIX.md`

No repository-local `.claude` adapter or skill registry was found. Do not claim
one is installed inside this repository.

<!-- BEGIN L9 FORMATTER OWNERSHIP (generated — do not edit) -->

## Formatter ownership

Workspace class: `biome_default` — Default for every governed workspace: Biome owns JS/TS/JSON, Ruff owns Python.

Exactly one formatter owns each language. Do not reformat a file with a tool other than its owner, and do not add config for a competing formatter: the result is a diff that churns on every save.

| Languages | Owner | Note |
|---|---|---|
| `javascript`, `javascriptreact`, `typescript`, `typescriptreact`, `json`, `jsonc` | **biome** | bound by the governed IDE profile |
| `python` | **ruff** | bound by the governed IDE profile |

Generated from `environment/ide/policy.json` in the governance clone by `ops/scripts/adapters/agentdocs.sh`. Edit the policy, not this block.

<!-- END L9 FORMATTER OWNERSHIP -->
