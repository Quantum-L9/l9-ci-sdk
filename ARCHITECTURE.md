<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: ARCHITECTURE.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Architecture

## Version axes

- SDK runtime version: `1.0.0`
- Architecture specification revision: `1.1.0`
- Artifact protocol: `l9.finding-bundle/v1`
- Schema version: `1.0.0`

These are separate axes. Do not infer SDK compatibility from artifact shape.

## Canonical flow

```text
repository -> capabilities -> execution -> providers -> identity
           -> policy -> gates -> artifacts -> projections
```

`l9-ci-sdk` produces local deterministic evidence. `l9-ci-core` owns GitHub
Actions orchestration, permissions, provider enablement, uploads, retention,
publication, and organization rollout.

## Package index

| Package | Responsibility | Key boundary |
|---|---|---|
| `contracts` | Immutable canonical models, enums, invariants | Standard library only |
| `repository` | Enumeration, Git inspection, snapshot identity | No provider/policy/gate/integration imports |
| `capabilities` | Repository capability detection | Contracts + repository |
| `providers` | SPI, execution/import, normalization, coverage | No artifacts/gates/integration/workflow imports |
| `identity` | Explicit canonical rule identity | Contracts only |
| `policy` | Policy loading and classification | No providers/artifacts/gates |
| `execution` | Profiles and provider selection | Capabilities + providers |
| `artifacts` | Serialization, schema/semantic validation, atomic writes | No providers/policy/gates |
| `gates` | Gate evaluation | No providers/policy/integration |
| `pipeline` | Public SDK composition | Composes public layers |
| `integration` | Limits, versioning, redaction, projections | No providers/pipeline |
| `cli` | Exit codes, diagnostics, output | Standard library boundary |
| `commands` | Public command composition | Public SDK packages only |

## Public surface

The authoritative public package set is `contracts`, `repository`,
`capabilities`, `providers`, `identity`, `policy`, `execution`, `artifacts`,
`gates`, `integration`, and `cli`. `pipeline` and `commands` are composition
layers rather than independent contract roots.

## CI/CD topology

```text
PR/push/dispatch
  -> l9-self-ci.yml
     -> classify
     -> secret_scan (only default hard block)
     -> validate, lint, typecheck, semgrep, audit, supply_chain (advisory)
     -> pr_pipeline_gate (rule-mode aware)

pull_request / merge_group (GitHub organization required-workflow ruleset)
  -> Quantum-L9/l9-ci-core main .github/workflows/org-ci.yml (not in this tree)
     -> resolve central governance
     -> provision the SDK revision Core selects (.l9/sdk-compatibility.yaml in Core)
     -> l9-ci semgrep run -> normalize and validate bundle
     -> l9-ci gate evaluate -> project agent payload and SARIF
     -> route, manifest, upload artifacts; required check "Analyze (central Core)"
```

This repository holds no Core caller, Core SHA, or SDK SHA (ADR-0016). Core
analyzes this repository with the SDK revision Core has admitted, not with the
tree under review; the SDK's own in-tree dogfood is the `semgrep` job of
`l9-self-ci.yml`.

## Non-goals

The SDK does not own workflow orchestration, hosted services, LLM orchestration,
repair, LSP/editor diagnostics, historical corpus storage, or repository
mutation.
