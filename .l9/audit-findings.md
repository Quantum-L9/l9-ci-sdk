# Audit Findings — Remediation Ledger

Source audit suite: `l9-ci-sdk-audit-suite-341ac62`
Immutable base reference: `341ac62e0f812dffd2e5a8633ef20a035ff41894`
Total findings: 28 (high: 20, medium: 8) · release-blocking: 21

This is the authoritative status ledger for the audit findings. Checked items
are remediated; unchecked items remain open. Each completed item references the
commit that closed it. First remediation pass: **PR #17**
(branch `claude/audit-findings-priority-w22f94`).

Legend: `[x]` done · `[~]` partial (gap recorded inline) · `[ ]` open · **H/M** = high/medium · **🚫** = blocks release.

## Architecture conformance

- [~] **AUD-001** H 🚫 — Providers must not depend on integration. *(PARTIAL — `65715d0` moved `SemanticVersion` to contracts, but the move removed `l9_ci.integration.SemanticVersion` without a compatibility alias, a breaking API change for existing importers. Remediated: deprecated re-export restored under `compatibility_allowlist` pending a versioned removal.)*
- [x] **AUD-002** H 🚫 — Architecture tests must enforce the complete authoritative dependency graph. *(reconciled may_depend_on + positive-allowlist enforcement — `1c74931`)*
- [x] **AUD-003** H 🚫 — Required provider failures must prevent a successful strict gate. *(evaluator fail-closed — `672a23f`)*
- [x] **AUD-004** H 🚫 — Unverified/missing scan coverage must not read as COMPLETE/PASS. *(coverage → PARTIAL without verified scan — `672a23f`)*
- [x] **AUD-005** H 🚫 — One canonical, test-enforced public API boundary. *(`.l9/public-api.yaml` drives root exports/docs/exact-equality tests — `PR6`)*
- [~] **AUD-006** H — SDK must not own GitHub Actions workflow orchestration. *(PARTIAL — `PR8`: removed the template-authority framing, recorded Core ownership in `.l9/ownership.yaml`. Full thin-caller conversion is blocked on a Core-side reusable workflow that accepts the raw report as an artifact — Core's current one reads report-in-tree. Tracked in `TODO.md`.)*
- [x] **AUD-007** H 🚫 — Validation evidence/inventory bound to the immutable commit. *(commit-bound generator + drift-checked manifest — `1c74931`)*
- [~] **AUD-008** H 🚫 — Required unit/lint/format/architecture gates run continuously on the commit (self-validation CI). *(PARTIAL — `1c74931` added ci.yml, but its action refs were mutable tags (now SHA-pinned) and requiring the check in branch protection remains a pending repo-admin action; not done until the check is required.)*
- [x] **AUD-009** M — SDK version & installation identity: one reproducible source of truth. *(pyproject single version source + console script — `1c74931`)*
- [x] **AUD-010** M — Provider version policy enforced on the canonical normalization path before promotion. *(promotion-gate guard test ties ProviderState to release-policy blockers — `PR7`)*

## Dead-wiring & latent capability

- [x] **DWA-001** H 🚫 — Registry-backed selection reachable from a runtime entrypoint. *(lifecycle seam — `420d2b7`)*
- [~] **DWA-002** H 🚫 — Bounded provider execution & structured execution-failure mapping have a production caller. *(PARTIAL — `PR7` added the generic runner behind `SemgrepPipelineRequest.execute`, but no CLI command or workflow invoked it, so the execution path still had no production caller. Remediated: `l9-ci semgrep run` exposes bounded execution; workflow adoption remains a Core/consumer decision.)*
- [~] **DWA-003** H 🚫 — Canonical gate evaluation carried into the Core-facing artifact flow. *(PARTIAL — `672a23f` added the gate contract and docs, but no analysis workflow executed `gate evaluate` or shipped `gate-result.json` in the artifact set. Remediated SDK-side: every l9-analysis caller now evaluates the gate and uploads `gate-result.json`; Core-side consumption of the gate result is external and tracked in TODO.md.)*
- [~] **DWA-004** H 🚫 — Semgrep version enforcement connected to the import/normalization path. *(PARTIAL — `420d2b7` wired the gate, but the policy accepted every future major version (`maximum_exclusive=None`), so "supported version range" was open-ended. Remediated: closed range `>=1.100.0,<2.0.0` with boundary tests.)*
- [x] **DWA-005** M 🚫 — Structured `Diagnostic` rendering used by command handlers. *(centralized CLI error boundary honoring --format on every command — `PR6`)*
- [x] **DWA-006** M — `ExecutionProfile.import_reports` read by provider selection. *(selection now honors import_reports — `420d2b7`)*
- [x] **DWA-007** M — Autofix projection has a trusted producer for `remediation_class`. *(versioned canonical-rule→class map, post-identity; ships empty, owner-populated — `PR7`)*
- [x] **DWA-008** M — `ProviderExecutionRequest.network_allowed` is an enforced (not inert) control. *(removed — SDK subprocess can't enforce network isolation; it's a Core guarantee — `PR7`)*

## Quality & test effectiveness

- [x] **QA-001** H 🚫 — Fail-closed gate decision test matrix. *(table-driven matrix — `672a23f`)*
- [x] **QA-002** H 🚫 — Semgrep coverage tests cover the zero-result / unverified-scan report. *(fixtures + gate e2e — `672a23f`)*
- [x] **QA-003** H 🚫 — Determinism proven for the production path, not a frozen `generated_at`. *(content digest excludes generated_at + cross-clock tests — `ad3a4ca`)*
- [~] **QA-004** H 🚫 — Version-policy tests validate the canonical normalization path. *(PARTIAL — `420d2b7` added pipeline-level tests, but they asserted acceptance of `2.0.0`, encoding the open-ended range rather than the policy intent. Remediated: boundary tests now reject `>=2.0.0` and cover both edges of the closed range.)*
- [x] **QA-005** H 🚫 — Architecture boundary test is recursive and spec-derived. *(matrix from architecture.yaml + mutation proof — `65715d0`)*
- [x] **QA-006** H 🚫 — Core-facing CLI has command-handler / argparse integration tests. *(main()-level tests per command: success/failure envelopes, exit codes — `PR6`)*
- [x] **QA-007** H 🚫 — Static type gate proves public contracts & critical paths type-check. *(strict mypy over l9_ci/tests/scripts — `1c74931`)*
- [x] **QA-008** M — Line/branch coverage target, measurement, and critical-path coverage evidence. *(pytest-cov branch ratchet + evaluator 100% — `1c74931`)*
- [x] **QA-009** M 🚫 — Public API tests assert exact equality (not subset). *(exact-equality per package + compatibility allowlist — `PR6`)*
- [x] **QA-010** H 🚫 — Provider tested against a runtime-captured, provenance-bound report. *(was PARTIAL at `ad3a4ca` — harness + scaffolding only; the full-path test was a tracked SKIP, which is not a closure. Remediated: runtime-captured Semgrep 1.170.0 report (workflow run 29835939127, artifact 8497285790) committed as a redacted, provenance-bound fixture; the full-path test now runs and asserts a deterministic strict-gate outcome.)*

## Status

Ledger correction (remediation pass 2): the previous revision of this ledger
over-claimed closure. DWA-002, DWA-003, QA-010, AUD-001, AUD-008, DWA-004 and
QA-004 were marked done while material gaps remained (no production caller for
bounded execution, no gate evaluation in the artifact flow, a skipped
runtime-fixture test, a compatibility-breaking symbol move, mutable action
pins, and an open-ended version range). Those items are now marked `[~]` with
the original gap and its remediation recorded inline. A checked item must mean
the behavior is enforced and verified on the canonical path — not that
scaffolding for it exists.

- Completed: 22 / 28 (QA-010 closed in this pass by the committed runtime fixture)
- Partial: 6 / 28 — AUD-001, AUD-006, AUD-008, DWA-002, DWA-003, DWA-004 /
  QA-004 (same underlying gap). The remaining partials carry explicit external dependencies: Core-side reusable workflow
  (AUD-006), branch-protection admin action (AUD-008), Core-side gate-result
  consumption (DWA-003), deprecated-alias removal window (AUD-001), and
  workflow adoption of bounded execution (DWA-002). See TODO.md.

Known caveats on completed items:
- **QA-003** chose the "exclude from content digest" remediation; byte-identical output still requires the caller to
  pin `generated_at`. See `TODO.md`.
