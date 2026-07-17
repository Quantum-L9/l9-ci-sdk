# l9-ci-sdk Architecture
`l9-ci-sdk` is the canonical analysis contract layer for the L9 CI
ecosystem.
The SDK separates five concerns:
1. Provider acquisition
2. Evidence normalization
3. Finding construction
4. Policy classification
5. Gate evaluation
Provider adapters produce facts. They do not decide whether findings block a
change.
## Dependency direction
```text
contracts
   ↑
providers
contracts
   ↑
artifacts

contracts must not depend on providers or artifact infrastructure.

providers must not depend on artifact infrastructure.

artifacts must not depend on provider implementations.

Phase 1 boundary

Phase 1 contains:

* canonical contracts
* provider SPI
* provider registry
* schemas
* serializers
* validators
* architecture tests
* roadmap
* ADR seeds

Phase 1 does not contain scanner implementations.
