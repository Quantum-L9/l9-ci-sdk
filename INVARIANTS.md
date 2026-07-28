<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: INVARIANTS.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Invariants

| ID | Invariant | Enforcement |
|---|---|---|
| INV-001 | Provider parsing is policy-independent | Architecture boundary tests and provider SPI |
| INV-002 | Native provider rule IDs are preserved | Semgrep provider and determinism tests |
| INV-003 | Canonical IDs require explicit resolution | Identity resolver tests |
| INV-004 | Unknown identities remain unresolved | Strict/tolerant compatibility and identity tests |
| INV-005 | Console output is not an integration contract | Provider report import contract |
| INV-006 | Canonical writes are deterministic and atomic | Serializer and deterministic serialization tests |
| INV-007 | Schema and semantic validation are both required | Artifact validator and schema conformance tests |
| INV-008 | Required provider failures never become PASS | Gate evaluator and provider failure tests |
| INV-009 | SDK contracts do not import workflow/scanner implementations | Dependency-boundary tests |
| INV-010 | Providers do not import artifact internals | Dependency-boundary tests |
| INV-011 | Canonical artifacts use repository-relative paths | Repository and provider path tests |
| INV-012 | Secret material is not retained | Redaction tests and diff-scoped gitleaks |
| INV-013 | Unsupported artifact majors are rejected | Compatibility fixtures |
| INV-014 | Generated evidence is regenerated, never hand-edited | Documentation compliance process |

## Enforcement reality

Only newly introduced secrets are hard-blocking by default in self-CI. Other
checks are advisory unless the rule-mode policy promotes them. An invariant may
be structurally tested without being a branch-protection block; do not conflate
test coverage with merge policy.

## Intentional false positives and exclusions

- Ruff ignores `docs/` because Markdown is outside the Python lint surface.
- Community Semgrep rules may produce findings with no L9 canonical identity.
  Those findings stay visible in advisory/non-strict mode.
- Audit and SBOM jobs skip when their required engine or manifest is absent.
  A clean skip is not proof that the absent control ran.
