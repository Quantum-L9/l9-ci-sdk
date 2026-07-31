<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: ALIGNMENT.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-31
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

1. Path A release evidence is sealed via `docs/release/evidence-map.yaml`.
   `MANIFEST.md` is the live inventory (reconciled by `l9-ci manifest` /
   `.github/workflows/l9-manifest-reconcile.yml`). There is no committed
   `VALIDATION_REPORT.json` at tip — treat historical mentions as absent, not
   current seal. Remaining reseal gap is Path B admin AUD-008 ruleset proofs
   (Path A waived; see evidence-map).
2. Packaging is dual-path and aligned: `pyproject.toml` (local/publish /
   hatchling wheel + `l9-ci` script) mirrors exact runtime pins in
   `requirements.txt` (Core `provision-sdk`). Issue #9 is **closed**.
3. First-party Actions are SHA-pinned; `lint/check_action_pins.py` enforces
   consistency. Issue #5 is **closed**.
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
