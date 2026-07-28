# l9-ci-sdk

Canonical analysis contracts, provider adapters, normalized findings,
validation, gate evaluation, and deterministic artifact generation for the L9
CI constellation.

> **CI Core orchestrates. CI SDK observes and decides analysis contracts.**
> Downstream products diagnose, mutate, learn, prevent, and assure; they are
> not implemented here.

Agent operating law: [`AGENTS.md`](AGENTS.md). Architecture and contract SSOT:
[`docs/architecture/`](docs/architecture/), [`docs/adr/`](docs/adr/), and
[`.l9/`](.l9/).

## Install

Python **≥ 3.11**.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[ci]"
l9-ci --help
```

Runtime dependencies are pinned in both
[`requirements.txt`](requirements.txt) and [`pyproject.toml`](pyproject.toml).
CI dependencies are pinned in [`requirements-ci.txt`](requirements-ci.txt).

Core provisions an immutable SDK revision and runs it from its own reusable
analysis workflows. Consumer repositories do not install or invoke the SDK
directly.

## CLI map

Entry points: `l9-ci` or `python -m l9_ci`.

| Group | Commands |
|---|---|
| `semgrep` | `detect`, `run`, `normalize` |
| `bundle` | `validate`, `project-agent-payload` |
| `compatibility` | `check` |
| `gate` | `evaluate` |
| `providers` | `list`, `detect` |
| `baseline` | `compare-tests`, `scan-packet-envelope`, `compare-scan`, `validate-ledger` |
| `manifest` | `generate`, `check` |

Contract details:

- [`.l9/integration-contract.yaml`](.l9/integration-contract.yaml)
- [`docs/architecture/cli-contract.md`](docs/architecture/cli-contract.md)
- [`docs/architecture/core-integration.md`](docs/architecture/core-integration.md)
- [`docs/architecture/artifact-protocol.md`](docs/architecture/artifact-protocol.md)

## Core-orchestrated analysis

Consumer workflows are thin callers of Core:

```text
repository event
  → l9-ci-core reusable analysis workflow
  → resolve governance
  → provision Semgrep
  → provision immutable l9-ci-sdk
  → l9-ci semgrep run
  → l9-ci bundle validate
  → l9-ci gate evaluate
  → l9-ci bundle project-agent-payload
  → Core route / manifest / upload / publish
```

Core owns:

- workflow orchestration;
- SDK revision selection;
- provider runtime provisioning;
- governance resolution;
- artifact routing and upload;
- publication of the SDK-produced gate result.

SDK owns:

- provider adapters;
- provider-report normalization;
- canonical artifacts;
- validation;
- policy classification;
- gate evaluation;
- downstream projections.

Core must publish the SDK-produced gate result. It must not reconstruct a
verdict from finding counts, provider exit codes, or projected payloads.

## SDK repository analysis callers

The five `l9-analysis*.yml` workflows in this repository contain only:

- event triggers;
- concurrency;
- minimum permissions;
- execution profile;
- matrix identifier;
- language and provider-version inputs;
- an immutable call to Core's reusable analysis workflow.

They do not install Semgrep, provision the SDK, execute SDK commands, route
artifacts, upload artifacts, or publish checks.

| Workflow | Profile | Matrix ID |
|---|---|---|
| `l9-analysis.yml` | `pr_fast` | `pr-semgrep` |
| `l9-analysis-merge.yml` | `merge` | `merge-semgrep` |
| `l9-analysis-nightly.yml` | `nightly` | `nightly-semgrep` |
| `l9-analysis-release.yml` | `release` | `release-semgrep` |
| `l9-analysis-supply-chain.yml` | `supply_chain` | `supply-chain-semgrep` |

All five callers must pin the same immutable Core commit containing
`.github/workflows/analyze-semgrep.yml`.

## Local gate

Mechanical checks are defined in
[`.pre-commit-config.yaml`](.pre-commit-config.yaml) and orchestrated through
the [`Makefile`](Makefile).

```bash
make bootstrap
make fmt
make check
make push
```

Do not bypass repository checks with `git push --no-verify`.

## CI surfaces

| Surface | Workflows | Role |
|---|---|---|
| Core-driven self-analysis | `l9-analysis*.yml` | Thin callers of Core's reusable Semgrep analysis workflow |
| Self-CI | `l9-self-ci.yml` | SDK repository classifier and rule-mode checks |
| YAML governance | `l9-yaml-governance.yml` and dogfood workflow | YAML, governance JSON, Action pin, actionlint, and zizmor checks |
| Biome static checks | `l9-biome-scan.yml` and dogfood workflow | JSON, JavaScript, and TypeScript formatting and linting |
| Manifest reconciliation | `l9-manifest-reconcile.yml` | Keeps `MANIFEST.md` aligned with tracked repository state |

## Constellation

| Product | Role |
|---|---|
| [`l9-ci-core`](https://github.com/Quantum-L9/l9-ci-core) | Orchestrates |
| **l9-ci-sdk** (this repo) | Observes, normalizes, validates, and evaluates |
| [`l9-ci-debt-resolver`](https://github.com/Quantum-L9/l9-ci-debt-resolver) | Diagnoses |
| [`PR_Repair`](https://github.com/Quantum-L9/PR_Repair) | Mutates |
| [`l9-ci-debt-intelligence`](https://github.com/Quantum-L9/l9-ci-debt-intelligence) | Learns |
| [`l9-ci-debt-lsp`](https://github.com/Quantum-L9/l9-ci-debt-lsp) | Prevents |
| [`l9-assurance`](https://github.com/Quantum-L9/l9-assurance) | Assures |

## Agent documentation policy

- `README.md` is the concise human entry point.
- `AGENTS.md` is the agent operating law.
- Architecture and protocol changes belong in `docs/architecture/`,
  `docs/adr/`, and `.l9/`.
- Use WIP commits instead of stashes and do not switch branches over
  uncommitted work.
