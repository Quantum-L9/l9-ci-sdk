<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: ALIGNMENT.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Alignment

## Authority order

1. `.l9/integration-contract.yaml` for SDK/Core ownership, CLI, and exit codes
2. `.l9/architecture.yaml` for package boundaries and canonical flow
3. `.l9/tool-stack.yaml` for supported stack, scope, and Python floor
4. `.l9/compatibility.yaml` for version and schema rules
5. Code and tests
6. `AGENTS.md` for contributor constraints
7. Human-readable documentation

## Alignment passes

| Pass | Rule | Evidence |
|---|---|---|
| Boundary | SDK must not own Core orchestration | Architecture and integration contracts |
| Identity | Canonical IDs require explicit resolution | Identity resolver and provider tests |
| Artifact | Schema and semantic validation are both required | Artifact validator and contract tests |
| Requiredness | Missing required evidence cannot pass | Gate evaluator and failure contracts |
| Determinism | Serialization and snapshot identity are stable | Determinism and repository tests |
| Redaction | Secret material is not retained | Integration redaction tests and gitleaks |
| Compatibility | Unsupported majors are rejected | Compatibility fixtures and rules |

## Known alignment gaps

1. `MANIFEST.md` and `VALIDATION_REPORT.json` describe the earlier 158-file
   bundle and omit later CI/governance scaffolding. No tracked reseal generator
   exists, so generated evidence cannot be truthfully refreshed in this pass.
2. Open issue #9 tracks packaging/scaffolding. The live branch intentionally has
   no `pyproject.toml`; runtime execution is source-based over `PYTHONPATH`.
3. Open issue #5 tracks immutable SHA pinning for remaining first-party actions.
4. The organization contributing template prefers `@v1` for thin callers, while
   this repository's deployed profile callers deliberately pin Core by commit
   SHA. The repository-specific immutable pin is the live authority.
5. The architecture spec revision is `1.1.0`, while the SDK runtime and
   integration contract version are `1.0.0`. These are distinct axes and must
   remain explicitly labeled.

## Allow-lists and intentional exclusions

- Ruff excludes `docs/`.
- Community Semgrep rules remain advisory because canonical L9 identity is not
  embedded.
- Advisory CI jobs may continue after findings so the final gate can aggregate
  evidence.
- Generated evidence files are never hand-edited to manufacture freshness.
