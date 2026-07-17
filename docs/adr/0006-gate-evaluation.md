# ADR 0006: Separate Gate Evaluation from Classification
## Status
Accepted
## Context
Classification states how governance treats a finding. Gate evaluation decides
the overall outcome of a bundle.
Provider failures and incomplete coverage can prevent a trustworthy result
even when no blocking finding exists.
## Decision
Gate evaluation is a separate SDK stage.
Gate status is one of:
- pass
- fail
- incomplete
- invalid
Missing required evidence can never produce pass.
## Consequences
- Classification remains finding-local.
- Provider completeness affects the overall decision.
- Core publishes the result but does not calculate it.
