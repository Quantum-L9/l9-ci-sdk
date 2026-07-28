<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: MIGRATION.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Migration

## Current compatibility state

The SDK runtime is `1.0.0`, the artifact protocol is
`l9.finding-bundle/v1`, and the schema version is `1.0.0`. No active artifact
major-version migration is required.

## Source-run packaging

The deployed integration provisions the SDK from source over `PYTHONPATH` and
installs `requirements.txt`. A repository-local `l9-ci` console script is not
available without packaging metadata. Issue #9 tracks the packaging/scaffolding
decision.

When packaging is introduced:

1. Preserve `python -m l9_ci` behavior and the Core-facing command contract.
2. Set the console entry point to `l9_ci.__main__:main`.
3. Ship all `l9_ci/schemas/v1/*.json` package data.
4. Keep runtime dependencies aligned with `requirements.txt`.
5. Verify `l9_ci.__version__` and integration-contract metadata match.
6. Run compatibility fixtures and all five profile smoke tests.

## Breaking artifact changes

Removing or renaming fields, changing identity inputs, or changing an artifact
major requires a new schema major, migration guide, compatibility fixtures, and
rollback plan. Readers must reject unsupported majors.

## Rollback

Revert the SDK source pin and all Core caller references together. Preserve raw
provider reports and the last valid canonical bundle so the failed migration can
be diagnosed without reinterpreting evidence.
