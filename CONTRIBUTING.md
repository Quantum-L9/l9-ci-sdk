<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: CONTRIBUTING.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
origin: Quantum-L9/.github@54306f8a9a03fd16d323d0287d7c8109211d250e
/L9_META -->
# Contributing to Quantum-L9

## Governance setup checklist

Before opening a pull request:

- Review the repository `AGENTS.md` and architecture contracts.
- Keep workspace governance wiring intact when it is installed.
- Do not bypass required status checks.
- Notify CODEOWNERS for blast-radius files.

## Branch and commit conventions

- Branches: `feat/<scope>`, `fix/<scope>`, `chore/<scope>`, `docs/<scope>`
- Commits: Conventional Commits format, for example `feat(scope): message`


## Repository-specific setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-ci.txt
```

## Required local validation

```bash
ruff check .
ruff format --check .
mypy l9_ci
pytest -q
```

## Live PR gate expectations

| Surface | Current treatment |
|---|---|
| New secret scan | Blocking |
| Final self-CI gate | Rule-mode aware; blocks configured blocking rules |
| Ruff, mypy, validation, Semgrep, audit, SBOM | Advisory |
| Five Core analysis profiles | Advisory/non-strict |

The live repository differs from the organization template in one material way:
its Core callers use an immutable commit SHA, not `@v1`. Preserve that pinning
model unless an approved migration changes the contract.

## Contract and architecture changes

A canonical model change requires the Python model, JSON Schema, compatibility
assessment, invariant tests, schema conformance tests, and an ADR update when
architectural semantics change.

Provider additions require a verified machine-readable format, real redacted
fixture, provider version and provenance, malformed-report tests, path tests,
determinism tests, failure tests, coverage behavior, and identity behavior.
