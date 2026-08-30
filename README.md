---
# l9-ci-sdk

Canonical analysis contracts, provider adapters, normalized findings,
validation, and deterministic artifact generation for the L9 CI constellation.

> **CI Core orchestrates. CI SDK observes.** Downstream products diagnose,
> mutate, learn, prevent, and decide — they are not implemented here.

Agent operating law (architecture, phases, layer edges, git hygiene):
[`AGENTS.md`](AGENTS.md). Deep SSOT: [`docs/architecture/`](docs/architecture/),
[`docs/adr/`](docs/adr/), [`.l9/`](.l9/).

## Install

Python **≥ 3.11**.

```bash
# From PyPI (released package)
pip install "l9-ci==1.0.0"

# Local editable install (console script `l9-ci`)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[ci]"

# Or: runtime deps only (matches Core provision-sdk)
pip install -r requirements.txt
export PYTHONPATH=.
python -m l9_ci --help
```

- PyPI: https://pypi.org/project/l9-ci/
- Runtime pins: [`requirements.txt`](requirements.txt) **and**
  [`pyproject.toml`](pyproject.toml) (must stay in sync).
- CI toolchain pins: [`requirements-ci.txt`](requirements-ci.txt).
- Core’s `provision-sdk` still runs this tree from source on `PYTHONPATH`
  and installs `requirements.txt` into its venv.
- Publishing notes: [`docs/PUBLISHING.md`](docs/PUBLISHING.md).

## CLI map

Entry points: `l9-ci` (after editable/wheel install) or `python -m l9_ci`.

| Group | Commands |
|---|---|
| `semgrep` | `detect`, `normalize` |
| `bundle` | `validate`, `project-agent-payload` |
| `compatibility` | `check` |
| `gate` | `evaluate` |
| `providers` | `list`, `detect` |
| `baseline` | `compare-tests`, `scan-packet-envelope`, `compare-scan`, `validate-ledger` |
| `manifest` | `generate`, `check` |

Core happy path:

```text
semgrep JSON → l9-ci semgrep normalize → l9-ci bundle validate
  → l9-ci bundle project-agent-payload → Core upload / publish
```

Exit codes and contract details: [`docs/architecture/cli-contract.md`](docs/architecture/cli-contract.md),
[`.l9/integration-contract.yaml`](.l9/integration-contract.yaml).

## Local gate (fail-closed)

Mechanical checks SSOT: [`.pre-commit-config.yaml`](.pre-commit-config.yaml).
Orchestration: [`Makefile`](Makefile).

```bash
make bootstrap   # .venv + deps + install pre-commit/pre-push hooks + doctor
make fmt         # intentional autofix (commit results)
make check       # hooks → clean tree → mypy → pytest
make push        # check, then git push
```

Do not bypass with `git push --no-verify`. Prefer `make push`.
Local zizmor is fail-closed even when dogfood CI is advisory.
`actionlint` remains CI-only until a pre-commit hook is added.

**Dropbox / mypy:** a `.venv` inside Dropbox often breaks mypy’s native
extensions. Prefer a clone outside Dropbox, or point Make at an off-Dropbox
interpreter (see `AGENTS.md` §10).

## CI surfaces in this repo

| Surface | Workflows | Role |
|---|---|---|
| Core-driven self-analysis | `l9-analysis*.yml` | Pins `l9-ci-core` by immutable SHA; advisory dogfood today |
| Self-CI (no Core) | `l9-self-ci.yml` | Classifier / rule-modes gate (`engine: ci-debt`) |
| YAML governance | `l9-yaml-governance.yml` + dogfood | Reusable yamllint / governance JSON / Action pins / actionlint / zizmor |
| Biome static checks | `l9-biome-scan.yml` + dogfood | JSON/JS/TS formatter+linter ownership (`biome.json`) |
| Manifest reconcile | `l9-manifest-reconcile.yml` | Keeps root `MANIFEST.md` aligned with tracked truth |

YAML governance configs: root [`lint/`](lint/). Biome config: root
[`biome.json`](biome.json). Downstream callers pin immutable SDK SHAs.
Details: [`docs/architecture/yaml-governance.md`](docs/architecture/yaml-governance.md),
[`docs/architecture/biome.md`](docs/architecture/biome.md),
[`docs/architecture/repository-manifest.md`](docs/architecture/repository-manifest.md).

## Constellation

Roles are the intended architecture. The `v0.1` column is what actually
consumes this SDK today — the two are not the same, and the difference matters
when reading the role column as a description of live wiring. Map:
[`l9-assurance/docs/constellation-v0.1.md`](https://github.com/Quantum-L9/l9-assurance/blob/main/docs/constellation-v0.1.md).

| Product | Role | Consumes this SDK in v0.1 |
|---|---|---|
| [`l9-ci-core`](https://github.com/Quantum-L9/l9-ci-core) | Orchestrates | Yes — provisions and invokes the SDK |
| **l9-ci-sdk** (this repo) | Observes / contracts | — |
| [`l9-ci-debt-resolver`](https://github.com/Quantum-L9/l9-ci-debt-resolver) | Diagnoses | No — its adapter targets `l9.sdk-knowledge-document/v1`, which this SDK does not emit |
| [`PR_Repair`](https://github.com/Quantum-L9/PR_Repair) | Mutates | No — standalone in v0.1; its agent-review payload is a different contract that shares a name |
| [`l9-ci-debt-intelligence`](https://github.com/Quantum-L9/l9-ci-debt-intelligence) | Learns | Declared: `l9.finding-bundle/v1` is its one active production input |
| [`l9-ci-debt-lsp`](https://github.com/Quantum-L9/l9-ci-debt-lsp) | Prevents | No — direct `l9.sdk-finding/v1` consumption is inactive; no producer exists |
| [`l9-assurance`](https://github.com/Quantum-L9/l9-assurance) | Decides | Yes — admits `l9.mandatory-findings` observations |

## Docs for agents (collision policy)

- **`README.md`** — short human entrypoint. Agents must **not** rewrite it
  from unrelated feature PRs (see `AGENTS.md` §13).
- **`AGENTS.md`** — agent operating law; update when law/surface changes.
- **Git hygiene** — WIP commits over stashes; never switch branches over
  uncommitted work (see `AGENTS.md` §12).
