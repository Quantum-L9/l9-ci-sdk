# TODO

Follow-ups tracked outside the current change set.

## Issue unblock (session reference)

**Cluster:** Quantum-L9/l9-ci-sdk#86
**Owning fix:** https://github.com/Quantum-L9/l9-ci-sdk/pull/85 (`0dee89c`)
**Next:** human letters on leftover OPEN issues; do not chain l9-pr-remediation while open_issues=10
**Pickup:** Graphiti PICKUP written 2026-09-02

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

## AUD-006: cross-repo workflow-ownership follow-up (closed)

Closed by ADR-0016. The `l9-analysis*.yml` and `l9-nightly.yml` Core callers
(Core-SHA-pinned delegations to Core reusable workflows) were removed; the
GitHub organization required-workflow ruleset runs `Quantum-L9/l9-ci-core`
`main` `.github/workflows/org-ci.yml` against this repository directly, and
`tests/architecture/test_l9_wiring.py` fails if a Core caller or a Core/SDK
pin returns.

- [x] **l9-ci-core**: central `org-ci.yml` runs the SDK-provisioned analysis
      in the consumer's checkout; no raw-report handoff is needed.
- [x] **l9-ci-sdk**: no analysis callers remain; Core ownership is recorded in
      `.l9/ownership.yaml` (`workflow_ownership`).
