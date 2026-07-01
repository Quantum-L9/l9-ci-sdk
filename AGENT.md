# AGENT.md — L9 governance context (l9-ci-sdk)

This document is the governance contract loaded by the L9 Implementer pipeline
(`Quantum-L9/PR_Repair`) before it acts on a payload from this repository. It is
deliberately factual and concise — it is not auto-generated.

## Repository role

`l9-ci-sdk` is the installable Python SDK and CLI (`l9-ci`). It owns the
execution/governance runtime: compliance scanners, the pipeline runner,
rule-mode governance, the CI gate, and agent-review-payload rendering. GitHub
Actions is a runner shell only; this repo is the source of the `l9-ci` command
surface that emits `agent_review_payload.json`.

## Wire contract

TransportPacket is the only supported wire contract. `PacketEnvelope` is
superseded and must not be reintroduced. Retired legacy tooling has no
references here, and there is no public packet-envelope command; the enforcing
command is `l9-ci check-transport-packet`.

## Implementer invariants (non-negotiable)

1. **Write, never merge.** The Implementer Bot runs under `GITHUB_TOKEN` (or a
   dedicated `L9_IMPLEMENTER_BOT_TOKEN`) with `pull-requests: write` /
   `issues: write`. It never merges, never edits branch protection, never
   mutates repository settings.
2. **Proposal-only by default:** `dry_run`, `PR_FIX_LLM_APPLY=0`, no push.
   Escalation is an explicit `workflow_dispatch` input.
3. **Deterministic autofixes never call an LLM.** The LLM lane must respect
   protected paths and never-auto-repair categories, and every mutation must
   pass native verification with rollback on failure.
4. **Fork safety.** Secret-dependent jobs are restricted to same-repo events.
   Never use `pull_request_target` to expose secrets to fork PRs.

## Public contract surfaces (never auto-repair)

- `l9_ci/cli.py` command names and flags.
- The `agent_review_payload` field set (validated against
  `Quantum-L9/l9-ci-core` `schemas/agent-review-payload.schema.json`).
- `.github/governance/**` and release/tag configuration.

## Never-auto-repair categories

- Security findings requiring human judgement.
- Governance policy changes.
- Anything altering the TransportPacket contract.

## Escalation

See `docs/ci-enablement/RUNBOOK.md`. Autonomy is raised only by explicit
operator dispatch.
