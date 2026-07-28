---
# Biome Static Checks

SDK-owned static checks (format, recommended lint rules, import
organization) for JSON/JS/TS assets, enforcing the Biome formatter ownership
already declared in `AGENTS.md`. See [ADR 0011](../adr/0011-biome-static-checks.md).

## Layout

| Path | Role |
|---|---|
| `biome.json` | Repo-root config (same convention as `ruff.toml`) |
| `.github/workflows/l9-biome-scan.yml` | Reusable `workflow_call` |
| `.github/workflows/l9-biome-scan-dogfood.yml` | This repo's dogfood caller |
| `.pre-commit-config.yaml` (`biome-check`) | Local autofix hook |
| `docs/templates/l9-biome-scan-caller.yml` | Downstream caller template |
| `tests/biome/` | Structure-validation tests |

`biome.json` lives at the repository root (same convention as `ruff.toml`),
**not** under `.github/`.

## Reusable inputs

| Input | Default | Notes |
|---|---|---|
| `scan-path` | `.` | Path argument passed to `biome ci` |
| `enforce-biome` | `false` | Advisory until promoted |

## Scope

`biome.json` `files.includes` covers `**/*.{json,jsonc,js,jsx,ts,tsx}` and
excludes `tests/fixtures` and `tests/compatibility/fixtures` — those
directories intentionally hold malformed/non-canonical JSON used to test
provider parsing failure paths, so they are never reformatted or linted.

## Local validation

SSOT is `.pre-commit-config.yaml`:

```bash
pre-commit run biome-check --all-files   # full pre-commit suite entry point
pytest tests/biome -q
```

Raw expansion (debugging only — do not diverge flags from the hook config):

```bash
npx --yes @biomejs/biome@2.5.5 ci .
npx --yes @biomejs/biome@2.5.5 check --write .
```

If this capability is combined with the YAML-governance root `Makefile`
(`make hooks` / `make check` / `make push`), add a `biome-test` target that
runs `pytest tests/biome` alongside the existing `yaml-test` target — do not
introduce a second, divergent Makefile.

## Downstream adoption

1. Copy `biome.json` from this repository into the consumer root.
2. Copy `docs/templates/l9-biome-scan-caller.yml` to
   `.github/workflows/l9-biome-scan.yml`.
3. Replace the zeroed SDK SHA with a full 40-character commit that contains
   this capability.
4. Adjust `files.includes` in `biome.json` for the consumer's JSON/JS/TS
   footprint.
5. Keep `permissions: contents: read`.

Do **not** pin `Quantum-L9/.github` or `Quantum-L9/l9-ci-core` for this
capability — same hosting rule as YAML governance (ADR 0010).
