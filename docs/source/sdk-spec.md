Yes. Starting over is the better decision.

The existing repository is still small—seven visible commits—and currently presents itself as a reusable Python CLI that owns scanner and gate logic, centralized Git-aware file enumeration, and a local-first pipeline runner. That makes it an appropriate place to establish the tool substrate cleanly rather than migrating the oversized Core normalizer into it. 

The reset should preserve only these conclusions from the prior work:

* scanner integrations belong in l9-ci-sdk;
* Core should invoke the SDK rather than parse scanner output;
* evidence, findings, policy classification, and gate decisions are separate stages;
* machine-readable provider formats are required;
* providers should be added one verified vertical slice at a time.

The broad multi-repository architecture, corpus platform, LSP runtime, repair planning, SQLite knowledge graph, and advanced program-analysis roadmap should not be part of the first tool-stack specification.

Here is the clean replacement.

schema: l9.tool-stack-spec/v1

metadata:
repository: Quantum-L9/l9-ci-sdk
repository_url: https://github.com/Quantum-L9/l9-ci-sdk
spec_path: .l9/tool-stack.yaml
spec_version: 1.0.0
status: proposed
last_updated: 2026-07-17

purpose:
statement: >-
Define the supported analysis, validation, normalization, and gate tool
stack for l9-ci-sdk without assigning CI workflow orchestration, repair
planning, editor behavior, or fleet intelligence to this repository.

primary_outcome: >-
Every supported tool produces a validated machine-readable report that is
converted into canonical SDK evidence and findings through a provider
adapter.

canonical_flow:
- repository_enumeration
- capability_detection
- provider_selection
- provider_execution_or_report_import
- provider_report_validation
- canonical_evidence_normalization
- canonical_finding_construction
- explicit_rule_identity_resolution
- policy_classification
- gate_evaluation
- artifact_bundle_emission

scope:
owns:
- Git-aware repository file enumeration
- local-first scanner execution
- provider process execution
- provider report import
- machine-readable report parsing
- canonical evidence records
- canonical finding records
- source-location normalization
- severity normalization
- provider failure records
- coverage and limitation records
- explicit rule identity mapping
- policy classification library
- gate evaluation library
- deterministic artifact serialization
- artifact schema validation
- public Python API
- public CLI

excludes:
- GitHub Actions workflow orchestration
- workflow permissions
- artifact upload and download
- organizational rule promotion
- fleet corpus storage
- historical recurrence analytics
- LSP protocol
- editor code actions
- repair strategy generation
- repository mutation
- PR retry loops
- general-purpose RAG
- hosted services
- LLM orchestration
- speculative universal semantic graph

architectural_rules:

* id: STACK-001
    rule: Provider parsing is policy-independent.
* id: STACK-002
    rule: Canonical findings never embed a CI verdict.
* id: STACK-003
    rule: Policy classification never changes provider facts.
* id: STACK-004
    rule: Gate evaluation consumes classifications and provider failures.
* id: STACK-005
    rule: Human-readable console output is not a durable provider contract.
* id: STACK-006
    rule: Missing required evidence is not PASS.
* id: STACK-007
    rule: Native provider rule IDs are always preserved.
* id: STACK-008
    rule: Canonical rule IDs and policy keys require explicit resolution.
* id: STACK-009
    rule: Unknown or unsupported provider behavior is labeled, not inferred.
* id: STACK-010
    rule: Every provider is integrated and released independently.

canonical_models:
source_location:
required:
- normalized_path
optional:
- start_line
- start_column
- end_line
- end_column
- byte_start
- byte_end

constraints:
  - paths use POSIX separators
  - paths are repository-relative
  - traversal paths are rejected
  - absolute paths are rejected or redacted
  - line and column numbers are positive when present

evidence:
required:
- evidence_id
- snapshot_id
- provider_id
- provider_rule_id
- evidence_type
- message
- locations
- attributes
- limitations

optional:
  - provider_version
  - canonical_rule_id
  - severity
  - confidence
  - provider_fingerprint
  - identifiers

finding:
required:
- finding_id
- snapshot_id
- provider_id
- provider_rule_id
- category
- message
- evidence_ids
- locations
- fingerprint
- attributes
- limitations

optional:
  - canonical_rule_id
  - severity
  - confidence
  - remediation_class

classification:
required:
- finding_id
- mode
- resolution_status
- used_default

optional:
  - policy_key
  - policy_version
  - waiver_id
modes:
  - blocking
  - advisory
  - shadow
  - disabled
  - unresolved

provider_failure:
required:
- provider_id
- failure_type
- message
- required
- fatal

optional:
  - provider_version
  - report_path
  - exit_code
  - diagnostics

coverage:
required:
- provider_id
- status
- files_considered
- files_analyzed
- limitations

statuses:
  - complete
  - partial
  - skipped
  - unsupported
  - failed

bundle:
protocol: l9.finding-bundle/v1
required_sections:
- schema
- SDK_version
- snapshot
- providers
- evidence
- findings
- classifications
- provider_failures
- coverage
- limitations
- summary

identity:
snapshot_id:
source: deterministic repository snapshot descriptor

evidence_id:
inputs:
- snapshot_id
- provider_id
- provider_rule_id
- normalized_path
- normalized_range
- stable_provider_discriminator

finding_id:
relationship: deterministic fingerprint-derived identity

provider_rule_id:
authority: provider-native rule identity

canonical_rule_id:
authority: explicit SDK mapping or trusted L9 rule metadata

policy_key:
authority: explicit governance mapping

resolution_order:
- trusted_L9_rule_metadata
- versioned_external_mapping
- unresolved

prohibitions:
- provider_name_plus_severity_fallback
- provider_name_plus_confidence_fallback
- implicit_SEMGREP_EXPERIMENTAL_fallback
- silently_changed_native_rule_id

severity:
canonical_values:
- critical
- high
- medium
- low
- informational
- unknown

requirements:
- preserve provider-native severity in attributes
- normalize through provider-specific explicit maps
- unknown provider values map to unknown
- unmapped values produce a limitation

provider_contract:
required_metadata:
- provider_id
- adapter_version
- supported_report_formats
- execution_support
- import_support
- network_requirement
- default_requiredness

required_operations:
- detect
- detect_version
- validate_configuration
- build_execution_plan
- execute
- import_report
- validate_report_shape
- normalize
- report_coverage

process_controls:
- timeout
- output_size_limit
- environment_allowlist
- working_directory
- network_policy
- exit_code_interpretation
- cancellation
- redacted_command_record

provider_states:
- unsupported
- proposed
- experimental
- shadow
- supported
- deprecated

tool_selection_principles:

* machine-readable output exists and is documented
* report shape can be represented with bounded parsing
* tool provides unique evidence not already covered
* tool can operate in local or CI environments
* tool execution can be bounded by timeout and output size
* licensing and distribution are compatible
* network behavior is explicit
* tool version can be recorded
* provider can be tested with real redacted fixtures
* downstream consumers benefit from normalized findings

stack:
foundation:
python:
role: SDK runtime
state: supported
required: true

git:
  role: repository-aware file enumeration and snapshot inputs
  state: supported
  required: true
json:
  role: canonical interchange
  state: supported
  required: true
yaml:
  role: configuration and policy input
  state: supported
  required: true
json_schema:
  role: artifact contract validation
  state: required_target
  required: true

native_checks:
python_ast:
role: Python syntax and deterministic structural checks
state: supported_or_existing
execution: in_process
priority: P0

terminology_guard:
  role: repository terminology policy
  state: existing
  execution: in_process
  priority: P0
banned_imports:
  role: deterministic import policy
  state: existing
  execution: in_process
  priority: P0
transport_packet_check:
  role: L9-specific contract validation
  state: existing
  execution: in_process
  priority: P0
deprecated_api_check:
  role: L9-specific deprecated API detection
  state: existing
  execution: in_process
  priority: P0

external_providers:
semgrep:
role:
- static analysis
- security patterns
- structural rules
preferred_format: JSON
alternate_format: SARIF
network_default: false
state: first_vertical_slice
priority: P1
notes:
- preserve check_id as provider_rule_id
- accept canonical identity only through trusted metadata or mapping
- preserve scan errors as limitations or provider failures

gitleaks:
  role:
    - secret detection
  preferred_format: JSON
  network_default: false
  state: next_after_semgrep
  priority: P2
  notes:
    - never retain secret values
    - fingerprints must exclude secret material
    - redacted fixtures only
sarif:
  role:
    - universal external static-analysis import gateway
  preferred_format: SARIF_2_1_0
  network_default: false
  state: planned
  priority: P3
  notes:
    - import only
    - redact command lines and absolute paths
    - preserve code flows and related locations when present
bandit:
  role:
    - Python security analysis
  preferred_format: JSON
  network_default: false
  state: planned
  priority: P4
  notes:
    - do not parse screen output
    - preserve test_id
    - normalize severity and confidence independently
pip_audit:
  role:
    - Python dependency vulnerability evidence
  preferred_format: JSON
  network_default: explicit
  state: planned
  priority: P5
  notes:
    - record vulnerability database provenance
    - distinguish direct and transitive packages when available
    - cache network-derived results when supported
SBOM:
  role:
    - dependency and component inventory
  preferred_formats:
    - CycloneDX_JSON
    - SPDX_JSON
  network_default: false
  state: planned
  priority: P6
  notes:
    - import before vulnerability enrichment
    - preserve raw component identifiers
    - normalize package URLs when present
Scorecard:
  role:
    - repository supply-chain posture
  preferred_format: SARIF
  network_default: true
  state: deferred
  priority: P7
  blockers:
    - network semantics
    - authentication semantics
    - real report fixture
    - stable rule mapping
Dependency_Review:
  role:
    - pull-request dependency delta risk
  preferred_format: unknown
  network_default: true
  state: unsupported
  priority: deferred
  blockers:
    - no verified stable structured output contract
    - GitHub-event coupling
    - action-output behavior unverified
TruffleHog:
  role:
    - secret detection
  preferred_format: unknown
  network_default: false
  state: unsupported
  priority: deferred
  blockers:
    - actual invocation and report schema unverified
    - overlap with Gitleaks not yet justified
Safety:
  role:
    - Python dependency vulnerability evidence
  preferred_format: unknown
  network_default: explicit
  state: unsupported
  priority: deferred
  blockers:
    - installed version unknown
    - report schema unknown
    - overlap with pip-audit not yet justified
MegaLinter:
  role:
    - aggregate lint execution
  preferred_format: unknown
  network_default: false
  state: unsupported
  priority: deferred
  blockers:
    - aggregate report schema not verified
    - individual linter normalization may be more precise
Radon:
  role:
    - Python complexity metrics
  preferred_format: JSON
  state: unsupported
  priority: deferred
  blockers:
    - no verified current consumer requirement
JSCPD:
  role:
    - duplicate-code metrics
  preferred_format: JSON
  state: unsupported
  priority: deferred
  blockers:
    - no verified current consumer requirement

execution_profiles:
native:
providers:
- python_ast
- terminology_guard
- banned_imports
- transport_packet_check
- deprecated_api_check

security_fast:
providers:
- native
- semgrep
- gitleaks

security_python:
providers:
- native
- semgrep
- gitleaks
- bandit
- pip_audit

supply_chain:
providers:
- SBOM
- pip_audit

import_only:
behavior: import existing machine-readable reports without executing tools

all_supported:
behavior: execute only providers whose state is supported

CLI:
commands:
providers_list:
syntax: l9-ci providers list

providers_detect:
  syntax: l9-ci providers detect --root .
provider_run:
  syntax: >-
    l9-ci providers run semgrep --root . --output
    artifacts/raw/semgrep.json
report_import:
  syntax: >-
    l9-ci findings import --provider semgrep --input
    artifacts/raw/semgrep.json --output
    artifacts/l9/findings.unclassified.json
classify:
  syntax: >-
    l9-ci findings classify --input
    artifacts/l9/findings.unclassified.json --policy
    .github/governance/rule-modes.yaml --output
    artifacts/l9/findings.classified.json --strict
bundle_build:
  syntax: >-
    l9-ci bundle build --input-dir artifacts/l9 --output
    artifacts/l9/finding-bundle.json
bundle_validate:
  syntax: l9-ci bundle validate artifacts/l9/finding-bundle.json
gate_evaluate:
  syntax: >-
    l9-ci gate evaluate --bundle artifacts/l9/finding-bundle.json

exit_codes:
0: success
1: finding_gate_failure
2: invalid_arguments
3: provider_execution_failure
4: provider_report_failure
5: schema_validation_failure
6: unresolved_strict_identity_or_policy
7: internal_error

artifact_layout:
root: artifacts

raw:
path: artifacts/raw
contents:
- provider-native machine-readable reports

canonical:
path: artifacts/l9
contents:
- evidence.jsonl
- findings.unclassified.jsonl
- classifications.jsonl
- finding-bundle.json
- coverage.json
- provider-runs.json

requirements:
- output directories are created by the SDK
- writes are atomic
- filenames are deterministic
- matrix callers supply unique roots
- raw provider artifacts are separate from canonical artifacts

validation:
bundle_checks:
- exact schema version
- required field types
- valid canonical enums
- unique evidence IDs
- unique finding IDs
- every finding evidence reference exists
- every classification finding reference exists
- classified bundles have exactly one classification per finding
- summary counts match records
- paths satisfy normalization rules
- provider failures use valid types
- coverage exists for every requested provider
- forbidden raw secret fields are absent

fixture_requirements:
- generated from a real tool invocation
- tool version recorded
- invocation recorded
- sensitive values redacted
- raw structure otherwise preserved
- checksum recorded
- provenance document included

provider_acceptance:
- real fixture parses
- malformed JSON or SARIF fails
- wrong top-level shape fails
- missing required sections fail
- unknown fields do not corrupt canonical output
- path traversal is rejected
- external paths are rejected or redacted
- provider version is captured
- native rule identity is preserved
- severity mapping is tested
- duplicate findings do not collide
- output is byte-deterministic
- full SDK test suite passes

release_policy:
provider_state_transitions:
unsupported_to_proposed:
requirements:
- consumer_need
- verified_machine_format
- initial_design

proposed_to_experimental:
  requirements:
    - adapter
    - real_fixture
    - schema_tests
    - documentation
experimental_to_shadow:
  requirements:
    - Core integration
    - non-blocking observation
    - failure telemetry
    - compatibility results
shadow_to_supported:
  requirements:
    - stable identities
    - acceptable false-positive behavior
    - deterministic output
    - version compatibility
    - documented operational limits
supported_to_deprecated:
  requirements:
    - replacement_or_removal_reason
    - migration_window
    - compatibility_notice

roadmap:

* phase: P0
    title: Canonical contracts
    deliverables:
    * source location model
    * evidence model
    * finding model
    * classification model
    * provider failure model
    * coverage model
    * finding bundle schema
    * deterministic serializer
    * strict validator
* phase: P1
    title: Provider SPI
    deliverables:
    * provider interface
    * provider registry
    * process runner
    * report importer
    * provider metadata
    * execution and import modes
* phase: P2
    title: Semgrep vertical slice
    deliverables:
    * JSON adapter
    * real redacted fixture
    * explicit identity resolution
    * policy classification
    * deterministic bundle
    * CLI integration
* phase: P3
    title: First Core consumption
    deliverables:
    * documented Core CLI contract
    * artifact layout
    * strict validation
    * agent payload projection contract
* phase: P4
    title: Gitleaks
    deliverables:
    * redacted JSON adapter
    * secret-safe identity strategy
    * Core shadow integration
* phase: P5
    title: SARIF gateway
    deliverables:
    * SARIF 2.1.0 importer
    * location and code-flow normalization
    * redaction policy
* phase: P6
    title: Python security and dependencies
    deliverables:
    * Bandit JSON adapter
    * pip-audit JSON adapter
    * SBOM import
* phase: P7
    title: Operational hardening
    deliverables:
    * provider compatibility matrix
    * timeout and output limits
    * structured diagnostics
    * performance tests
    * artifact migration policy

non_goals_until_after_P7:

* Tree-sitter platform
* SQLite knowledge graph
* universal symbol graph
* call graph
* control-flow graph
* data-flow engine
* architecture contract DSL expansion
* corpus persistence
* LSP incremental runtime
* repair context API
* autonomous repair
* vector retrieval

agent_contract:
must:
- implement one roadmap phase at a time
- inspect existing SDK abstractions first
- use real provider output fixtures
- preserve native provider identities
- separate facts from policy
- label unsupported behavior
- validate deterministic output
- run the complete SDK test suite

must_not:
- modify l9-ci-core in the same change unless explicitly assigned
- implement multiple new providers in one task
- fabricate fixtures
- parse human-readable output when machine output exists
- embed organizational policy into provider adapters
- claim integration without a real invocation path
- add speculative semantic-platform scope
- infer unsupported provider schemas

required_delivery_evidence:
- exact repository revision
- complete changed-file list
- fixture provenance
- provider version
- command transcript
- test transcript
- deterministic output hash comparison
- schema validation transcript
- known limitations

acceptance:
first_release_target:
description: >-
A complete Semgrep vertical slice from real JSON report to validated
canonical finding bundle.

required:
  - canonical models
  - schemas
  - provider SPI
  - Semgrep adapter
  - identity resolution
  - policy classification
  - bundle validation
  - deterministic output
  - public CLI
  - real redacted fixture
  - full tests
explicitly_not_required:
  - Core workflow patch
  - second provider
  - agent payload changes
  - corpus export
  - semantic graph
  - repair integration

unknowns:

* Current internal module boundaries require repository inventory.
* Current package versioning mechanism requires verification.
* Current Python dependency policy requires verification.
* Current gate policy model requires inventory before reuse.
* Current native scanner result formats require inventory.

This is the right restart boundary:

P0 contracts
→ P1 provider SPI
→ P2 Semgrep only
→ stop and validate

Core already installs the SDK as its runtime CLI, currently pinned to a specific SDK commit, so the first integration can remain narrow once the SDK contract is stable. 