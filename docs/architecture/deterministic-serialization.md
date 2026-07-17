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
`generated_at` is part of the bundle content.
Determinism tests must either:
- provide a fixed `generated_at`; or
- compare bundles after explicitly controlling generation time.
The serializer must not inject additional timestamps.
