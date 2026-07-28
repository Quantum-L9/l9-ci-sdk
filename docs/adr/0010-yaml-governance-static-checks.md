---
# ADR 0010: YAML Governance Static Checks

## Status

Accepted

## Context

Workflow and governance YAML failures are cheap to introduce and expensive to
discover late. Community `yamllint` alone cannot enforce:

- JSON-as-YAML governance documents parsed by Core with `json.loads`;
- SHA-pinned `uses:` refs and in-file Core pin consistency;
- GitHub Actions semantic / shellcheck issues;
- workflow security findings (zizmor).

A WIP pack proposed hosting this reusable workflow on Core or the org
`.github` repository. That conflicts with this repository’s ownership of
SDK-adjacent CI capabilities and with the product-repo convention that tool
configs live at the repository root (alongside `ruff.toml`), not under
`.github/lint/`.

## Decision

`l9-ci-sdk` owns:

- reusable workflow `.github/workflows/l9-yaml-governance.yml` (`workflow_call`);
- dogfood caller `.github/workflows/l9-yaml-governance-dogfood.yml`;
- tool configs and stdlib checkers under root `lint/`;
- unit tests under `tests/yaml/`.

Forbidden hosts for this capability:

- `Quantum-L9/.github` (org defaults repo);
- `Quantum-L9/l9-ci-core` as the reusable workflow owner.

Downstream consumers pin an immutable SDK commit SHA and copy `lint/` into
their repository root. Dogfood uses `uses: ./.github/workflows/…` to avoid a
self-pin chicken/egg.

Activation defaults: `enforce-actionlint: true`, `enforce-zizmor: false`
(promote zizmor using the evidence bar in `.github/governance/promotion-policy.yaml`).

Hybrid governance: JSON pack files under `.github/governance/` remain strict
JSON. Real-YAML self-CI companions (`rule-modes.selfci.yaml`,
`l9-ci-shared-spec.yaml`) are fully skipped by `lint/check_governance_json.py`.

## Consequences

- YAML/workflow static checks are an independent CI gate (not a Semgrep
  provider / execution-profile entry).
- Consumers must copy `lint/`; missing configs fail closed.
- Floating Action tags in workflows are rejected by `check_action_pins.py`.
- Biome and other formatter CI remain out of scope for this ADR.
