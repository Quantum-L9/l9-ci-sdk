# Provider SPI
A provider adapter converts one provider-native report into canonical SDK
records.
## Required capabilities
Every provider exposes:
- metadata
- availability detection
- version detection
- configuration validation
- execution planning
- bounded execution
- report import
- report-shape validation
- canonical normalization
- coverage reporting
## Fact and policy separation
Provider normalization may produce:
- `EvidenceRecord`
- `Finding`
- `Coverage`
- `ProviderFailure`
Provider normalization must not produce:
- blocking decisions
- advisory decisions
- workflow status
- pull-request comments
- organizational policy defaults
## Native identity
The provider-native rule identifier must be preserved in
`provider_rule_id`.
A provider may populate `canonical_rule_id` only when identity is supplied by
trusted provider metadata or an explicit versioned mapping.
A provider must not synthesize canonical identity from severity, confidence,
tool name, or message text.
## Failure behavior
Malformed reports and unsupported report versions produce structured provider
failures.
Required provider failures may later cause a gate failure.
Optional provider failures must remain visible in the artifact bundle.
