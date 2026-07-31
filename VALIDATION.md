<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: VALIDATION.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-31
/L9_META -->
# Validation

## Evidence sets

| Evidence | Current status |
|---|---|
| `VALIDATION_REPORT.json` | Absent at tip — not a current seal |
| `MANIFEST.md` | Live repository inventory via `l9-ci manifest` (reconcile workflow) |
| Self-CI / self-validation artifacts | Live per-run CI evidence (see `docs/release/evidence-map.yaml`) |
| L9 analysis artifacts | Raw Semgrep report, canonical bundle, agent payload, Core publish |
| Compatibility fixtures | Bundle v1 valid/invalid and unsupported v2 fixtures |
| Runtime Semgrep fixture | `tests/fixtures/semgrep/runtime/` + provenance |

## Live validation surfaces

- Python compilation and YAML parsing
- Ruff lint and format checks
- mypy type checking
- pytest suites across architecture, contracts, repository, providers, policy,
  gates, pipeline, integration, and compatibility
- Diff-scoped gitleaks for new secrets
- Semgrep provider report import and normalized artifact validation
- Rule-mode-aware final gate
- Biome / YAML governance / action-pin / zizmor hooks (local `make check`)

## Local regeneration

```bash
make bootstrap   # once per clone
make check       # hooks + mypy + pytest (fail-closed local gate)
PYTHONPATH=. python -m l9_ci providers list
PYTHONPATH=. python -m l9_ci providers detect --root .
PYTHONPATH=. python -m l9_ci manifest check --tracked-only --exclude-dir memory-bank
```

## Baseline result

Current tip: `make check` green (388 tests at Path A audit). Runtime-captured
Semgrep fixture is present and exercised by
`tests/providers/semgrep/test_runtime_fixture.py`. Thin Core analysis callers
pin `analyze-semgrep.yml@c3f04e1…` and dogfood on `main`.

## Freshness rule

Do not hand-edit `MANIFEST.md` to manufacture freshness — regenerate with
`l9-ci manifest generate` / reconcile workflow. Path A release evidence URLs and
SHAs are owned by `docs/release/evidence-map.yaml`; do not reintroduce
`{{PLACEHOLDER}}` tokens into seal files.
