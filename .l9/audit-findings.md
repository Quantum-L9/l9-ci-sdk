# Audit Findings - Final Remediation Ledger

Source audit base: `341ac62e0f812dffd2e5a8633ef20a035ff41894`  
Runtime SDK code revision: `0c487747b0fcd172edaefe9e843dac818de8fc12`  
SDK workflow/evidence revision: `4c7fbb785dac5b65cc74263c4b28afa6fa95959b`  
Core reusable analysis revision: `c3f04e1268364e3623fc57f963937e2a0665e0e0`

Evidence map SSOT: `docs/release/evidence-map.yaml` (Path A seal 2026-07-31).

## Findings

- [x] **AUD-001** `BLOCKER` - Authoritative dependency direction: providers must not depend on integration.
  - Evidence: PR #17 base plus SDK S1 (`0c487747b0fcd172edaefe9e843dac818de8fc12`)
- [x] **AUD-002** `BLOCKER` - Architecture tests must enforce the complete authoritative dependency graph.
  - Evidence: PR #17 architecture enforcement at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **AUD-003** `BLOCKER` - Required provider failures must prevent successful strict gate evaluation.
  - Evidence: PR #17 fail-closed evaluator at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **AUD-004** `BLOCKER` - Unverified or missing scan coverage must not be represented as COMPLETE or PASS.
  - Evidence: PR #17 verified coverage semantics at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **AUD-005** `BLOCKER` - The SDK must have one canonical, test-enforced public API boundary.
  - Evidence: SDK S1 (`0c487747b0fcd172edaefe9e843dac818de8fc12`) public API manifest plus v1 compatibility alias
- [x] **AUD-006** `NON-BLOCKER` - The SDK must not own or distribute GitHub Actions workflow orchestration assigned to l9-ci-core.
  - Evidence: Core C3 (`c3f04e1268364e3623fc57f963937e2a0665e0e0`) and SDK S3 (`4c7fbb785dac5b65cc74263c4b28afa6fa95959b`) thin callers
- [x] **AUD-007** `BLOCKER` - Validation evidence and repository inventory must be bound to the immutable commit being released.
  - Evidence: SDK S3 (`4c7fbb785dac5b65cc74263c4b28afa6fa95959b`) and validation artifact https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182197/artifacts/8797085061
- [x] **AUD-008** `BLOCKER` - Required unit, lint, format, and architecture gates must run continuously on the commit under review.
  - Evidence: Path A waiver for issue/ruleset/± proofs (see evidence-map); positive tip CI https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182197; admin ruleset proof deferred to Path B
- [x] **AUD-009** `NON-BLOCKER` - SDK version and installation identity must have one reproducible source of truth.
  - Evidence: PR #17 package metadata at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **AUD-010** `NON-BLOCKER` - Declared provider version policy must be enforced on the canonical normalization path before promotion.
  - Evidence: SDK S1 (`0c487747b0fcd172edaefe9e843dac818de8fc12`) and runtime evidence in SDK S2 (`0c487747b0fcd172edaefe9e843dac818de8fc12`)
- [x] **DWA-001** `BLOCKER` - Registry-backed capability detection and execution-profile selection are not reachable from a runtime entrypoint.
  - Evidence: PR #17 registry lifecycle at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **DWA-002** `BLOCKER` - Bounded provider execution and structured execution-failure mapping have no production caller.
  - Evidence: SDK S1 (`0c487747b0fcd172edaefe9e843dac818de8fc12`) plus Core C3 production caller (`c3f04e1268364e3623fc57f963937e2a0665e0e0`)
- [x] **DWA-003** `BLOCKER` - Canonical gate evaluation is implemented and CLI-reachable but omitted from the Core-facing artifact flow.
  - Evidence: Core analyze pin `c3f04e1268364e3623fc57f963937e2a0665e0e0`; CORE_ACTIONS/CORE_PUBLISH Path A waived (thin caller); run https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182783; check https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182783/job/91188145152
- [x] **DWA-004** `BLOCKER` - Semgrep version enforcement exists but is not connected to the import and normalization path.
  - Evidence: SDK S1 (`0c487747b0fcd172edaefe9e843dac818de8fc12`) exact Semgrep 1.170.0 enforcement
- [x] **DWA-005** `BLOCKER` - Structured Diagnostic rendering is public and documented but unused by command handlers.
  - Evidence: PR #17 structured diagnostics, retained and integration-tested by SDK S1 (`0c487747b0fcd172edaefe9e843dac818de8fc12`)
- [x] **DWA-006** `NON-BLOCKER` - ExecutionProfile.import_reports is defined and serialized but never read by provider selection.
  - Evidence: PR #17 provider selection fix at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **DWA-007** `NON-BLOCKER` - Autofix candidate projection has no trusted producer for remediation_class in the active provider path.
  - Evidence: PR #17 trusted remediation map at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **DWA-008** `NON-BLOCKER` - ProviderExecutionRequest.network_allowed is an inert control in the built-in execution path.
  - Evidence: PR #17 removal of inert network flag at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **QA-001** `BLOCKER` - The gate decision engine lacks a complete fail-closed behavioral test matrix.
  - Evidence: PR #17 exhaustive gate matrix at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **QA-002** `BLOCKER` - Semgrep coverage tests omit the zero-result report with no verified scanned-path inventory.
  - Evidence: PR #17 zero-result fixtures and gate tests at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **QA-003** `BLOCKER` - Determinism tests freeze generated_at and therefore do not test the production default path.
  - Evidence: SDK S1 (`0c487747b0fcd172edaefe9e843dac818de8fc12`) requires generated-at and preserves byte determinism
- [x] **QA-004** `BLOCKER` - Semgrep version-policy tests validate the helper but not the canonical normalization path that must enforce it.
  - Evidence: SDK S1 (`0c487747b0fcd172edaefe9e843dac818de8fc12`) pipeline/CLI version tests and SDK S2 runtime proof (`0c487747b0fcd172edaefe9e843dac818de8fc12`)
- [x] **QA-005** `BLOCKER` - The architecture boundary test checks a hand-written subset non-recursively and misses a real forbidden import.
  - Evidence: PR #17 recursive spec-derived architecture mutation tests at `4bc1526330188a7e209adf4c1109236ec726d869`
- [x] **QA-006** `BLOCKER` - The Core-facing CLI boundary has no command-handler or argparse integration tests.
  - Evidence: PR #17 command integration tests plus SDK S1 execute CLI tests (`0c487747b0fcd172edaefe9e843dac818de8fc12`)
- [x] **QA-007** `BLOCKER` - No static type gate proves the public SDK contracts and critical paths type-check.
  - Evidence: PR #17/S3 strict mypy required check; tip self-validation https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182197 (AUD-008 positive ruleset proof Path A waived)
- [x] **QA-008** `NON-BLOCKER` - The repository reports a test count but has no line or branch coverage target, measurement, or critical-path coverage evidence.
  - Evidence: PR #17/S3 branch coverage ratchet; validation artifact https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182197/artifacts/8797085061
- [x] **QA-009** `BLOCKER` - Public API tests use subset assertions and cannot detect accidental exports or undeclared compatibility expansion.
  - Evidence: SDK S1 (`0c487747b0fcd172edaefe9e843dac818de8fc12`) exact API manifest plus explicit compatibility allowlist
- [x] **QA-010** `BLOCKER` - Provider behavior is tested only against a representative Semgrep fixture, not a runtime-captured and provenance-bound report.
  - Evidence: SDK S2 runtime capture and non-skipped full-path test (`0c487747b0fcd172edaefe9e843dac818de8fc12`)

## Closure summary

- Release-blocking findings closed: **21 / 21**
- Total findings closed: **28 / 28**
- AUD-008 administrator issue: Path A waived — see `docs/release/evidence-map.yaml`
- AUD-008 active ruleset: Path A waived — see `docs/release/evidence-map.yaml`
- Canonical gate publication run: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182783
- Canonical gate check: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182783/job/91188145152
- Commit-bound SDK validation artifact: https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182197/artifacts/8797085061
