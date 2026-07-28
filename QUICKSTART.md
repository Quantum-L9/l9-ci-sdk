<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: QUICKSTART.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Quickstart

## Prerequisites

- Python 3.11 or newer
- Git
- A source checkout of `Quantum-L9/l9-ci-sdk`

## Set up

```bash
git clone https://github.com/Quantum-L9/l9-ci-sdk.git
cd l9-ci-sdk
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-ci.txt
```

## Verify the CLI contract

```bash
PYTHONPATH=. python -m l9_ci --help
PYTHONPATH=. python -m l9_ci providers list
PYTHONPATH=. python -m l9_ci providers detect --root .
```

## Run the local gate

```bash
ruff check .
ruff format --check .
mypy l9_ci
pytest -q
```

## Normalize a Semgrep report

```bash
PYTHONPATH=. python -m l9_ci semgrep normalize   --input artifacts/raw/semgrep/report.json   --output artifacts/l9/finding-bundle.json   --root .   --snapshot-id LOCAL-SNAPSHOT
PYTHONPATH=. python -m l9_ci bundle validate artifacts/l9/finding-bundle.json
```

Use a real machine-readable Semgrep JSON report. Do not fabricate fixtures or
parse console output. Add `--strict` or `--required` only when the selected
policy and identity map support those modes.

## Expected result

The CLI returns a stable exit code and writes a deterministic canonical bundle.
Exit-code meanings are authoritative in `.l9/integration-contract.yaml`.
