---
# l9-ci-sdk

Canonical analysis contracts, provider adapters, normalized findings,
validation, and deterministic artifact generation for the L9 CI constellation.

See [`AGENTS.md`](AGENTS.md) for architectural rules and agent operating notes.

## Local gate

Mechanical checks are owned by [`.pre-commit-config.yaml`](.pre-commit-config.yaml).
The root [`Makefile`](Makefile) orchestrates that suite plus `mypy` / `pytest`.
Push is fail-closed: use `make push`, and a git `pre-push` hook runs `make check`
even for raw `git push` (unless `make push` already cleared the gate).

```bash
make bootstrap   # .venv + deps + install pre-commit/pre-push hooks + doctor
make fmt         # intentional autofix via pre-commit (commit results)
make check       # hooks + clean tree + mypy + pytest
make push        # check, then git push
```

`make deps` creates `.venv/` when missing (PEP 668–safe). Override with
`make check PYTHON=/path/to/python` if you manage your own environment.

Do not bypass with `git push --no-verify`. Prefer `make push` / `make check`.
Known CI-only gap: `actionlint` (yaml-governance workflow); local zizmor is stricter
than the dogfood caller’s advisory setting.

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
