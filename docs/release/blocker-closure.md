# Release-Blocker Closure Evidence

## Repository revisions

- SDK base PR #17: `4bc1526330188a7e209adf4c1109236ec726d869`
- SDK runtime contract commit: `0c487747b0fcd172edaefe9e843dac818de8fc12`
- SDK runtime fixture / Core-pinned code commit: `0c487747b0fcd172edaefe9e843dac818de8fc12`
- SDK thin workflow and required-CI commit: `4c7fbb785dac5b65cc74263c4b28afa6fa95959b`
- Core action commit: Path A waived — superseded by thin `analyze-semgrep.yml` caller (see `docs/release/evidence-map.yaml`)
- Core publication commit: Path A waived — publish invoked inside Core reusable jobs from thin caller (see evidence-map)
- Core reusable analysis commit: `c3f04e1268364e3623fc57f963937e2a0665e0e0`

## Administrator evidence

- Tracking issue: https://github.com/Quantum-L9/l9-ci-sdk/issues/44
- Active required-check ruleset: https://github.com/Quantum-L9/l9-ci-sdk/rules/20147356
- Intentionally failing PR blocked from merge: https://github.com/Quantum-L9/l9-ci-sdk/pull/45
- Restored PR accepted after required check passed: https://github.com/Quantum-L9/l9-ci-sdk/pull/46

## Cross-repository gate evidence

- Workflow run: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182783
- Published GitHub check: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182783/job/91188145152
- Commit-bound self-validation artifact: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182197/artifacts/8797085061

## Required assertions

- The routed `gate-result.json` matches a fresh SDK reevaluation byte-for-byte.
- Core publication conclusion is derived from canonical gate status plus governance mode.
- The SDK self-validation check **`Lint, type-check, test, coverage`** is required on `main` via Active ruleset https://github.com/Quantum-L9/l9-ci-sdk/rules/20147356.
- The runtime Semgrep fixture test executes without skip.
- No evidence URL in this document is a placeholder. Remaining waived keys cite `docs/release/evidence-map.yaml` explicitly instead of fabricated URLs.

## Path A waivers (remaining)

| Key | Approver | Date | Reason |
|---|---|---|---|
| CORE_ACTIONS_SHA | path-a-operator | 2026-07-31 | Thin caller superseded composite action pins |
| CORE_PUBLISH_SHA | path-a-operator | 2026-07-31 | Publish inside Core reusable jobs; not pinned in SDK |
