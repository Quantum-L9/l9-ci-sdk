---
# Biome Static Checks

Biome is this repository's own JSON/JS/TS dev toolchain (format, recommended
lint rules, import organization), enforcing the Biome formatter ownership
declared in `AGENTS.md`. It is SDK self-CI only. See
[ADR 0017](../adr/0017-sdk-cedes-org-tool-version-selection.md), which
supersedes [ADR 0011](../adr/0011-biome-static-checks.md).

## Layout

| Path | Role |
|---|---|
| `biome.json` | Repo-root config (same convention as `ruff.toml`) |
| `.github/workflows/l9-biome-scan-dogfood.yml` | SDK self-CI job (advisory, `contents: read`, checksum-verified binary) |
| `.pre-commit-config.yaml` (`biome-check`) | Local autofix hook |
| `tests/biome/` | Structure tests and the version drift guard |

`biome.json` lives at the repository root (same convention as `ruff.toml`),
**not** under `.github/`.

## Version

The Biome version appears in four places that must move together:
`biome.json` `$schema`, the `biome-check` hook's `additional_dependencies`,
`BIOME_VERSION` in the self-CI workflow, and the `npx` lines below.
`tests/biome` fails if they differ. The value tracks Core's
`install-consumer-ci/toolchain-lock.json` `biome` key because Core's
toolchain-alignment check runs on this repository too; it is a repository
toolchain pin, not an organization pin.

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
npx --yes @biomejs/biome@2.5.8 ci .
npx --yes @biomejs/biome@2.5.8 check --write .
```

If this capability is combined with the YAML-governance root `Makefile`
(`make hooks` / `make check` / `make push`), add a `biome-test` target that
runs `pytest tests/biome` alongside the existing `yaml-test` target — do not
introduce a second, divergent Makefile.

## Consumers → Core org-ci (ADR 0017)

This repository offers no reusable Biome workflow and no caller template.
Consumer repositories get the Biome check from Core's organization workflow
(`Quantum-L9/l9-ci-core` `org-ci.yml`: `install-biome` then
`run-biome-check`), with the version taken from Core's toolchain lock. A
consumer still owns its `biome.json`.

Existing callers pinned to `l9-biome-scan.yml@<sha>` keep resolving because
the SHA is immutable, but they get no updates. Remove such a caller only
after Core's `org-ci` Biome step is live for that repository.
