# Action Plan: Porting L9_Original_Repo Strength Concepts into Quantum-L9/l9-ci-core (Revision 1.1 — DORA Omitted, Meta-Injection Engine Added)

---
title: l9-ci-core Strength-Porting Action Plan (Rev 1.1)
created: 2026-07-27T00:00Z
version: 1.1.0
type: workflow
domain: ci-platform
tags: l9-ci-core, l9-meta-injector, governed-providers, adr-enforcement, auto-remediation, meta-injection, porting-plan
related: StructuredReasoningOrchestratedMeta-Injectionvial9-ci-core.md, l9-ci-core_Strength_Porting_Action_Plan.md (v1.0.0, superseded), L9_Original_Repo_CI_Map_and_Alignment_Report.md, l9-ci-core_Consumer_CI_Map_SWOT_and_Comparison.md
source: canonical
status: draft
owner: Igor Beylin
author: Manus AI
---
purpose: Phased engineering plan to port L9_Original_Repo's proven CI strengths into l9-ci-core as governed platform capabilities — with all DORA porting removed and replaced by the l9-meta-injector orchestrated meta-injection engine (per the approved structured-reasoning design, Alternative B) — with zero changes to L9_Original_Repo.

---

## A. Objective

Elevate `l9-ci-core` from a semgrep-only governed control plane into a **multi-engine control plane** carrying L9's institutional CI knowledge, by executing five strength ports. Four are donor-derived from `L9_Original_Repo` (read-only concept donor — no patches, edits, or commits to it): the 35-script gate library, ADR structural enforcement, the auto-remediation culture, and strict blocking thresholds with the fast local commit loop. The fifth — **replacing all previously planned DORA porting** — is the integration of `Quantum-L9/l9-meta-injector` as a second provisioned engine, delivering verify-only, fail-closed metadata compliance to every consumer under the chosen "injection as proposal" doctrine (Alternative B, ToTh score 0.85) from the approved structured-reasoning design [1].

Success criteria inherited from that design: no CI job ever mutates consumer trees; meta compliance remains fail-closed; injection capability is owned by `l9-meta-injector` and orchestrated by `l9-ci-core`, mirroring the existing Core⇄SDK doctrine; the consumer caller is a copyable three-file template; and all fleet CI stays green.

## B. Key Factors

1. **Architecture boundary is non-negotiable.** ci-core's own tests freeze the workflow inventory (`test_phase_scope.py`), forbid write permissions, and require immutable full-40-char SHA pins ("no floating refs, no branches, no tags, no short SHAs"). Core owns orchestration, provisioning, and publication; it never owns analysis or injection semantics. Every port respects this split: **rules/checkers → SDK; injection semantics → l9-meta-injector; orchestration, governance data, and distribution → Core.**
2. **The donor inventory is concrete.** L9_Original_Repo (`@b785c415`, read-only) contains 35 Python gate scripts under `ci/`, a curated semgrep ruleset (`.semgrep/l9-rules.yaml`, ADR-0083–0088), a 709-line 9-phase pre-commit hook, the `auto_fix_adr.py` remediator, and blocking thresholds (75 % coverage, 85 % mutation). All DORA-specific assets (`check_dora_compliance.py`, `dora-check` job, hook Phase 7B DORA injection) are **explicitly out of scope in this revision.**
3. **The meta-injection engine is verified ready.** `l9-meta-injector` v3.0.0 at pin `98e23af085abb1e047fcd003f283e93ba0c5343e` is a TypeScript library with committed `dist/`, node ≥18, no `bin` CLI, and unpublished to npm (publication gate fails closed by design — git-pinned provisioning needs no registry). Its stable surface is `runPipelineAsync(PipelineConfig)` with `dryRun: boolean`, returning `PipelineResult.verification.passed` — the documented CI gate boolean — plus coverage, placement plans, and nine-plane MetaV3 records. The operator-customizable `MetaSchema` layer (`parseCanonicalYaml` → `toMetaSchema` → `applySchema`, targets `file_header|sidecar|manifest`) makes any repo's metadata dialect reviewable config data instead of code. All verified against the live clone.
4. **ci-core already has the sockets and precedent.** `actions/provision-sdk` (clone-at-pin → isolated install → liveness probe) is the provisioning pattern to mirror for a Node engine; `.l9/sdk-compatibility.yaml` is the pin-file idiom to replicate; `docs/templates/` → org mirror → consumer caller is the distribution path; `rule-modes.yaml` supplies shadow → advisory → blocking rollout semantics; and the promotion state machine (≥20 runs, ≥7 days, approval) governs every newly ported gate.

## C. Analysis — Strength-to-Target Mapping (Revised)

| # | Strength / capability | Source | Port target in l9-ci-core ecosystem | Mechanism |
|---|---|---|---|---|
| S1 | Curated semgrep ruleset (ADR-0083–0088) | L9_Original_Repo (read-only) | SDK policy pack + `semgrep-policy.yaml` preset update | Existing semgrep pipeline, zero new architecture |
| S2 | 35 `ci/check_*.py` gate scripts (ADR, crypto, imports, naming — **DORA checker excluded**) | L9_Original_Repo (read-only) | New **`l9-gates` governed provider** in the SDK; Core gains `profile-normalize-l9gates.yml` | Same normalize → validate → project → publish pipeline as semgrep |
| S3 | Auto-remediation (`ruff --fix`, `auto_fix_adr.py` — **DORA injection excluded**) | L9_Original_Repo (read-only) | SDK `fix` operations + advisory **`l9-autofix` kernel** uploading patch artifacts (never pushes) | Preserves Core's least-privilege, no-write invariant |
| S4 | Strict thresholds (75 % coverage, mutation 85 %) + 9-phase local loop | L9_Original_Repo (read-only) | Hardened preset defaults, `strict` execution profile, baseline-ratchet ledgers, `presets/*/local/` pre-commit pack | Governance-as-data; one policy source for local + CI |
| S5 | **Orchestrated meta-injection (replaces DORA)** — fail-closed metadata compliance with CI-never-writes guarantee | `l9-meta-injector` @ `98e23af0…` per approved design [1] | **Second provisioned engine**: pin file, provision/invoke action pair, reusable `meta-injection.yml`, consumer caller template `l9-meta.yml` | Three-artifact engine recipe mirroring the SDK doctrine; verify-only dry-run gate + injection-preview diff artifact |

The unifying design decision: neither the 35 checkers (S2) nor the injector (S5) may live in Core as workflow bash. S2 semantics land in the SDK; S5 semantics stay in `l9-meta-injector`; Core only provisions at immutable pins, invokes through closed-verb adapters, and publishes verdicts through governance modes. This makes S5 the **precedent-setting second engine** — proving the three-artifact recipe (pin file + provision/invoke actions + caller template) that any future engine (SBOM, docs-gen, license-stamper) will follow.

## D. Phased Action Plan (Revised)

### Phase 0 — Foundations and Extraction Audit (Week 1)

1. Snapshot the donor at pinned SHA `b785c415` into a read-only reference directory; record provenance in a ci-core ADR: *"ADR: Adopt L9_Original_Repo gate library as SDK provider `l9-gates` v1."*
2. Classify the 35 checkers into portable-generic, portable-parameterized, and excluded buckets. **`check_dora_compliance.py` moves to the excluded bucket by explicit directive**, alongside donor-specific checkers (`check_substrate_api`, `validate_spec_v25`); log the exclusion rationale in the ADR.
3. Draft a **second ADR** for the meta-injection engine: *"ADR: Adopt l9-meta-injector as second provisioned engine under the multi-engine control-plane doctrine"* — capturing Alternative B's rationale, the rejected alternatives (central write-mode 0.20, consumer-side-only 0.40, npm-publish-first 0.30), and the CI-never-writes constitutional guarantee [1].
4. Extract and reconcile `.semgrep/l9-rules.yaml` against the SDK's current semgrep policy.
5. Exit gate: both ADRs signed off; classification matrix committed to ci-core `docs/`.

### Phase 1 — Semgrep Quick Wins (Weeks 1–2)

1. Ship the merged L9 ruleset (S1) as an SDK policy revision; update `presets/python` governance files (`semgrep-policy.yaml`, `semgrep-identity-map.yaml`).
2. New rules enter in `shadow` mode via `rule-modes.yaml`; the promotion policy governs their path to `blocking`.
3. First threshold tranche (S4): raise documented default `COVERAGE_THRESHOLD` guidance from `"0"` to donor-proven `75` (explicit opt-down preserved); pin toolchain versions in `requirements-ci.txt` guidance.
4. Exit gate: preset consumers pass CI unchanged; new rules reporting in shadow artifacts.

### Phase 2 — Meta-Injection Engine Integration (Weeks 2–5) — *replaces the former DORA/ADR Phase 3's DORA half and is promoted to an early phase per the approved implementation plan* [1]

**l9-ci-core additions (feature branch `feat/meta-injection-engine`, one PR):**

1. `.l9/meta-injector-compatibility.yaml` — schema `l9.engine-compatibility/v1`, producer `Quantum-L9/l9-meta-injector`, pinned `revision: 98e23af085abb1e047fcd003f283e93ba0c5343e`, policy: no floating refs/branches/tags/short SHAs (exact `sdk-compatibility.yaml` idiom).
2. `.github/actions/provision-meta-injector/` — composite action: clone at pin → `npm ci --ignore-scripts` (no lifecycle scripts, supply-chain hardening) → committed-`dist/` build check → liveness probe (`node -e "require('<dir>')"`) → output engine directory.
3. `.github/actions/invoke-meta-injector/` — safe adapter with **exactly one operation** (mirroring invoke-sdk's closed verb set): a fixed Node driver that loads the consumer's `.github/l9-meta/schema.yaml` through the injector's `meta_schema` layer, runs `runPipelineAsync` with `dryRun: true`, writes `meta-verification.json` + `injection-preview.diff`, and exits per mode — blocking → nonzero on `verification.passed == false`; advisory → annotate only; shadow → artifact only. No shell eval of inputs.
4. `.github/workflows/meta-injection.yml` — reusable (`workflow_call`) workflow: inputs `schema-path` (default `.github/l9-meta/schema.yaml`), `include-glob`, `mode` (shadow|advisory|blocking, default advisory), `engine-ref-override` (rejected unless full 40-char SHA, fail-closed). Jobs: provision → invoke → upload artifacts → publish summary. `permissions: contents: read` only.
5. `docs/templates/l9-meta.yml` — the consumer caller template ("optimal instantiation"): env-pinned `L9_CORE_REF`, triggers `pull_request` + `push: branches [main]` + `workflow_dispatch`, one job calling `meta-injection.yml@${L9_CORE_REF}`.
6. `test_phase_scope.py` expected set += `meta-injection.yml` in the same PR (the sanctioned mechanism for a governed scope change); AGENTS.md §3–4 updated with the engine recipe and consumer integration step.

**Reference-consumer instantiation (l9-graphiti-memory, second PR, merges after ci-core PR records merge SHA S):** delete the write-mode `apply_l9_meta.py` call from `validate_release.sh:36` (keep the read-only `check_l9_meta.py` gate); add deliberate local write path `scripts/meta_apply.sh`; add operator dialect `.github/l9-meta/schema.yaml` (fields `l9_schema=1` const, `repo` const, `path` from `source_path`, `layer`, `owner` default `memory-control-plane`, `status` default `active`, `version`, `updated`; targets `[file_header, manifest]`); add caller `.github/workflows/l9-meta.yml` pinned `L9_CORE_REF=S`, mode `advisory` initially. This wiring is the copyable model for all consumers: **three files — caller, schema, mode.**

7. Exit gate: ci-core self-CI green (including updated phase-scope test); graphiti-memory CI green with the `l9-meta` advisory check visible and no CI job mutating tracked files; injection-preview diff artifact verified against a known non-compliant fixture. Rollback: single-commit reverts on both PRs.

### Phase 3 — The `l9-gates` Governed Provider (Weeks 3–7, overlaps Phase 2)

1. **SDK side:** implement bucket-(a)/(b) checkers as one `l9-ci l9-gates-run` operation emitting a canonical finding bundle (stable rule IDs, `l9gates-identity-map.yaml`), versioned and SHA-pinned.
2. **Core side:** add `profile-normalize-l9gates.yml` mirroring `profile-normalize-semgrep.yml` (governance resolution → provider run → normalize → validate-bundle → project → route-artifacts → manifest → publish); extend the invoke-sdk allowlist by one entry; update the phase-scope frozen set in the same PR.
3. **Governance side:** add `l9gates` to `provider-requiredness.yaml`, `rule-modes.yaml` (`provider_overrides.l9gates`), `execution-profiles.yaml`; ship schema-validated `l9gates-parameters.yaml` for consumer-supplied lists (deprecated services, naming conventions, protected paths).
4. **ADR structural rules (formerly bundled with DORA, now standalone):** port `check_adr_compliance.py` semantics as parameterized rules with the ADR manifest location supplied via `l9gates-parameters.yaml`; consumers without ADR practices leave them `disabled`. Add a baseline-ratchet ledger template for ADR debt so legacy repos enroll with today's violations quarantined and ratchet downward.
5. **Preset side:** regenerate `presets/python` with the second provider job in `l9-analysis.yml`; new check `Governed L9 Gates Analysis` enters the org ruleset in `evaluate` mode.
6. Exit gate: dogfood on ci-core plus 2–3 volunteer repos in shadow; zero contract failures across the promotion window.

### Phase 4 — Auto-Remediation as Advisory Artifacts (Weeks 6–9)

1. SDK `fix` operations mirroring the donor's ADR auto-fixer (`auto_fix_adr.py` semantics; **DORA block injection dropped**), emitting unified-diff patch artifacts, never mutating trees in CI — the same proposal doctrine Phase 2 establishes for metadata.
2. Advisory kernel `l9-autofix.yml` (v1 channel) runs the fixers and uploads patch + job-summary "apply locally with `git apply`" guidance. The formerly rejected bot-commit model remains out of scope; an *explicitly dispatched* fix-PR workflow is retained as a possible later addition, consistent with the design's second-order notes [1].
3. Exit gate: patch artifacts byte-identical to donor remediator output on a violation corpus.

### Phase 5 — Local Commit Loop (Weeks 8–11)

1. Ship `presets/python/local/`: a `.pre-commit-config.yaml` template whose hooks call the same pinned SDK (`l9-ci l9-gates-run --local`, ruff, secret scan), plus an optional local `meta verify` hook driving the injector dry-run against the repo's `schema.yaml` — so local and CI verdicts on both code gates and metadata derive from single policy sources.
2. Port the donor hook's UX strengths (staged-file scoping, parallel format/lint/type phases, JSON audit trail, exact-fix-command failure messages); drop auto-`git add` in favor of printed patches.
3. Extend the `l9-ci-activation` skill to install the local pack and the three-file meta-injection instantiation.
4. Exit gate: activation skill onboards a fresh repo (analysis + meta) end-to-end in under 2 minutes.

### Phase 6 — Threshold Hardening and Fleet Rollout (Weeks 11–15)

1. Introduce the `strict` execution-profile variant (blocking coverage ≥75 %, mutation via ratchet ledgers, l9gates blocking) selectable per repo.
2. Promote meta-injection from `advisory` to `blocking` for burn-in-complete consumers, per the rule-modes rollout doctrine; add `Governed L9 Gates Analysis` and the meta check to required checks, moving the org ruleset from `evaluate` to `active` for promoted repos.
3. Publish immutable release `v2.1.0` (updated compatibility allowlists for **both** engine pins, MANIFEST resealing, migration notes); advance `@v1` only if kernel contracts are untouched.
4. Exit gate: ≥5 fleet repos on blocking `l9gates`; ≥3 consumers on blocking meta-injection; release validation green.

## E. Workstream Summary and Effort (Revised)

| Phase | Window | Primary repo(s) | Key deliverables | Risk |
|---|---|---|---|---|
| 0 Foundations | Wk 1 | ci-core (docs) | Two ADRs, checker classification (DORA excluded) | Low |
| 1 Semgrep quick wins | Wk 1–2 | SDK + preset | L9 ruleset in shadow; hardened defaults | Low |
| 2 Meta-injection engine | Wk 2–5 | ci-core + graphiti-memory (reference consumer) | Pin file, 2 actions, `meta-injection.yml`, `l9-meta.yml` template, reference instantiation | Medium |
| 3 `l9-gates` provider + ADR rules | Wk 3–7 | SDK + ci-core | Provider, reusable workflow, governance schema, ADR ratchet ledger, preset v2 | High |
| 4 Auto-remediation | Wk 6–9 | SDK + ci-core | Fix operations, advisory `l9-autofix` kernel | Medium |
| 5 Local loop | Wk 8–11 | ci-core presets + skill | Local pre-commit pack incl. meta verify, activation skill update | Medium |
| 6 Hardening & rollout | Wk 11–15 | ci-core + org | `strict` profile, blocking promotions, `v2.1.0` release | Medium |

## F. Risks and Mitigations

The dominant structural risk remains **scope violation of Core's thin-control-plane doctrine**; mitigation is architectural — all gate logic lives in the SDK, all injection semantics live in `l9-meta-injector`, and the frozen-scope, permission, and pinning tests are updated deliberately in the same reviewed PRs. Second, the **original sin must not be reintroduced centrally**: the meta-injection workflow is dry-run-only with `contents: read`; a non-compliant PR fails with a diff artifact instead of being auto-fixed — deliberate friction accepted as the cost of the CI-never-writes guarantee [1]. Third, **injector dry-run fidelity against consumer dialects** is the residual risk the design itself flags (confidence 0.85); mitigated by advisory-mode burn-in while each consumer's existing read-only validator (e.g., `check_l9_meta.py`) stays blocking locally, with the operator `MetaSchema` as the declared convergence target. Fourth, **dual-engine pin coupling**: both `.l9/sdk-compatibility.yaml` and `.l9/meta-injector-compatibility.yaml` require pin-bump PRs to advance — exactly the immutability discipline already imposed, with fail-closed rejection of non-40-char overrides. Fifth, **fleet disruption** is neutralized by mandating every ported rule and the meta check be born in `shadow`/`advisory` and travel the promotion state machine — nothing is born blocking. Where donor checker semantics are ambiguous, the status is **Unknown** and the checker stays excluded from v1 rather than guessed.

## G. Recommendation

Execute Phases 0–1 immediately (low-risk, fleet-wide value within two weeks). Prioritize **Phase 2 (meta-injection engine) ahead of the gates provider** — it is smaller, fully specified by the approved structured-reasoning design, removes an active hazard (the tree-mutating write step in the reference consumer), and establishes the multi-engine three-artifact recipe that Phase 3 then follows with higher confidence. Commit to Phase 3 as the flagship quarter effort. Do not embed checker or injector logic in workflows, do not force npm publication of the injector, and do not touch L9_Original_Repo at any point — it remains the untouched living reference until it eventually adopts the platform as an ordinary consumer.

## H. Next Steps (Immediate, This Week)

1. Approve both ADR drafts: `l9-gates` provider adoption and `l9-meta-injector` second-engine adoption (Phase 0.1–0.3).
2. Circulate the 35-checker classification matrix with `check_dora_compliance.py` marked excluded-by-directive (Phase 0.2).
3. Open the ci-core PR `feat/meta-injection-engine` with the six-file addition set and phase-scope test update (Phase 2.1–2.6).
4. Open the SDK policy PR merging the L9 semgrep ruleset in shadow mode (Phase 1.1–1.2).
5. After ci-core PR merge, open the graphiti-memory reference-consumer PR pinned to merge SHA S (Phase 2, consumer half).
6. Schedule the T+7-day promotion-window review for shadow → advisory transitions.

## I. Source Basis and References

All facts verified against local clones: `Quantum-L9/l9-ci-core` v2.0.0 (workflows, actions, presets, governance files, phase-scope test, docs); `Quantum-L9/l9-meta-injector` v3.0.0 at HEAD `98e23af085abb1e047fcd003f283e93ba0c5343e` (package.json — no `bin`, node ≥18, committed `dist/`; `dist/index.d.ts` exporting `runPipelineAsync`; `dist/schema.d.ts` `PipelineConfig.dryRun`; `dist/pipeline.d.ts` `VerificationSummary.passed` documented as the CI gate; `dist/meta_schema.d.ts` operator MetaSchema layer; fail-closed `check:publication` gate); and read-only reference `cryptoxdog/L9_Original_Repo@b785c415` (35 `ci/*.py` gate scripts, `.semgrep/l9-rules.yaml`, 9-phase pre-commit hook, 17-job `ci.yml` DAG), as mapped in the two prior audit reports delivered in this session.

[1]: /home/ubuntu/upload/StructuredReasoningOrchestratedMeta-Injectionvial9-ci-core.md "Structured Reasoning: Orchestrated Meta-Injection via l9-ci-core (user-approved design, Alternative B, confidence 0.85)"
