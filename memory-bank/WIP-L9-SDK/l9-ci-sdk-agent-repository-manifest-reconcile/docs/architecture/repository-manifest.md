# Repository Manifest Reconciliation

## Decision

`l9-ci-sdk` owns deterministic repository manifest generation. CI orchestration remains outside the SDK, but this repository dogfoods the capability with `.github/workflows/l9-manifest-reconcile.yml`.

## Canonical contract

- Output: `MANIFEST.md`.
- Truth source: Git tracked-file inventory by default in CI.
- Ordering: ascending repository-relative POSIX paths.
- Self-reference: `MANIFEST.md` is excluded from its own inventory.
- Write behavior: atomic and idempotent.
- Drift behavior: drift is repaired, not treated as a merge failure.

## CLI

```bash
PYTHONPATH=. python -m l9_ci manifest generate --repository-root . --output MANIFEST.md --tracked-only
PYTHONPATH=. python -m l9_ci manifest check --repository-root . --output MANIFEST.md --tracked-only
```

`generate` always exits successfully after a valid reconciliation. `check` writes the corrected manifest and exits with the standard gate-failure code when drift was found, making it useful for consumers that want detection without automatic commit behavior.

## PR behavior

For same-repository PR branches, the workflow commits the corrected manifest directly to the PR head. That push emits a new `synchronize` event, and CI runs again against the corrected revision.

Fork PR tokens are read-only. The workflow therefore generates and uploads `manifest-reconcile.patch` without failing the PR. Using `pull_request_target` to execute untrusted fork code is intentionally prohibited.

## Fleet adoption

Consumer repositories need:

1. An immutable `l9-ci-sdk` provision step.
2. The `manifest generate` invocation.
3. `contents: write` for same-repository PR repair.
4. A same-repo branch guard before push.
5. Concurrency cancellation so the corrected head supersedes stale CI work.

The reusable fleet-wide orchestration belongs in `l9-ci-core`; this SDK feature supplies the deterministic engine.
