# ADR 0009: Repository Manifest Reconciliation

## Status

Accepted

## Context

Repositories need a deterministic, human-readable inventory (`MANIFEST.md`)
that stays aligned with Git tracked truth. Manual maintenance drifts.
Analysis artifact manifests (Core `build-artifact-manifest`) are a different
concern and must not be conflated with repository file inventory.

Snapshot identity (ADR 0007) already depends on normalized repository file
inventory; a first-class CLI to render and reconcile that inventory makes the
contract operable for CI auto-fix bots.

## Decision

`l9-ci-sdk` owns:

- deterministic `MANIFEST.md` generation;
- self-exclusion of the manifest path from its own inventory;
- atomic, idempotent writes;
- CLI surfaces `manifest generate` (reconcile, exit success) and
  `manifest check` (reconcile, exit gate-failure on drift).

This repository dogfoods an auto-fix GitHub Actions workflow that commits
corrections to same-repo PR heads and uploads a patch artifact for fork PRs.

`l9-ci-core` reusable-workflow packaging is deferred. Downstream consumers
adopt by copying the workflow and invoking a provisioned SDK executable.

## Consequences

- Drift is repaired on PRs rather than blocking merge by default.
- Fork PRs never receive a write-token auto-commit (security).
- Consumer adoption does not require Core code changes.
- Repository inventory remains distinct from analysis artifact manifests.
