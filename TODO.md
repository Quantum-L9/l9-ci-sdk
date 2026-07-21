# TODO

Follow-ups tracked outside the current change set.

## generated_at provenance

`FindingBundle.generated_at` is a required ISO-8601 timestamp in the artifact
protocol, but it is **write-only** inside the SDK: nothing in `l9_ci/` branches
on its value (gate evaluation, coverage, projection, version negotiation, and
redaction all ignore it), and it is excluded from content identity via
`FindingBundle.canonical_digest()`.

- [ ] Confirm whether `l9-ci-core` (or any downstream consumer) actually reads
      `generated_at` — e.g. for freshness, artifact retention/expiry, or CI-run
      correlation. It is not consumed anywhere in this repo.
- [ ] If a consumer exists: document that contract and have Core pass an
      explicit `--generated-at` so canonical bundles are byte-reproducible
      (content is already reproducible regardless, via `canonical_digest()`).
- [ ] If no consumer exists: decide whether `generated_at` should remain a
      required field in `l9_ci/schemas/v1/finding-bundle.schema.json` or become
      optional / provenance-only, and record the decision in an ADR.

## AUD-006: cross-repo workflow-ownership follow-up (blocked on l9-ci-core)

The SDK's `.github/workflows/l9-analysis*.yml` still run `semgrep scan` and the
Core composite actions within one job. They cannot shrink to a pure `uses:` thin
caller of Core's reusable workflow because Core's
`normalize-semgrep-report.yml` re-checks-out `github.sha` and reads the report
from the tree — it cannot receive a freshly-generated (uncommitted) report.

- [ ] **l9-ci-core**: add a reusable analysis workflow that accepts the raw
      Semgrep report as an uploaded **artifact** (not an in-tree `report-path`),
      so consumer repos can reduce their caller to: `scan → upload-artifact →
      uses: Core/analysis.yml`.
- [ ] **l9-ci-sdk (after Core lands the above)**: convert `l9-analysis*.yml` to
      thin `uses:` callers and delete the inline orchestration. Requires GitHub
      Actions verification (cannot be validated locally).
- The SDK-side portion done now: removed the "copy-in template / template
      authority" framing and recorded Core ownership in `.l9/ownership.yaml`
      (`workflow_ownership`).
