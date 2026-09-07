# L9 CI governance pack (SDK self-CI inputs)

> **Not a copy-in template.** Organization L9 CI is executed by the GitHub
> organization required-workflow ruleset from `Quantum-L9/l9-ci-core` `main`
> `.github/workflows/org-ci.yml`, which resolves governance centrally
> (`@core-defaults`). A governed repository copies neither a Core caller
> workflow nor this pack, and selects no Core or SDK revision; it may add only
> an optional `.l9/ci.json` (`owner`, `repo_class`, `waiver_refs`). See
> `docs/adr/0016-organization-managed-l9-ci.md` and `.l9/ownership.yaml`
> (`workflow_ownership`). The files here remain as the inputs of this
> repository's own `l9-self-ci.yml` (classifier, rule modes, thresholds) and as
> the reference shape of the Core governance schema. The copy instructions
> below are retained as historical documentation of the pre-ruleset "v2"
> instantiation model.

Drop-in governance for a repository adopting l9-ci-core **v2**. Copy the six
`*.yaml` files in this directory into your repo at **`.github/governance/`** —
that is the path `resolve-governance` and `validate-governance` read.

This pack is **language-agnostic**: it works unchanged for **Python and
Node.js/TypeScript** repos. `semgrep` is the single provider the pinned SDK
normalizes, and semgrep scans Python, JavaScript, and TypeScript alike. The
only per-language difference lives in the caller workflow's single
`env.L9_LANGUAGE` value (`"python"` or `"typescript"`; the former
`l9-analysis.yml` caller is no longer in this tree), never in this pack. The SDK's
`l9-ci semgrep run --language "$L9_LANGUAGE"` command resolves both the
matching community registry ruleset (`p/python` or `p/typescript`) and the
SDK's own packaged L9 ruleset for that language internally — there is no
`--config` list to author or keep in sync by hand.

> **Format gotcha — these are JSON.** The resolver parses each file with
> `json.loads`, so the `.yaml` files must be **valid JSON**: double-quoted
> keys, no comments, no trailing commas. Keep them as JSON objects.

## The six files

| File | You set | Hard rules enforced |
|---|---|---|
| `execution-profiles.yaml` | The profile set and each profile's `sdk_profile`, `strict`, `default_mode`, `providers`, `allowed_events` | Profile set must be **exactly** `pr_fast, merge, nightly, release, supply_chain`. `sdk_profile ∈ {ci_fast, ci_deep}`. `strict` boolean. `default_mode` ∈ the four modes. The resolved provider must appear in `providers`; the event must appear in `allowed_events`. |
| `provider-requiredness.yaml` | Per profile, is each provider required (`semgrep: true/false`) | Every profile must carry a **boolean** for each provider it declares. A required provider may not resolve to `disabled`. |
| `rule-modes.yaml` | `defaults` mode per profile; optional `provider_overrides` | `allowed_modes` must equal **exactly** `blocking, advisory, shadow, disabled`. Effective mode = provider override → profile default → profile `default_mode`. |
| `waivers.yaml` | Time-boxed waivers | Empty `[]` is valid. Each entry needs `id, owner, reason, created, expires` (ISO-8601 dates) and a `scope`. **Malformed, duplicate-id, or expired waivers are fatal.** |
| `promotion-policy.yaml` | Allowed mode `transitions` + promotion evidence `requirements` | Transition sources/targets must be valid modes; **self-transitions are prohibited**. |
| `quality-thresholds.yaml` | `sdk_policy` file to select per profile | Must be a string. Empty = no policy. If set, the path must exist; **Core validates existence only — the SDK owns threshold semantics.** |

## Resolved behavior of this pack

| Profile | Event | sdk_profile | Default mode | semgrep required |
|---|---|---|---|---|
| `pr_fast` | `pull_request` | ci_fast | advisory | yes |
| `merge` | `push` | ci_fast | advisory | yes |
| `nightly` | `schedule` | ci_deep | advisory | no |
| `release` | `push` | ci_deep | advisory | yes |
| `supply_chain` | `schedule` | ci_deep | advisory | yes |

Every profile in this pack defaults to **advisory**, not blocking — this is
the actual, current content of `execution-profiles.yaml` and
`rule-modes.yaml` in this directory; there is no blocking profile shipped
by default. This is deliberate: most community Semgrep registry findings
(e.g. `p/python`, `p/typescript`) still carry no L9 canonical rule ID, so
strict identity resolution would reject them at normalize. A packaged
identity map (`l9_ci/rulesets/semgrep/identity-map.yaml`, mirrored at
`.l9/semgrep-identity-map.yaml` in the SDK repo) now resolves a growing set
of registry `check_id`s to canonical rule IDs, and the SDK's own
L9-authored rules already carry trusted `metadata.l9.canonical_rule_id` —
but registry coverage is still partial, so advisory-first remains correct
here. Promote a profile to `blocking` per `promotion-policy.yaml` only
once you have verified the specific rules you depend on actually resolve
(via the identity map or trusted metadata) for your repo's languages.

Validated with Core's own `validate-governance` (`status: valid`).

## Rolling a provider out safely (advisory → blocking)

This repository's dogfood profiles and self-CI start in **`advisory`** (full
run, GitHub check, findings annotated, do not fail closed). The promotion
ladder still allows `shadow` for other consumers, but this repo does not use
`shadow` on first activation:

`disabled → shadow → advisory → blocking` (library ladder)

Dogfood today: stay on `advisory` until promoting a rule/profile to `blocking`.

Change the mode in `rule-modes.yaml` `defaults` (or a `provider_overrides`
entry). `promotion-policy.yaml` records the evidence bar for each hop
(observation runs/days, zero contract/artifact failures, approval).

## Example waiver

`waivers.yaml` ships empty. To suppress a *gate* temporarily (Core never
suppresses findings — this only affects requiredness/mode gating), add an
entry like this (remember: valid JSON, no comments):

```json
{
  "schema": "l9.waivers/v1",
  "waivers": [
    {
      "id": "WAIVER-2026-001",
      "owner": "platform-team",
      "reason": "semgrep p/typescript false positive under review upstream",
      "created": "2026-07-18",
      "expires": "2026-08-01",
      "scope": {
        "repositories": ["Quantum-L9/your-repo"],
        "refs": ["refs/heads/main"],
        "profiles": ["pr_fast"],
        "providers": ["semgrep"]
      }
    }
  ]
}
```

Any empty scope list means "match all". Once `expires` is in the past the
whole resolve step **fails closed** — remove or extend expired waivers.

## Selecting an SDK policy (optional)

To raise or lower gates, point `sdk_policy` at a policy file the pinned SDK
understands, e.g.:

```json
"pr_fast": { "sdk_policy": ".github/governance/policies/pr-fast.policy.json" }
```

Commit that file; Core checks it exists and passes the path to the SDK. Core
never reads or evaluates its contents.

## Python vs Node.js — what changes, what doesn't

| Concern | Python repo | Node.js/TypeScript repo |
|---|---|---|
| This governance pack | identical | identical |
| Provider | semgrep | semgrep |
| Caller workflow's `env.L9_LANGUAGE` | `"python"` | `"typescript"` |
| Generic lint/test (separate) | ruff / mypy / pytest — see [`../l9-lint-test.yml`](../l9-lint-test.yml) | eslint / `tsc --noEmit` / `vitest run` — see [`../l9-lint-test-node.yml`](../l9-lint-test-node.yml) |

The analysis pipeline (this pack + semgrep + the SDK) is identical across
languages. Only `env.L9_LANGUAGE` and your out-of-band lint/test suite differ.

### TypeScript / Node preset (strict TS repo)

For a strict-TypeScript service (e.g. eslint + `tsc --noEmit` + `vitest run`):

1. Copy the governance pack unchanged into `.github/governance/`.
2. Copy `l9-lint-test-node.yml`. It runs three independent required gates:
   `eslint .`, `tsc --noEmit` (type soundness, honors `strict: true`, emits no
   JS), and `vitest run` (one-shot — never bare `vitest`, which is watch mode).
   Package manager is auto-detected from the lockfile.
3. (Historical) Copy `l9-analysis.yml` and set `env.L9_LANGUAGE: "typescript"`.
   Under the current model there is no caller to copy: Core's `org-ci.yml`
   detects the language through the SDK and selects both the `p/typescript`
   community registry ruleset and the SDK's packaged TypeScript L9 ruleset
   via `l9-ci semgrep run --language typescript`; there is no separate
   `--config` list to edit.
4. Keep your existing `tsconfig.json`, `.eslintrc*`, and `vitest.config.ts` as
   the source of truth — the templates invoke your tools, they do not replace
   your configs.
5. Mark `ESLint`, `tsc --noEmit`, and `Vitest` as required checks in branch
   protection; roll semgrep out `shadow → advisory → blocking`.

## Wiring (current model)

There is nothing to wire. A repository targeted by the organization ruleset
gets `Analyze (central Core)` on every `pull_request` and `merge_group` from
`Quantum-L9/l9-ci-core` `main` `org-ci.yml`, with governance resolved from
Core's central defaults. Do not copy this directory, do not add an
`l9-analysis.yml` caller, and do not pin a Core or SDK SHA or the `v2` tag;
a Core change reaches every governed repository with no consumer edit.
Repository-owned lint/test workflows remain the repository's own.

The historical "v2" wiring (copy this pack plus a Core-pinned
`l9-analysis.yml` caller) is superseded; see
`docs/adr/0016-organization-managed-l9-ci.md`.
