---
# l9-ci-sdk

Canonical analysis contracts, provider adapters, normalized findings,
validation, and deterministic artifact generation for the L9 CI constellation.

See [`AGENTS.md`](AGENTS.md) for architectural rules and agent operating notes.

## YAML governance

This repository owns a reusable GitHub Actions workflow for YAML/workflow
static checks (yamllint, governance JSON contract, Action SHA pins, actionlint,
zizmor).

| Artifact | Path |
|---|---|
| Reusable workflow | [`.github/workflows/l9-yaml-governance.yml`](.github/workflows/l9-yaml-governance.yml) |
| Dogfood caller | [`.github/workflows/l9-yaml-governance-dogfood.yml`](.github/workflows/l9-yaml-governance-dogfood.yml) |
| Configs + checkers | [`lint/`](lint/) |
| Consumer template | [`docs/templates/l9-yaml-governance-caller.yml`](docs/templates/l9-yaml-governance-caller.yml) |
| Architecture | [`docs/architecture/yaml-governance.md`](docs/architecture/yaml-governance.md) |
| ADR | [`docs/adr/0010-yaml-governance-static-checks.md`](docs/adr/0010-yaml-governance-static-checks.md) |

Downstream: copy `lint/`, pin an immutable SDK SHA in the caller template.
Do not use `Quantum-L9/.github` or `l9-ci-core` as the host for this capability.
