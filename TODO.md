# TODO

Follow-ups outside the SDK-to-Core workflow handoff implementation.

## generated_at provenance

`FindingBundle.generated_at` is a required ISO-8601 timestamp in the artifact
protocol, but it is write-only inside the SDK. Gate evaluation, coverage,
projection, version negotiation, and redaction do not branch on its value. It
is excluded from content identity through `FindingBundle.canonical_digest()`.

- [ ] Confirm whether `l9-ci-core` or another downstream consumer reads
      `generated_at` for freshness, retention, expiry, or run correlation.
- [ ] If a consumer exists, document the contract and have Core pass an
      explicit `--generated-at`.
- [ ] If no consumer exists, decide whether the field remains required or
      becomes optional/provenance-only.
- [ ] Record the decision in an ADR.

## AUD-006: Core workflow handoff

Implementation state:

- SDK workflow ownership is limited to triggers, permissions, concurrency,
  profile selection, and the immutable Core workflow call.
- Inline Semgrep installation and execution were removed from
  `.github/workflows/l9-analysis*.yml`.
- Inline SDK provisioning and SDK command invocation were removed.
- Inline artifact routing, manifest construction, upload, and publication
  were removed.
- The SDK/Core boundary and reusable-workflow interface are recorded in
  `.l9/integration-contract.yaml`.

Integration verification:

- [ ] Confirm the pinned Core commit contains
      `.github/workflows/analyze-semgrep.yml`.
- [ ] Confirm Core uses one SDK revision for provider execution,
      normalization, validation, gate evaluation, and projection.
- [ ] Run `l9-analysis.yml` through a pull-request event.
- [ ] Run `l9-analysis-merge.yml` through a push to `main`.
- [ ] Run `l9-analysis-nightly.yml` through `workflow_dispatch`.
- [ ] Run `l9-analysis-release.yml` through `workflow_dispatch`.
- [ ] Run `l9-analysis-supply-chain.yml` through `workflow_dispatch`.
- [ ] Confirm every run uploads the raw report, finding bundle, gate result,
      agent-review payload, and artifact manifest.
- [ ] Confirm Core publishes the SDK-produced gate result without
      reconstructing the verdict.
- [ ] Record successful Core workflow-run URLs and close AUD-006.

Known integration gap (recorded at handoff time):

- The only Core commit currently containing
  `.github/workflows/analyze-semgrep.yml` is
  `c5924473f4a765e0fbfc8164afff0ae6e57a9ba9`
  (branch `claude/core-guardrails-self-analysis`); it is not on Core `main`.
- That revision's `workflow_call` interface differs from
  `.l9/integration-contract.yaml` v1.1.0 (it requires `sdk-revision` and does
  not accept `language`, `semgrep-version`, `repository-revision`,
  `retention-days`, or `publish`), and it contains an unresolved
  `{{CORE_PUBLISH_SHA}}` placeholder.
- [ ] Land the contract-conformant `analyze-semgrep.yml` on Core `main`,
      then re-pin all five callers to that immutable commit.

## Handoff maintenance

- Keep all five SDK callers pinned to the same immutable Core commit.
- Update the Core pin only when the reusable workflow contract or an
  orchestrated dependency changes.
- Re-run the five-profile integration verification after any Core workflow
  interface change.
