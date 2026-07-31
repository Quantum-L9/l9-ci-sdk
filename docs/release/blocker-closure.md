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

- Tracking issue: Path A waived (no AUD-008 issue found via API; deferred to Path B / org admin)
- Active required-check ruleset: Path A waived (no self-validation required-check ruleset found; deferred to Path B)
- Intentionally failing PR blocked from merge: Path A waived (deferred to Path B)
- Restored PR accepted after required check passed: Path A waived (deferred to Path B); tip self-validation success: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182197

## Cross-repository gate evidence

- Workflow run: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182783
- Published GitHub check: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182783/job/91188145152
- Commit-bound self-validation artifact: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182197/artifacts/8797085061

## Required assertions

- The routed `gate-result.json` matches a fresh SDK reevaluation byte-for-byte.
- Core publication conclusion is derived from canonical gate status plus governance mode.
- The SDK self-validation check runs on `main` (tip green); org **required-check ruleset** proof is Path A waived — must be attached before claiming AUD-008 admin closure for Path B.
- The runtime Semgrep fixture test executes without skip.
- No evidence URL in this document is a placeholder. Waived keys cite `docs/release/evidence-map.yaml` explicitly instead of fabricated URLs.

## Path A waivers

| Key | Approver | Date | Reason |
|---|---|---|---|
| CORE_ACTIONS_SHA | path-a-operator | 2026-07-31 | Thin caller superseded composite action pins |
| CORE_PUBLISH_SHA | path-a-operator | 2026-07-31 | Publish inside Core reusable jobs; not pinned in SDK |
| AUD_008_ISSUE_URL | path-a-operator | 2026-07-31 | No tracking issue found; never invent URL |
| AUD_008_RULESET_URL | path-a-operator | 2026-07-31 | No required self-validation ruleset found |
| AUD_008_NEGATIVE_PROOF_URL | path-a-operator | 2026-07-31 | No blocked-merge proof located |
| AUD_008_POSITIVE_PROOF_URL | path-a-operator | 2026-07-31 | Tip CI ≠ ruleset-bound positive proof |
