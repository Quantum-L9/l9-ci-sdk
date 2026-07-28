<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: SECURITY.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
origin: Quantum-L9/.github@54306f8a9a03fd16d323d0287d7c8109211d250e
/L9_META -->
# Security Policy

## Scope

This policy applies to all repositories in the **Quantum-L9** GitHub organization.

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/Quantum-L9/.github/security/advisories/new).

Include:
- Affected repository and version/SHA
- Vulnerability type and CVSS score estimate
- Reproduction steps, preferably a minimal reproducer
- Potential impact assessment
- Proposed mitigations, if known

## Response SLA

| Severity | Acknowledge | Patch Target |
|---|---|---|
| Critical (CVSS 9.0-10.0) | 24 hours | 7 days |
| High (CVSS 7.0-8.9) | 48 hours | 14 days |
| Medium (CVSS 4.0-6.9) | 48 hours | 30 days |
| Low (CVSS 0.1-3.9) | 5 business days | Next release cycle |

## Automated Security Controls

Organization controls include gitleaks, Semgrep, dependency audits, Dependabot,
and OpenSSF Scorecard where wired.

## Disclosure Policy

Quantum-L9 follows coordinated disclosure and requests 90 days to remediate
before public disclosure.


## l9-ci-sdk threat model and controls

| Risk | Control |
|---|---|
| Untrusted provider output | Structured JSON validation before normalization |
| Canonical identity spoofing | Explicit identity resolution; unknown stays unresolved |
| Secret retention | Redaction contract plus diff-scoped gitleaks in self-CI |
| Path leakage | Normalized repository-relative source locations |
| Missing required evidence | Structured provider failure; never converted to PASS |
| Artifact drift | Deterministic serialization plus schema and semantic validation |
| Workflow privilege creep | SDK/Core ownership boundary; SDK does not read GitHub context |

Current enforcement is deliberately asymmetric: newly introduced secrets are
hard-blocking, while lint, type checking, Semgrep, audit, SBOM, and profile
analysis remain advisory. That is the live state, not a promise that all
organization controls are already blocking in this repository.
