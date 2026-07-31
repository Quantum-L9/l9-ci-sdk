# AGENTS.md — l9-ci-sdk

Operating rules for coding agents in `Quantum-L9/l9-ci-sdk`.

This file is an agent-facing index of laws already owned by `.l9/*`,
`docs/adr/*`, and `docs/architecture/*`. When those diverge, the
machine-readable contracts and ADRs win; update this file to match.

---

## 1. Constellation role

L9 CI is a multi-repo constellation. Each product owns one authority surface:

| Product | Repo | Role |
|---|---|---|
| **CI Core** | [`l9-ci-core`](https://github.com/Quantum-L9/l9-ci-core) | Orchestrates — workflows, permissions, provider enablement, artifact upload/retention, gate publication, org rollout |
| **CI SDK** | [`l9-ci-sdk`](https://github.com/Quantum-L9/l9-ci-sdk) (**this repo**) | Observes — provider adapters, canonical evidence/findings, identity, policy classification library, gate evaluation library, deterministic bundles, agent projections |
| **Debt Resolver** | [`l9-ci-debt-resolver`](https://github.com/Quantum-L9/l9-ci-debt-resolver) | Diagnoses — interprets validated evidence into debt diagnoses |
| **PR Repair** | [`PR_Repair`](https://github.com/Quantum-L9/PR_Repair) | Mutates — repair planning and repository/PR mutation |
| **Debt Intelligence** | [`l9-ci-debt-intelligence`](https://github.com/Quantum-L9/l9-ci-debt-intelligence) | Learns — corpus, recurrence, fleet intelligence |
| **Debt LSP** | [`l9-ci-debt-lsp`](https://github.com/Quantum-L9/l9-ci-debt-lsp) | Prevents — editor/LSP diagnostics |
| **Assurance** | [`l9-assurance`](https://github.com/Quantum-L9/l9-assurance) | Decides — assurance / release decision authority |
| **Harness** | [`l9-harness`](https://github.com/Quantum-L9/l9-harness) | Executes harnessed evaluation loops outside Core orchestration |

One-line doctrine:

> **CI Core orchestrates. CI SDK observes. Debt Resolver diagnoses. PR Repair mutates. Debt Intelligence learns. Debt LSP prevents. Assurance decides.**

### What this repo is
The canonical **analysis contract layer**. Provider adapters produce facts.
They do not decide whether findings block a change. Core (and downstream
products) consume the public CLI and validated artifacts only.

### What this repo is not
Do not implement here:

- GitHub Actions orchestration, permissions, upload/retention (Core)
- Org-wide provider promotion / rollout policy (Core)
- Historical corpus, recurrence analytics (Debt Intelligence)
- LSP / editor diagnostics (Debt LSP)
- Repair planning, repository mutation, PR retry loops (PR Repair)
- Hosted services / LLM orchestration
- Parsing provider-native reports inside Core (forbidden both ways)

Forbidden dependency edges (see `.l9/architecture.yaml`):
`SDK_to_Core`, `SDK_to_LSP`, `SDK_to_Repair`, `SDK_to_Corpus`, plus the
layer edges listed in §4.

---

## 2. Mission & ownership

### Owns
- Provider SPI, registry, execution/import contracts, adapters
- Canonical evidence, findings, coverage, provider failures, limitations
- Explicit rule-identity resolution and versioned identity maps
- Policy classification **library** (not org promotion policy)
- Gate evaluation **library** (`pass` / `fail` / `incomplete` / `invalid`)
- Deterministic artifact serialization; schema + semantic validation
- Agent-review payload **projection** (regenerable; not a second store)
- Public Python API + public CLI (`l9-ci`)
- YAML/workflow static-check capability (reusable workflow + root `lint/`)
- Repository snapshot identity and capability detection
- Operational limits, compatibility negotiation, redaction validation

Authoritative ownership table: `.l9/ownership.yaml`.
Authoritative stack scope: `.l9/tool-stack.yaml` (`owns` / `excludes`).
Authoritative Core↔SDK boundary: `.l9/integration-contract.yaml`.

### Does not own
Everything listed under constellation “is not” above, plus: Core must not
parse provider-native reports, reconstruct findings, mutate bundles, or
synthesize rule identity. SDK must not upload workflow artifacts, read
GitHub workflow context directly, or decide org-wide provider promotion.

---

## 3. Current phase (do not use stale Phase-1 bans)

Source of truth: `.l9/roadmap.yaml`.

| Phase | Status | Meaning for agents |
|---|---|---|
| P0 Architecture & contracts | **complete** | Models, schemas, SPI, serializer, validator, arch tests |
| P1 Semgrep vertical slice | **complete** | Semgrep JSON import + normalize; runtime-captured fixture + provenance under `tests/fixtures/semgrep/runtime/` |
| P2 Integration & release readiness | **complete** | CLI, version negotiation, validation, agent projection, limits |
| P3 Spec closure | **complete** | Gates, snapshots, capabilities, profiles, CLI SSOT, Semgrep version policy, limits, layer enforcement |
| P4 Semgrep shadow rollout | **ready_for_promotion** | Fixture + thin Core path exist; shadow observation / supported promotion not claimed (Path B) |
| P5 Second provider | **deferred** | Gitleaks / SARIF only after Semgrep is `supported` and bundle has no known breaking defects |

**Stale guidance to ignore:** older docs that say “Phase 1: do not add
Semgrep-specific code / scanner providers.” Semgrep is present and
`experimental` (see `.l9/release-policy.yaml`). Do **not** start a second
provider in P3/P4.

Semgrep lifecycle today: `experimental` (Path A). P4 is `ready_for_promotion`
but shadow observation is not started — do not claim GA or `supported` early.

---

## 4. Architectural laws

### STACK rules (`.l9/tool-stack.yaml`)
1. **STACK-001** — Provider parsing is policy-independent.
2. **STACK-002** — Canonical findings never embed a CI verdict.
3. **STACK-003** — Policy classification never mutates provider facts.
4. **STACK-004** — Gate evaluation consumes classifications, coverage, and provider failures.
5. **STACK-005** — Human-readable console output is not a durable provider contract.
6. **STACK-006** — Missing required evidence is not equivalent to PASS.
7. **STACK-007** — Native provider rule identifiers are always preserved.
8. **STACK-008** — Canonical rule identifiers require explicit resolution.
9. **STACK-009** — Unsupported behavior is labeled rather than inferred.
10. **STACK-010** — Providers are integrated and promoted independently.

### Layer dependency law (`.l9/architecture.yaml`)
Canonical flow:

```text
repository → capabilities → execution → providers → identity
  → policy → gates → artifacts → projections
```

Public packages: `contracts`, `repository`, `capabilities`, `providers`,
`identity`, `policy`, `execution`, `artifacts`, `gates`, `integration`, `cli`.

Composition layers (not listed as public_surface packages): `pipeline`,
`commands`. Experimental / under-documented: `l9_ci/baseline` (baseline-ratchet
debt-governance helpers — keep out of Core contracts until owned in `.l9`).

**Hard edges (do not introduce):**
- `contracts` ↛ `providers` / `artifacts`
- `providers` ↛ `artifacts` / `policy` / `gates` / workflow code
- `artifacts` ↛ `providers` / `policy` / `gates`
- `policy` ↛ `providers`
- `gates` ↛ `providers`
- `integration` ↛ `pipeline`
- SDK ↛ Core / LSP / Repair / Corpus internals

Architecture boundary tests live under `tests/architecture/`. Extend them
when adding layers or edges.

### ADR index (read before changing semantics)

| ADR | Decision |
|---|---|
| [0001](docs/adr/0001-canonical-evidence-and-findings.md) | Separate `EvidenceRecord` from `Finding`; findings reference evidence by ID |
| [0002](docs/adr/0002-policy-independent-normalization.md) | Normalization produces facts only; classification is later |
| [0003](docs/adr/0003-explicit-rule-identity.md) | Keep `provider_rule_id`; canonical ID only via trusted metadata or versioned map; unresolved stays explicit |
| [0004](docs/adr/0004-versioned-artifact-protocol.md) | Emit versioned `l9.finding-bundle/v1` |
| [0005](docs/adr/0005-provider-spi.md) | Explicit Provider SPI + registry |
| [0006](docs/adr/0006-gate-evaluation.md) | Gate statuses pass/fail/incomplete/invalid; missing required evidence ≠ pass |
| [0007](docs/adr/0007-repository-snapshot-identity.md) | SDK derives snapshot identity |
| [0008](docs/adr/0008-agent-payload-is-a-projection.md) | Agent payload is a regenerable projection |
| [0009](docs/adr/0009-repository-manifest-reconciliation.md) | Root `MANIFEST.md` reconciled from Git tracked truth |
| [0010](docs/adr/0010-yaml-governance-static-checks.md) | SDK owns YAML/workflow static checks + `lint/` |
| [0011](docs/adr/0011-biome-static-checks.md) | SDK owns Biome static checks + root `biome.json` |

Architecture prose: [`docs/architecture/`](docs/architecture/README.md).

---

## 5. Canonical contracts & artifacts

### Protocol
- Bundle protocol: `l9.finding-bundle/v1`
- Agent projection: `l9.agent-review-projection/v1`
- Identity map schema: `l9.identity-map/v1`
- JSON Schema Draft 2020-12 under `l9_ci/schemas/v1/`

### Artifact layout (`.l9/integration-contract.yaml`)
```text
artifacts/raw/<provider>/<report>          # provider-native (input)
artifacts/l9/finding-bundle.json           # canonical bundle
artifacts/l9/agent-review-payload.json     # projection
```
Publication/upload is **Core-owned**. SDK writes local filesystem only.

### Bundle contents (conceptual)
schema / schema_version / SDK_version / generated_at / snapshot /
providers / evidence / findings / classifications / provider_failures /
coverage / limitations / summary

### Validation (both required)
1. Compatibility / version negotiation
2. JSON Schema validation
3. Semantic validation (IDs, evidence refs, one coverage record per provider,
   summary coherence)
4. Defensive redaction scan (no secret material, no absolute source paths)

### Determinism
Sorted keys, no insignificant whitespace, one trailing newline, stable sort
orders, atomic writes. Fix `generated_at` in tests. See
`docs/architecture/deterministic-serialization.md`.

### Identity resolution
Statuses: `trusted_metadata` | `explicit_mapping` | `unresolved`.
Never derive canonical identity from severity. Never invent policy keys.
Map file: `.l9/semgrep-identity-map.yaml` (may be empty `rules: {}`).

### Gates
Evaluate classifications + required provider failures + coverage →
`pass` | `fail` | `incomplete` | `invalid`.
Order of force (code): INVALID → INCOMPLETE (fatal/incomplete coverage) →
FAIL (blocking) → INCOMPLETE (strict unresolved) → PASS.
Required provider failure must never become PASS (STACK-006).

### Agent payload
Buckets: blocking / advisory / shadow / unresolved / disabled + autofix
candidates only when `remediation_class` ∈ `{safe-autofix, mechanical}`.
Semgrep must not invent autofix safety. Payload is regenerable from the
bundle (ADR 0008).

---

## 6. Provider SPI & Semgrep

### SPI obligations (`l9_ci/providers/spi.py`)
Every provider implements: metadata, detect, detect_version,
validate_configuration, build_execution_plan, execute,
validate_report_shape, import_report, normalize →
`ProviderNormalizationResult` (evidence, findings, coverage, failures,
limitations).

Providers **must not** produce blocking/advisory/workflow/PR/org policy.

### Lifecycle
`unsupported → proposed → experimental → shadow → supported → deprecated`
(`.l9/release-policy.yaml`). Promote independently (STACK-010).

### Semgrep (only in-tree provider; experimental)
- Machine-readable Semgrep JSON only (`--json-output`). Never parse console.
- Preserve `check_id` as `provider_rule_id` exactly.
- Canonical ID only from `extra.metadata.l9.canonical_rule_id` **or**
  versioned identity map.
- Redact snippets, metavars, absolute paths, env, raw finding bodies.
- Coverage may be limited until a verified scanned-path contract exists.
- Version policy: unsupported Semgrep versions fail explicitly in
  `validate_configuration` (minimum documented in provider code / release
  policy — do not weaken).
- Docs: `docs/architecture/semgrep-provider.md`,
  `docs/architecture/provider-spi.md`.

### Future providers (P5+)
Required deliverables before merge:

- verified machine-readable format
- real redacted fixture (never fabricate)
- provider version + invocation provenance
- malformed-report, path-normalization, deterministic-output tests
- provider-failure tests
- coverage behavior + identity-resolution behavior

---

## 7. Public CLI & packaging

### Runtime packaging (two install paths — keep them aligned)

| Path | Who uses it | How |
|---|---|---|
| **Core provision** | `l9-ci-core` `provision-sdk` | Tree on `PYTHONPATH`; installs [`requirements.txt`](requirements.txt) into the provisioning venv |
| **Local / publish** | Developers + wheel publish | [`pyproject.toml`](pyproject.toml) → `pip install -e .` / hatchling wheel; console script `l9-ci = l9_ci.__main__:main` |

Laws:

- Runtime deps in `pyproject.toml` **must mirror** `requirements.txt` (exact pins).
- Adding a runtime import **requires** updating **both** files together.
- Canonical version: `l9_ci.__version__` **must equal**
  `.l9/integration-contract.yaml` `metadata.version` and `project.version`
  in `pyproject.toml`.
- CI toolchain pins live in `requirements-ci.txt` /
  `[project.optional-dependencies] ci` — not unused placeholder extras.
- Core’s provision path remains source + `requirements.txt`; do not claim
  `pyproject.toml` is absent (publish / local editable install use it).

### CLI (`python -m l9_ci` / `l9-ci`)
| Group | Commands |
|---|---|
| `semgrep` | `detect`, `normalize` |
| `bundle` | `validate`, `project-agent-payload` |
| `compatibility` | `check` |
| `gate` | `evaluate` |
| `providers` | `list`, `detect` |
| `baseline` | `compare-tests`, `scan-packet-envelope`, `compare-scan`, `validate-ledger` |
| `manifest` | `generate`, `check` |

Exit codes (SSOT: `l9_ci/cli/exit_codes.py` + integration-contract):

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | gate_failure |
| 2 | invalid_arguments |
| 3 | provider_execution_failure |
| 4 | provider_report_failure |
| 5 | artifact_validation_failure |
| 6 | unresolved_strict_contract |
| 7 | internal_error |
| 8 | incompatible_version |
| 9 | operational_limit_exceeded |

Core-facing happy path:

```text
semgrep JSON
  → l9-ci semgrep normalize
  → l9-ci bundle validate
  → l9-ci bundle project-agent-payload
  → Core upload / publish
```

Core must not import SDK internals or parse Semgrep JSON itself
(`docs/architecture/core-integration.md`).

---

## 8. Contract-change checklist

Any change to a canonical model / protocol / SPI semantic must include:

1. Python model update (`l9_ci/contracts` or owning package)
2. JSON Schema update (`l9_ci/schemas/v1`)
3. Compatibility assessment (`.l9/compatibility.yaml` / fixtures)
4. Model invariant tests
5. Schema conformance tests
6. ADR update when architectural semantics change
7. Integration-contract / architecture YAML updates when the public surface moves

Compatibility laws (COMPAT-* in `.l9/compatibility.yaml`): schema validation
does **not** replace semantic validation; readers may be strict or tolerant
per declared mode — do not silently repair authority state.

---

## 9. Continuous integration in this repo

### A. Core-driven self-analysis (`l9-analysis*.yml`)
Consumes `l9-ci-core` v2. Core is pinned by **immutable 40-char commit SHA**
in every caller (never branch/tag).

Profiles (`.github/governance/execution-profiles.yaml`):
`pr_fast`, `merge`, `nightly`, `supply_chain`, `release` — each also
`workflow_dispatch`-able.

Shared path:

```text
semgrep (--config p/python)
  → provision-sdk
  → semgrep normalize
  → validate-bundle
  → agent payload
  → route → manifest → upload
  → Core publish-analysis.yml
```

Dogfood posture today: all Core analysis profiles are `advisory` and
`strict: false`. Community `p/python` rules lack L9 canonical IDs; strict
identity resolution would reject every finding at normalize. Promote later
per `.github/governance/promotion-policy.yaml`.

Note: Core’s `publish-analysis.yml` always defines jobs named `shadow` and
`publish`; when mode is `advisory`, `publish` runs and `shadow` is skipped
(UI may still list the skipped job — that is Core layout, not shadow mode).

### B. Self-CI without Core (`l9-self-ci.yml`)
Self-contained PR/main gate (`engine: ci-debt`). Philosophy encoded in the
workflow header: *“CI is a routing system, not a nightclub bouncer.”*
Classifier + rule-modes driven; first activation is advisory-first
(`rule-modes.selfci.yaml`).

### C. YAML governance (SDK-owned product surface)
Reusable workflow: `.github/workflows/l9-yaml-governance.yml`
Dogfood: `.github/workflows/l9-yaml-governance-dogfood.yml`
Configs/checkers: root `lint/` (not `.github/lint/`)
Consumer template: `docs/templates/l9-yaml-governance-caller.yml`

Consumers pin
`Quantum-L9/l9-ci-sdk/.github/workflows/l9-yaml-governance.yml@<40-char-sha>`
and copy `lint/`. Do **not** host this on `Quantum-L9/.github` or
`l9-ci-core`. Independent gate — not a Semgrep `providers` entry.
Details: `docs/architecture/yaml-governance.md`, ADR 0010.

### Governance file format gotcha
Most files under `.github/governance/*.yaml` are **JSON with a `.yaml`
extension** (`json.loads` — no comments, no trailing commas). Real-YAML
companions `rule-modes.selfci.yaml` and `l9-ci-shared-spec.yaml` are skipped
by `lint/check_governance_json.py`.

---

## 10. Local gate & push (fail-closed)

Mechanical checks SSOT: [`.pre-commit-config.yaml`](.pre-commit-config.yaml)
(ruff, yamllint infra/data, governance JSON, action pins, zizmor).
Toolchain pins: [`requirements-ci.txt`](requirements-ci.txt).
Orchestration: root [`Makefile`](Makefile) — does **not** restate tool flags.

```bash
make bootstrap   # once per clone (.venv + hooks + doctor)
make fmt         # intentional autofix; commit results
make check       # hooks → clean tree → mypy → pytest
make push        # check, then git push
```

Rules:

- Ship via `make push`. Do not use `git push --no-verify`.
- Git `pre-push` runs `make check` for raw `git push` too; `make push` sets
  `L9_MAKE_PUSH=1` to skip a double run after it already gated.
- Change hook behavior in `.pre-commit-config.yaml` / `lint/`, not ad-hoc CLIs.
- Local zizmor is fail-closed even when dogfood CI sets `enforce-zizmor: false`.
- `actionlint` remains CI-only until a pre-commit hook is added.

**Dropbox note:** a `.venv` inside Dropbox often breaks mypy’s native
extensions (macOS code signature). Prefer cloning outside Dropbox, or point
Make at an off-Dropbox interpreter:

```bash
make check PYTHON=$HOME/.cache/l9-ci-sdk/venv/bin/python \
  PRE_COMMIT_BIN=$HOME/.cache/l9-ci-sdk/venv/bin/pre-commit
```

---

## Manifest auto-fix
`.github/workflows/l9-manifest-reconcile.yml` reconciles root `MANIFEST.md`
from Git tracked truth on PRs (`l9-ci manifest generate --tracked-only
--exclude-dir memory-bank`).
- Same-repo PRs: bot commits corrections (`contents: write` required).
- Fork PRs: upload `manifest-reconcile.patch`; never use `pull_request_target`.
- Downstream consumers copy that workflow and replace the dogfood
  `PYTHONPATH=.` step with existing Core `provision-sdk` plus the provisioned
  `l9-ci` executable. Pin an SDK revision that includes the `manifest` CLI.
- `memory-bank/` (including WIP packs) is user/agent scratch only — gitignored
  and excluded from `MANIFEST.md`; never treat it as product code.
- This is repository inventory reconciliation, not analysis-artifact
  manifests and not finding repair. See ADR 0009 and
  `docs/architecture/repository-manifest.md`.

---

## Biome static checks
`l9-ci-sdk` owns the reusable Biome static-check workflow
(`.github/workflows/l9-biome-scan.yml`) and root `biome.json` config,
enforcing the Biome formatter/linter ownership over JSON/JS/TS assets.
Dogfood runs via `.github/workflows/l9-biome-scan-dogfood.yml`.
- Consumers pin `Quantum-L9/l9-ci-sdk/.github/workflows/l9-biome-scan.yml@<40-char-sha>`
  and copy `biome.json` into their repo root (see
  `docs/templates/l9-biome-scan-caller.yml`).
- Do **not** host or pin this capability on `Quantum-L9/.github` or
  `l9-ci-core`.
- `biome.json` lives at the repository root (like `ruff.toml`).
- Independent gate — not a Semgrep `providers` entry. Details:
  `docs/architecture/biome.md`, ADR 0011.
- Local: `pre-commit run biome-check --all-files` autofixes via the
  `biome-check` hook; CI runs read-only `biome ci` and is advisory
  (`enforce-biome: false`) until promoted per
  `.github/governance/promotion-policy.yaml`.
- `tests/fixtures/` and `tests/compatibility/fixtures/` are excluded from
  Biome's scope — they intentionally hold malformed/non-canonical JSON for
  provider-parsing failure tests.

---


## Audit findings ledger
Authoritative remediation ledger: `.l9/audit-findings.md`. Route audit closure
work through that ledger before claiming a finding resolved.

---

## 11. Prohibited shortcuts
Do not:

- fabricate provider fixtures
- parse console output when structured output exists
- invent policy keys
- derive canonical identity from severity
- silently discard malformed records
- retain secret material in artifacts
- use absolute source paths in canonical artifacts
- convert required provider failures into PASS
- claim successful validation without executing tests
- import Core/workflow/LSP/Repair/Corpus code into SDK packages
- let providers import artifact internals
- let contracts import providers or artifact infrastructure
- bypass `make check` / pre-commit with `--no-verify`
- float Core pins on branch/tag names
- switch branches / stash / reset / checkout over uncommitted valuable work
- invent extra local branches or long-lived stashes without an explicit user ask
- casually rewrite `README.md` from a feature PR (see §13)

---

## 12. Git & working-tree hygiene (do not lose work)

Uncommitted edits are not durable. Concurrent agents, Dropbox sync, and
branch switches have wiped valid work that never reached git history.

### Laws
1. **WIP commit > stash.** After any non-trivial edit batch, commit:
   `git commit -m "wip: park <topic>"`. Squash or reword later if needed.
2. **Clean tree before switch.** Never `git switch` / `checkout` / `stash` /
   `reset` while the working tree holds work you care about.
3. **One WIP branch per worktree.** For parallel topics, use a second
   `git worktree` — do not interleave stashes across branches.
4. **Push anything that must survive.** Remote tracking + open PR is the
   backup. Local-only branches and unnamed stashes are where work dies.
5. **Do not invent branches/stashes** unless the user explicitly asks.
   Stay on the current branch; do not “park” work by creating spaghetti
   restore branches that point at unrelated tips.
6. **Named stash only as a last resort**, then apply/pop on the **same**
   branch before any further switch:
   `git stash push -u -m "<branch>: <why>"`.

Org-wide agent git hygiene may also be published in
[`Quantum-L9/Cursor-Governance`](https://github.com/Quantum-L9/Cursor-Governance);
when that exists, keep this section aligned and do not weaken it locally.

---

## 13. Documentation ownership (README vs AGENTS)

| File | Audience | Role |
|---|---|---|
| [`README.md`](README.md) | Humans / install consumers | Short product entrypoint: what / install / CLI map / local gate / links |
| [`AGENTS.md`](AGENTS.md) (this file) | Coding agents | Operating law, constellation boundaries, phase status, checklists |
| `docs/architecture/*`, `docs/adr/*`, `.l9/*` | Both | Deep SSOT — wins when prose diverges |

Do **not** paste full architecture essays into `README.md`. Link out.

### README collision rule
Concurrent feature agents historically all rewrote `README.md`, causing
merge fights; a temporary “do not touch README” ban left it stale.

Lasting rule:

1. **Do not edit `README.md` unless this task explicitly owns a README
   realignment** (user asked, or the PR’s acceptance criteria require it).
2. **Never append a feature-marketing section** from an unrelated PR
   (“also see my new workflow…”). That is how collisions restart.
3. Feature PRs update deep docs (`docs/architecture/`, ADRs, `.l9/`) and
   this file when agent-facing law changes — **not** a parallel README rewrite.
4. When install path, CLI groups, local gate, or primary workflows change,
   the landing PR **or** a dedicated docs PR updates `README.md` once and
   keeps it short (link out; do not duplicate this file).
5. If unsure: update `AGENTS.md` / architecture docs only, and leave a
   one-line note for the human — do not speculative-edit README.

### When to update this file (`AGENTS.md`)
- Update when phase status, ownership, packaging, CLI groups, CI surfaces,
  or agent working method change.
- Keep it an **index of laws** already owned by `.l9/*` and ADRs — do not
  invent a second protocol here.
- When contracts/ADRs and this file disagree, contracts/ADRs win; fix this file.

---

## 14. Agent working method

1. Read the relevant ADR + architecture doc + `.l9` contract before editing.
2. Confirm `git status` / current branch; do not start work on the wrong tip.
3. Make the smallest coherent change that preserves layer edges.
4. **WIP-commit** after each coherent batch so a branch switch cannot wipe it.
5. Update tests in the same pass (model invariants, schema conformance,
   provider/malformed/determinism, architecture boundaries as applicable).
6. Update `AGENTS.md` / architecture / ADRs when law or surface changes;
   touch `README.md` only under §13.
7. Run `make check` (or at least the touched slice: `make hooks`,
   `make test PYTEST_ARGS='…'`, `make typecheck`).
8. Ship with `make push`.

Prefer stabilization (invariants, fail-closed behavior, fixture honesty)
over speculative abstractions or second providers.

---

## 15. Key paths

| Path | Why |
|---|---|
| `.l9/architecture.yaml` | Layers, public surface, forbidden edges, canonical flow |
| `.l9/ownership.yaml` | Package ownership + Core boundary |
| `.l9/integration-contract.yaml` | CLI, exit codes, artifact layout, version |
| `.l9/tool-stack.yaml` | STACK laws, owns/excludes |
| `.l9/roadmap.yaml` | Phase status / GA criteria |
| `.l9/compatibility.yaml` | Reader modes / COMPAT rules |
| `.l9/release-policy.yaml` | Provider lifecycle / Semgrep promotion |
| `.l9/semgrep-identity-map.yaml` | Explicit Semgrep → canonical map |
| `docs/adr/` | Architectural decisions |
| `docs/architecture/` | Human architecture SSOT |
| `docs/examples/core-semgrep-integration.sh` | Core integration recipe |
| `l9_ci/contracts/` | Canonical models |
| `l9_ci/providers/spi.py` | Provider SPI |
| `l9_ci/providers/semgrep/` | Only provider implementation |
| `l9_ci/identity/`, `policy/`, `gates/` | Identity / classification / gates |
| `l9_ci/artifacts/`, `schemas/v1/` | Bundles + JSON Schema |
| `l9_ci/integration/` | Compatibility, limits, redaction, projections |
| `l9_ci/pipeline/semgrep.py` | Normalize composition |
| `l9_ci/cli/`, `commands/`, `__main__.py` | CLI SSOT |
| `l9_ci/baseline/` | Baseline-ratchet helpers (not yet in `.l9` ownership) |
| `.github/governance/` | Core v2 instantiation pack |
| `.github/workflows/l9-analysis*.yml` | Core-pinned self-analysis callers |
| `.github/workflows/l9-self-ci.yml` | Core-free self CI |
| `.github/workflows/l9-yaml-governance*.yml` | YAML governance product |
| `.github/workflows/l9-biome-scan*.yml` | Biome static-check product |
| `.github/workflows/l9-manifest-reconcile.yml` | Repository manifest auto-fix |
| `biome.json` | Biome config (JSON/JS/TS ownership) |
| `lint/` | Yamllint profiles + pin/governance checkers |
| `Makefile`, `.pre-commit-config.yaml` | Local fail-closed gate |
| `requirements.txt`, `requirements-ci.txt` | Runtime vs CI toolchain |
| `pyproject.toml` | Local editable install / hatchling wheel / `l9-ci` script |
| `README.md` | Human entrypoint (edit only under §13) |
| `tests/architecture/`, `tests/compatibility/` | Boundary + protocol fixtures |

---

<!-- BEGIN L9 FORMATTER OWNERSHIP (generated — do not edit) -->

## Formatter ownership

Workspace class: `biome_default` — Default for every governed workspace: Biome owns JS/TS/JSON, Ruff owns Python.

Exactly one formatter owns each language. Do not reformat a file with a tool other than its owner, and do not add config for a competing formatter: the result is a diff that churns on every save.

| Languages | Owner | Note |
|---|---|---|
| `javascript`, `javascriptreact`, `typescript`, `typescriptreact`, `json`, `jsonc` | **biome** | bound by the governed IDE profile |
| `python` | **ruff** | bound by the governed IDE profile |

Generated from `environment/ide/policy.json` in the governance clone by `ops/scripts/adapters/agentdocs.sh`. Edit the policy, not this block.

<!-- END L9 FORMATTER OWNERSHIP -->
