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
- Drift behavior: drift fails the reconcile workflow, which publishes the fix
  as a patch artifact; the workflow never pushes (see "PR behavior").

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

The workflow runs read-only (`contents: read`, `persist-credentials: false`)
for every PR, same-repository or fork. On drift it prints the diff and the
regeneration command, uploads `repository-reconcile.patch` as the
`repository-reconcile-patch` artifact, and fails. The author regenerates (or
applies the patch) and pushes; that push is an ordinary `synchronize` event
and every workflow runs on the corrected head.

The workflow formerly committed the correction to same-repository PR heads
with the workflow `GITHUB_TOKEN`. GitHub starts no workflow run for a push
made with that token, so the corrected head carried no CI at all (or runs held
at `action_required`): l9-ci-sdk#117 head `df39e1e6` sat with every required
check missing. Pushing with a different credential would need a new secret,
which is out of scope, so the push was removed (2026-11-20).
`tests/architecture/test_manifest_reconcile_workflow.py` keeps it removed.

Using `pull_request_target` to execute untrusted fork code is intentionally
prohibited.

## Downstream consumer adoption

Consumers copy `.github/workflows/l9-manifest-reconcile.yml` and replace the
dogfood generate step (`PYTHONPATH=. python -m l9_ci ...`) with:

1. An immutable `provision-sdk` step from existing `l9-ci-core` (no Core
   changes required).
2. `"$EXECUTABLE" manifest generate --repository-root . --output MANIFEST.md --tracked-only`
   using the provisioned executable.
3. `contents: read` only; the template never pushes.
4. Concurrency cancellation so the corrected head supersedes stale CI work.

Pin an SDK revision that includes the `manifest` CLI. Core-owned
`workflow_call` packaging remains a future option; it is out of scope for
this SDK delivery.
