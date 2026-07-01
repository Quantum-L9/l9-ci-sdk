# MANIFEST — CI enablement (l9-ci-sdk)

Adapted from the `l9-ci-enablement-pack` (model repo: `Quantum-L9/PR_Repair`).
Re-derived for this repo's actual stack; nothing blind-copied.

## Files

| Path | Responsibility | Consumes | Blocking? |
|---|---|---|---|
| `.github/workflows/pr-checks.yml` | PR quality + security gate | `GITGUARDIAN_API_KEY`, `SONAR_TOKEN` | pytest **blocking**; GitGuardian blocking *when secret present*; ruff/mypy/Sonar advisory |
| `.github/workflows/pr-repair.yml` | Payload source + handoff to PR_Repair (no bot vendored) | `L9_IMPLEMENTER_BOT_TOKEN` (optional) | n/a (manual dispatch) |
| `.coderabbit.yaml` | CodeRabbit review tuning | app install (`CODERABBIT_TOKEN` only for API/self-hosted) | n/a |
| `sonar-project.properties` | Sonar project mapping + coverage import | `SONAR_TOKEN` | n/a |
| `AGENT.md` | Governance contract the Implementer loads | — | — |
| `tests/test_agent_payload_contract.py` | Verifies the `l9-ci` emitter contract | — | runs under the blocking pytest gate |
| `docs/ci-enablement/*` | This pack's docs | — | — |

## Secret → tool map (org secrets already exist; visibility on private repos must be confirmed)

| Secret / var | Used by | Notes |
|---|---|---|
| `GITGUARDIAN_API_KEY` | pr-checks / gitguardian | blocking scan; skipped on fork PRs and when the secret is absent |
| `SONAR_TOKEN` | pr-checks / sonar | advisory until projectKey/org set and token visible |
| `L9_IMPLEMENTER_BOT_TOKEN` | pr-repair / handoff | optional; enables cross-repo dispatch to PR_Repair |

## Unknowns (must be filled — not invented)

| Where | Value | How to resolve |
|---|---|---|
| `sonar-project.properties` | `sonar.projectKey`, `sonar.organization` | from your SonarCloud/SonarQube project |
| repo settings | secret visibility on this **private** repo | confirm org secrets reach it, or add repo-level secrets |
| PR_Repair | `on: repository_dispatch` handler for `l9-implementer-review` | wired on the PR_Repair side (out of scope here) |
