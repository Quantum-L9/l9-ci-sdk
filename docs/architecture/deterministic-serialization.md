# Deterministic Serialization
The SDK must produce byte-identical output for logically identical bundles.
## Rules
- UTF-8 encoding
- JSON object keys sorted lexicographically
- no insignificant whitespace
- exactly one trailing newline
- NaN and Infinity prohibited
- evidence sorted by `evidence_id`
- findings sorted by `finding_id`
- classifications sorted by `finding_id`
- providers sorted by `provider_id`
- coverage sorted by `provider_id`
- provider failures sorted by provider and failure type
- limitations sorted lexicographically
## Time fields
`generated_at` is invocation provenance, not content. It is serialized in the
bundle for the record, but it is excluded from the bundle's canonical content
identity (`FindingBundle.canonical_digest()`). Two bundles that differ only by
`generated_at` therefore share a canonical digest.

Determinism guarantees:
- byte-identical output requires a fixed `generated_at` (callers such as Core
  should pin it, e.g. via `--generated-at`);
- content reproducibility (the canonical digest) holds regardless of generation
  time, so it can be asserted across a clock boundary.

The serializer must not inject additional timestamps.
