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
