# CHANGE_SUMMARY — CI enablement (l9-ci-sdk)

## What lands

- A PR quality/security gate (`pr-checks.yml`): blocking `pytest` with coverage;
  advisory `ruff`, `mypy --strict`, and Sonar; a GitGuardian secret scan that is
  blocking when its secret is visible and skipped (with a warning) otherwise.
- A payload-source + handoff workflow (`pr-repair.yml`) that emits
  `agent_review_payload.json` with the real `l9-ci` CLI and optionally notifies
  `Quantum-L9/PR_Repair`. The Implementer Bot is **not** vendored here.
- CodeRabbit config, Sonar mapping, an `AGENT.md` governance contract, and a
  CLI-contract test.

## Impact

- Every PR gets lint/type/test signal and a secret scan without any repo able to
  go red purely because a private-repo secret is not yet wired.
- No application/source behavior changes. No merges, no settings changes.
- Redundancy note: this supersedes the interim `self-test.yml` (PR #2) — once
  `pr-checks.yml` lands, `self-test.yml` can be dropped.

## Blocking-vs-advisory rationale (measured locally)

| Gate | Status today | Decision |
|---|---|---|
| pytest | 65 passing, 87% coverage | **blocking** |
| ruff | 45 findings | advisory (do not weaken to green) |
| mypy --strict | 17 findings | advisory |
| GitGuardian | depends on secret visibility | blocking when present, else skipped |
| Sonar | projectKey/org UNKNOWN | advisory |
