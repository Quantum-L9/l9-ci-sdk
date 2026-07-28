# l9-ci-sdk

Canonical analysis contracts, provider adapters, normalized findings,
validation, and deterministic artifact generation for Quantum-L9 CI.

This SDK does **not** own CI workflow orchestration — that responsibility
belongs to [`l9-ci-core`](https://github.com/Quantum-L9/l9-ci-core), which
consumes this package to run analysis and evaluate gates inside a caller's
CI pipeline. See [`AGENTS.md`](./AGENTS.md) for the full architectural
contract, Phase 1 restrictions, and provider requirements.

## What this SDK owns

- Provider-independent parsing of scanner output into canonical findings
- Explicit rule-identity resolution (native provider rule IDs are always
  preserved; canonical rule IDs require explicit resolution)
- Schema and semantic validation of canonical artifacts (`l9_ci/schemas/v1/`)
- Deterministic, atomic canonical bundle writes
- Gate evaluation over normalized findings

## Installation

```bash
pip install -e ".[ci]"
```

The `ci` extra installs the local validation toolchain (`ruff`, `mypy`,
`pytest`, and the type stub packages mypy needs to resolve this SDK's
third-party imports). Runtime-only installs (`pip install -e .`) pull in
just `jsonschema`, `referencing`, and `PyYAML`.

In production, `l9-ci-core`'s `provision-sdk` action installs this package
from source over `PYTHONPATH` rather than from a package index — this repo
ships no build manifest for PyPI distribution (see Phase 1 restrictions in
`AGENTS.md`). `pyproject.toml` exists so the package is locally installable
and editable (`pip install -e .`) and so `l9-ci` resolves as a console
script; it is not a signal that this SDK is published anywhere.

## CLI

```bash
l9-ci --help
```

### Repository manifest

Deterministic inventory generation for root `MANIFEST.md`:

```bash
PYTHONPATH=. python -m l9_ci manifest generate --repository-root . --output MANIFEST.md --tracked-only --exclude-dir memory-bank
PYTHONPATH=. python -m l9_ci manifest check --repository-root . --output MANIFEST.md --tracked-only --exclude-dir memory-bank
```

`memory-bank/` (including WIP packs) is a local scratchpad — gitignored and
excluded from the inventory; it is not part of the SDK codebase.

`generate` always exits successfully after reconciliation. `check` writes a
correction when drift is found and exits with the gate-failure code.

### Manifest auto-fix (CI)

[`.github/workflows/l9-manifest-reconcile.yml`](./.github/workflows/l9-manifest-reconcile.yml)
is a dual-purpose PR auto-fix bot: it dogfoods in this repo and is the
copy-in template for downstream consumers.

- Same-repo PRs: bot commits reconciled `MANIFEST.md` to the PR head.
- Fork PRs: uploads `manifest-reconcile.patch` (no write to the fork).
- Consumers: copy the workflow, keep `contents: write`, replace the dogfood
  `PYTHONPATH=.` generate step with existing Core `provision-sdk` plus
  `"$EXECUTABLE" manifest generate ...`, and pin an SDK revision that
  includes the `manifest` CLI. See
  [`docs/architecture/repository-manifest.md`](./docs/architecture/repository-manifest.md).

## Local validation gate

```bash
ruff check l9_ci tests .github/scripts
ruff format --check l9_ci tests .github/scripts
mypy l9_ci
pytest -q
```

These match the local gate in `requirements-ci.txt` and the advisory Python
jobs in [`.github/workflows/l9-self-ci.yml`](./.github/workflows/l9-self-ci.yml).

## Repository layout

| Path | Purpose |
|---|---|
| `l9_ci/` | The SDK package: providers, gates, execution, repository scanning, schemas |
| `l9_ci/schemas/v1/` | JSON Schemas for canonical artifacts (findings, evidence, gate results, etc.) |
| `tests/` | Unit and pipeline tests |
| `docs/` | Architecture notes and ADRs |
| `.l9/` | Machine-readable SDK metadata (integration contract, tool stack spec) consumed by `l9-ci-core` |

## Contributing

Architectural rules, change policy, and provider requirements are defined in
[`AGENTS.md`](./AGENTS.md) — read it before making changes. Contribution and
security policies are inherited from
[`Quantum-L9/.github`](https://github.com/Quantum-L9/.github).

## License

See [`LICENSE`](./LICENSE).
