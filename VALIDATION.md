<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: VALIDATION.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Validation

## Evidence sets

| Evidence | Current status |
|---|---|
| `VALIDATION_REPORT.json` | Historical sealed baseline; 75 tests passed |
| `MANIFEST.md` | Historical 158-file inventory |
| Self-CI artifacts | Live per-run CI context, summary, agent payload |
| L9 analysis artifacts | Raw Semgrep report, canonical bundle, agent payload, metadata manifest |
| Compatibility fixtures | Bundle v1 valid/invalid and unsupported v2 fixtures |

## Live validation surfaces

- Python compilation and YAML parsing
- Ruff lint and format checks
- mypy type checking
- pytest suites across architecture, contracts, repository, providers, policy,
  gates, pipeline, integration, and compatibility
- Diff-scoped gitleaks for new secrets
- Semgrep provider report import and normalized artifact validation
- Rule-mode-aware final gate

## Local regeneration

```bash
python -m pip install -r requirements-ci.txt
ruff check .
ruff format --check .
mypy l9_ci
pytest -q
PYTHONPATH=. python -m l9_ci providers list
PYTHONPATH=. python -m l9_ci providers detect --root .
```

## Baseline result

The committed report records compile, Ruff, formatting, 75 tests, CLI provider
listing/detection, and cache hygiene as passing. It also records two empirical
blockers: no runtime-captured redacted Semgrep fixture and no verified live Core
invocation.

## Freshness rule

Do not claim that the 158-file report covers the current CI-expanded tree. No
`generate_manifest` tooling is present in the tracked inventory, so this
remediation intentionally leaves generated evidence unchanged and records the
reseal gap in `ALIGNMENT.md` and `ROADMAP.md`.
