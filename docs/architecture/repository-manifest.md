# Repository Manifest Reconciliation

## Decision

`l9-ci-sdk` owns deterministic repository manifest generation. Fleet-wide Core
reusable-workflow packaging is deferred; this repository dogfoods the
capability with `.github/workflows/l9-manifest-reconcile.yml` and publishes
that file as the consumer copy-in template.

## Canonical contract

- Output: `MANIFEST.md`.
- Truth source: Git tracked-file inventory by default in CI (`--tracked-only`).
- Ordering: ascending repository-relative POSIX paths.
- Self-reference: `MANIFEST.md` is excluded from its own inventory.
- Scratchpad: `memory-bank/` (including WIP packs) is user/agent scratch only —
  gitignored in this repo and excluded via `--exclude-dir memory-bank` in CI.
- Write behavior: atomic and idempotent.
- Drift behavior: drift is repaired, not treated as a merge failure.

## CLI

```bash
PYTHONPATH=. python -m l9_ci manifest generate --repository-root . --output MANIFEST.md --tracked-only --exclude-dir memory-bank
PYTHONPATH=. python -m l9_ci manifest check --repository-root . --output MANIFEST.md --tracked-only --exclude-dir memory-bank
```

`generate` always exits successfully after a valid reconciliation. `check`
writes the corrected manifest and exits with the standard gate-failure code
when drift was found, making it useful for consumers that want detection
without automatic commit behavior.

## PR behavior

For same-repository PR branches, the workflow commits the corrected manifest
directly to the PR head. That push emits a new `synchronize` event, and CI
runs again against the corrected revision.

Fork PR tokens are read-only. The workflow therefore generates and uploads
`manifest-reconcile.patch` without failing the PR. Using `pull_request_target`
to execute untrusted fork code is intentionally prohibited.

## Downstream consumer adoption

Consumers copy `.github/workflows/l9-manifest-reconcile.yml` and replace the
dogfood generate step (`PYTHONPATH=. python -m l9_ci ...`) with:

1. An immutable `provision-sdk` step from existing `l9-ci-core` (no Core
   changes required).
2. `"$EXECUTABLE" manifest generate --repository-root . --output MANIFEST.md --tracked-only`
   using the provisioned executable.
3. `contents: write` for same-repository PR repair.
4. A same-repo branch guard before push (already in the template).
5. Concurrency cancellation so the corrected head supersedes stale CI work.

Pin an SDK revision that includes the `manifest` CLI. Core-owned
`workflow_call` packaging remains a future option; it is out of scope for
this SDK delivery.
