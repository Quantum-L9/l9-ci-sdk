# RUNBOOK — CI enablement (l9-ci-sdk)

## Activate

1. **CodeRabbit** — install the app on the org/repo:
   https://github.com/apps/coderabbitai. `.coderabbit.yaml` tunes it. No secret
   needed for the SaaS app (`CODERABBIT_TOKEN` only for API/self-hosted).
2. **GitGuardian** — ensure `GITGUARDIAN_API_KEY` is visible to this repo (org
   secret, or repo-level for a private repo). Until then the job skips with a
   warning; once present the scan is blocking on same-repo PRs.
3. **Sonar** — org-level config only. `pr-checks.yml` derives
   `sonar.projectKey` (`<owner>_<name>`) and defaults `sonar.organization` to
   `quantum-l9`, so you do NOT set these in `sonar-project.properties`. To
   activate: provision the matching project in SonarCloud/SonarQube and make
   the org-level `SONAR_TOKEN` visible to this repo. Optional org-level
   overrides: `SONAR_ORGANIZATION` (if not `quantum-l9`) and `SONAR_HOST_URL`
   (self-hosted; defaults to `https://sonarcloud.io`).

## Make an advisory gate blocking

Drive its findings to zero, then remove `continue-on-error: true` from that step
in `pr-checks.yml`:
- ruff: `ruff check --fix .` handles the auto-fixable subset first.
- mypy: resolve the 17 `--strict` findings (start with `l9_ci/cli.py`).

## Payload handoff to PR_Repair

`pr-repair.yml` is manual (`workflow_dispatch`). It emits
`agent_review_payload.json` with `l9-ci` and uploads it as the
`agent-review-payload` artifact.

- Default: `dispatch=false` — payload is produced and uploaded only.
- `dispatch=true` **and** `L9_IMPLEMENTER_BOT_TOKEN` present → sends a
  `repository_dispatch` (`event_type: l9-implementer-review`) to
  `Quantum-L9/PR_Repair`. PR_Repair must expose a matching handler; that wiring
  lives on the PR_Repair side.
- No token → the dispatch step skips with a notice; nothing fails.

The Implementer Bot, its LLM-Router lane, and verify/rollback engine are **not**
in this repo — they live in `Quantum-L9/PR_Repair`. This repo is only the payload
source. Never merge, never push fixes, never change repo settings from CI.

## Fork PRs

Secret-dependent jobs are guarded to same-repo events. Never switch them to
`pull_request_target`.
