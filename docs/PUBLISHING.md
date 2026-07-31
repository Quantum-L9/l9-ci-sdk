<!-- L9_META
l9_schema: 1
origin: l9-ci-sdk
layer: [docs, release]
tags: [L9_CI, release, pypi, install]
owner: platform
status: active
/L9_META -->

# Publishing & installing the `l9-ci` SDK

`l9-ci` is consumed by `l9-ci-core`'s reusable workflows as a **runtime CLI**
(installed by a command), not as a checked-in dependency. This document describes
how it is installed and how releases are published.

## Package facts

- **Distribution name:** `l9-ci`
- **Import package:** `l9_ci`
- **Console entry point:** `l9-ci` → `l9_ci.cli:main`
- **Build backend:** hatchling
- **Requires:** Python `>=3.11`
- **Runtime deps (exact pins; mirror `requirements.txt`):**
  `jsonschema==4.26.0`, `referencing==0.37.0`, `PyYAML==6.0.3`
- **Current version (`pyproject.toml` / `l9_ci.__version__` /
  `.l9/integration-contract.yaml`):** `1.0.0`
- **PyPI:** https://pypi.org/project/l9-ci/ (`1.0.0` published 2026-07-31)

## Install paths

### Index install (preferred for humans / local smoke)

```bash
python -m pip install "l9-ci==1.0.0"
l9-ci providers list
```

### Pinned Git ref (Core / CI default today)

Core still commonly installs from a pinned immutable SHA (never a floating
branch). That remains valid alongside the index:

**Public repo (no token):**
```bash
python -m pip install "l9-ci @ git+https://github.com/Quantum-L9/l9-ci-sdk.git@<COMMIT_SHA>"
```

**Private repo (token):** set an `SDK_TOKEN` with read access to
`Quantum-L9/l9-ci-sdk`. The example below rewrites GitHub HTTPS URLs via
`git config` for the install step. That places the token in the git config
value (GitHub Actions secret masking still redacts `${SDK_TOKEN}` in logs,
but this is not stronger than that — do not leave the rewrite configured on
shared runners or developer machines):
```bash
git config --global url."https://x-access-token:${SDK_TOKEN}@github.com/".insteadOf "https://github.com/"
python -m pip install "l9-ci @ git+https://github.com/Quantum-L9/l9-ci-sdk.git@<COMMIT_SHA>"
git config --global --unset-all url."https://x-access-token:${SDK_TOKEN}@github.com/".insteadOf || true
```

`l9-ci-core`'s reusable workflows default `l9-ci-install-command` to the public
Git form and support the private form when `SDK_TOKEN` is provided.

### Editable / developer install

```bash
pip install -e ".[ci]"
# or Core-style:
pip install -r requirements.txt
```

## Releasing (publish workflow)

`.github/workflows/publish.yml`:

- **`workflow_dispatch`** — builds the sdist/wheel and runs `twine check` only.
  No publish. Safe to run anytime to validate packaging.
- **Push a `v*` tag** — builds, checks, verifies the tag matches the
  `pyproject.toml` version, then publishes to PyPI with username `__token__`
  and environment secret `PYPI_API_TOKEN` on the GitHub **`pypi`**
  environment.

### Auth model (current)

| Item | Value |
|------|--------|
| Owner / repo | `Quantum-L9` / `l9-ci-sdk` |
| Workflow | `publish.yml` |
| GitHub environment | `pypi` |
| Auth | PyPI API token (`user=__token__`) |
| GitHub secret | environment secret `pypi` / `PYPI_API_TOKEN` |
| Operator SSOT | AWS Secrets Manager `openclaw-igorbot/pypi` (`us-east-1`, JSON `token`) |

`v1.0.0` was first uploaded out-of-band with that AWS token after Trusted
Publisher OIDC returned `invalid-publisher`. The workflow now uses the same
token path via the GitHub environment secret so future `v*` tags publish
without OIDC.

### Rotate / re-sync the token

```bash
# After rotating on pypi.org, update AWS then mirror into GitHub:
aws secretsmanager put-secret-value --region us-east-1 \
  --secret-id openclaw-igorbot/pypi \
  --secret-string '{"token":"pypi-…","username":"__token__"}'

aws secretsmanager get-secret-value --region us-east-1 \
  --secret-id openclaw-igorbot/pypi --query SecretString --output text \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"], end="")' \
  | gh secret set PYPI_API_TOKEN -R Quantum-L9/l9-ci-sdk --env pypi
```

Trusted Publishing (OIDC) remains optional future hardening; do not remove the
API-token path until a publisher with matching claims is verified green on a
tag dry-run.

### Version / tag note

- Annotated tag **`v1.0.0`** released; GitHub Release:
  https://github.com/Quantum-L9/l9-ci-sdk/releases/tag/v1.0.0
- Older tag `v0.1.0` predates current remediations — do not use as an install
  pin for current `main`.
- Future releases: bump version triad → tag `vX.Y.Z` matching
  `pyproject.toml` → `publish.yml` uploads with `PYPI_API_TOKEN`.
