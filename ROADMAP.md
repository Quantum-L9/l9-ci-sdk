<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: ROADMAP.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Roadmap

## Current state

| Phase | Status | Result |
|---|---|---|
| P0 Architecture and contracts | Complete | Models, schemas, SPI, serializer, validation, boundary tests |
| P1 Semgrep vertical slice | Complete with fixture limitation | Import, normalization, identity, policy, failure, bundle |
| P2 Integration and release readiness | Complete | CLI, version negotiation, validation, projection, limits |
| P3 Spec closure | Current | Gates, snapshots, capabilities, profiles, CLI, limits, architecture tests |
| P4 Semgrep shadow rollout | Blocked | Runtime fixture and live Core evidence required |
| P5 Second provider | Deferred | Gitleaks or SARIF only after Semgrep is supported |

## Next milestones

1. Capture and redact a real Semgrep report with provenance.
2. Execute and preserve a live `l9-ci-core` integration run across all five
   profiles.
3. Restore or add canonical reseal tooling, then regenerate `manifest.json`,
   `MANIFEST.md`, and validation evidence for the live tree.
4. Resolve issue #9 packaging/scaffolding decision without violating the current
   source-run contract.
5. Resolve issue #5 by verifying and pinning remaining first-party action SHAs.
6. Promote Semgrep rules only after canonical rule identity is explicit.

## GA criteria

- One supported provider
- Stable v1 artifact protocol
- Stable public Python API
- Stable Core integration contract
- Compatibility fixtures
- Deterministic outputs
- Documented migration and rollback

## Deferred

No second provider, repair loop, LSP integration, corpus analytics, hosted
service, or LLM orchestration enters scope before the current blockers close.
