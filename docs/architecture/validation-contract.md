# Validation Contract
Validation has three layers.
## 1. Compatibility validation
Checks:
- artifact protocol
- supported schema major version
- reader compatibility
## 2. JSON Schema validation
Checks:
- required properties
- field types
- enum membership
- structural shape
- forbidden additional properties
## 3. Semantic validation
Checks:
- unique evidence IDs
- unique finding IDs
- unique classification references
- valid evidence references
- valid finding references
- valid provider references
- snapshot consistency
- one coverage record per requested provider
- matching summary counts
Schema validation does not replace semantic validation.
