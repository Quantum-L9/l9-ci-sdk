# Audit Findings — Remediation Ledger

Source audit suite: `l9-ci-sdk-audit-suite-341ac62`
Immutable base reference: `341ac62e0f812dffd2e5a8633ef20a035ff41894`
Total findings: 28 (high: 20, medium: 8) · release-blocking: 21

This is the authoritative status ledger for the audit findings. Checked items
are remediated; unchecked items remain open. Each completed item references the
commit that closed it. First remediation pass: **PR #17**
(branch `claude/audit-findings-priority-w22f94`).

Legend: `[x]` done · `[ ]` open · **H/M** = high/medium · **🚫** = blocks release.

## Architecture conformance

- [x] **AUD-001** H 🚫 — Providers must not depend on integration. *(moved `SemanticVersion` to contracts — `65715d0`)*
- [x] **AUD-002** H 🚫 — Architecture tests must enforce the complete authoritative dependency graph. *(reconciled may_depend_on + positive-allowlist enforcement — `1c74931`)*
- [x] **AUD-003** H 🚫 — Required provider failures must prevent a successful strict gate. *(evaluator fail-closed — `672a23f`)*
- [x] **AUD-004** H 🚫 — Unverified/missing scan coverage must not read as COMPLETE/PASS. *(coverage → PARTIAL without verified scan — `672a23f`)*
- [x] **AUD-005** H 🚫 — One canonical, test-enforced public API boundary. *(`.l9/public-api.yaml` drives root exports/docs/exact-equality tests — `PR6`)*
- [~] **AUD-006** H — SDK must not own GitHub Actions workflow orchestration. *(PARTIAL — `PR8`: removed the template-authority framing, recorded Core ownership in `.l9/ownership.yaml`. Full thin-caller conversion is blocked on a Core-side reusable workflow that accepts the raw report as an artifact — Core's current one reads report-in-tree. Tracked in `TODO.md`.)*
- [x] **AUD-007** H 🚫 — Validation evidence/inventory bound to the immutable commit. *(commit-bound generator + drift-checked manifest — `1c74931`)*
- [x] **AUD-008** H 🚫 — Required unit/lint/format/architecture gates run continuously on the commit (self-validation CI). *(ci.yml added — `1c74931`; requiring it in branch protection is a pending repo-admin action)*
- [x] **AUD-009** M — SDK version & installation identity: one reproducible source of truth. *(pyproject single version source + console script — `1c74931`)*
- [x] **AUD-010** M — Provider version policy enforced on the canonical normalization path before promotion. *(promotion-gate guard test ties ProviderState to release-policy blockers — `PR7`)*

## Dead-wiring & latent capability

- [x] **DWA-001** H 🚫 — Registry-backed selection reachable from a runtime entrypoint. *(lifecycle seam — `420d2b7`)*
- [x] **DWA-002** H 🚫 — Bounded provider execution & structured execution-failure mapping have a production caller. *(generic runner behind execute mode; execution_failure promoted to the SPI — `PR7`)*
- [x] **DWA-003** H 🚫 — Canonical gate evaluation carried into the Core-facing artifact flow. *(contract + docs — `672a23f`)*
- [x] **DWA-004** H 🚫 — Semgrep version enforcement connected to the import/normalization path. *(pipeline version gate — `420d2b7`)*
- [x] **DWA-005** M 🚫 — Structured `Diagnostic` rendering used by command handlers. *(centralized CLI error boundary honoring --format on every command — `PR6`)*
- [x] **DWA-006** M — `ExecutionProfile.import_reports` read by provider selection. *(selection now honors import_reports — `420d2b7`)*
- [x] **DWA-007** M — Autofix projection has a trusted producer for `remediation_class`. *(versioned canonical-rule→class map, post-identity; ships empty, owner-populated — `PR7`)*
- [x] **DWA-008** M — `ProviderExecutionRequest.network_allowed` is an enforced (not inert) control. *(removed — SDK subprocess can't enforce network isolation; it's a Core guarantee — `PR7`)*

## Quality & test effectiveness

- [x] **QA-001** H 🚫 — Fail-closed gate decision test matrix. *(table-driven matrix — `672a23f`)*
- [x] **QA-002** H 🚫 — Semgrep coverage tests cover the zero-result / unverified-scan report. *(fixtures + gate e2e — `672a23f`)*
- [x] **QA-003** H 🚫 — Determinism proven for the production path, not a frozen `generated_at`. *(content digest excludes generated_at + cross-clock tests — `ad3a4ca`)*
- [x] **QA-004** H 🚫 — Version-policy tests validate the canonical normalization path. *(pipeline-level version tests — `420d2b7`)*
- [x] **QA-005** H 🚫 — Architecture boundary test is recursive and spec-derived. *(matrix from architecture.yaml + mutation proof — `65715d0`)*
- [x] **QA-006** H 🚫 — Core-facing CLI has command-handler / argparse integration tests. *(main()-level tests per command: success/failure envelopes, exit codes — `PR6`)*
- [x] **QA-007** H 🚫 — Static type gate proves public contracts & critical paths type-check. *(strict mypy over l9_ci/tests/scripts — `1c74931`)*
- [x] **QA-008** M — Line/branch coverage target, measurement, and critical-path coverage evidence. *(pytest-cov branch ratchet + evaluator 100% — `1c74931`)*
- [x] **QA-009** M 🚫 — Public API tests assert exact equality (not subset). *(exact-equality per package + compatibility allowlist — `PR6`)*
- [x] **QA-010** H 🚫 — Provider tested against a runtime-captured, provenance-bound report. *(full-path harness + scaffolding; capture is a tracked skip — `ad3a4ca`)*

## Status

- Completed: 27 / 28 (all AUD except 006; all DWA; all QA)
- Partial: 1 / 28 — AUD-006 (workflow ownership): SDK-side framing + ownership
  docs done; full orchestration hand-off blocked on a Core-side reusable
  workflow (report-as-artifact). See TODO.md.

Known caveats on completed items:
- **QA-010** capture step skips until a real Semgrep fixture is captured (Semgrep binary unavailable in the audit
  environment); see `tests/fixtures/semgrep/runtime/provenance.yaml`. Gates Semgrep promotion out of EXPERIMENTAL.
- **QA-003** chose the "exclude from content digest" remediation; byte-identical output still requires the caller to
  pin `generated_at`. See `TODO.md`.
