---
# ADR 0011: Biome Static Checks

## Status

Accepted

## Context

`AGENTS.md` already declares Biome as the sole formatter owner for
JavaScript/TypeScript/JSON (`biome_default` workspace class). Formatter
ownership alone is a local IDE-format-on-save contract; it is not a CI gate.
Nothing currently enforces that Biome's formatting, recommended lint rules,
and import organization actually hold for the repository's JSON schema
assets (`l9_ci/schemas/v1/*.schema.json`) and any future JS/TS surface.

ADR 0010 (YAML Governance) explicitly scoped Biome and other formatter CI out
of its capability. This ADR fills that gap using the same ownership and
supply-chain conventions already established by ADR 0010.

## Decision

`l9-ci-sdk` owns:

- reusable workflow `.github/workflows/l9-biome-scan.yml` (`workflow_call`);
- dogfood caller `.github/workflows/l9-biome-scan-dogfood.yml`;
- `biome.json` at the repository root (same convention as `ruff.toml`);
- local pre-commit hook `biome-check` (`.pre-commit-config.yaml`, `language:
  node`, pinned to `@biomejs/biome@2.5.5`);
- unit tests under `tests/biome/`.

The reusable workflow follows the zero-external-GitHub-Actions convention
from ADR 0010: it downloads the pinned `biome-linux-x64` release binary and
verifies its SHA256 checksum rather than depending on `setup-node` or the
`@biomejs/biome` npm package in CI. The local pre-commit hook uses
`language: node` (isolated per-hook `node_modules`, not a global npm
install) because pre-commit's Node.js hook environment already exists for
local developer machines and Biome's npm distribution is the simplest path
to a per-hook pinned version there.

`tests/fixtures/` and `tests/compatibility/fixtures/` are excluded from both
the CI scan (`biome.json` → `files.includes`) and the pre-commit hook
(`exclude:`) because those directories intentionally contain malformed or
non-canonical JSON used to test provider parsing failure paths; reformatting
them would either break the fixtures or mask what they are testing.

Dogfood/first-activation default: `enforce-biome` is `false` — full scan,
annotate all findings, do not fail the job. Promote to `true` using the
evidence bar in `.github/governance/promotion-policy.yaml`, matching the
promotion path already used for the YAML governance gates.

Downstream consumers pin an immutable SDK commit SHA and copy `biome.json`
into their repository root, adjusting `files.includes` for their own
JSON/JS/TS footprint. Dogfood uses `uses: ./.github/workflows/…` to avoid a
self-pin chicken/egg, identical to the YAML governance pattern.

## Consequences

- Biome format/lint/import-organization checks are an independent CI gate
  (not a Semgrep provider / execution-profile entry), consistent with how
  YAML governance is scoped.
- Consumers must copy `biome.json`; a missing `biome.json` fails the job
  closed regardless of `enforce-biome`.
- Local developers get the same checks via `pre-commit run biome-check
  --all-files`, with autofix (`biome check --write`) instead of CI's
  read-only `biome ci`.
- This ADR does not change formatter ownership (already declared in
  `AGENTS.md`); it adds enforcement for the ownership that already exists.
