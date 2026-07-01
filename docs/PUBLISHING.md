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
how it is installed today and how it will be installed once published.

## Package facts

- **Distribution name:** `l9-ci`
- **Import package:** `l9_ci`
- **Console entry point:** `l9-ci` → `l9_ci.cli:main`
- **Build backend:** hatchling
- **Requires:** Python `>=3.11`; runtime dependency `pyyaml`
- **Current version (`pyproject.toml`):** `1.0.0`

## Install paths

### Short-term (today): install from the SDK repo by pinned ref

Until the package is published to an index, install directly from GitHub, pinned
to an immutable commit (never a floating branch):

**Public repo (no token):**
```bash
python -m pip install "l9-ci @ git+https://github.com/Quantum-L9/l9-ci-sdk.git@<COMMIT_SHA>"
```

**Private repo (token):** set an `SDK_TOKEN` with read access to
`Quantum-L9/l9-ci-sdk`, then rewrite the transport before installing (the token
is never placed on the command line or echoed):
```bash
git config --global url."https://x-access-token:${SDK_TOKEN}@github.com/".insteadOf "https://github.com/"
python -m pip install "l9-ci @ git+https://github.com/Quantum-L9/l9-ci-sdk.git@<COMMIT_SHA>"
```

`l9-ci-core`'s reusable workflows default `l9-ci-install-command` to the public
form above and support the private form automatically when `SDK_TOKEN` is
provided. See `l9-ci-core` docs for caller examples.

### Long-term (target): `pip install l9-ci`

Once the package is published (below), callers drop the ref pin and use the
plain default:
```bash
python -m pip install l9-ci
```

## Releasing (publish workflow)

`.github/workflows/publish.yml`:

- **`workflow_dispatch`** — builds the sdist/wheel and runs `twine check` only.
  No publish. Safe to run anytime to validate packaging.
- **Push a `v*` tag** — builds, checks, verifies the tag matches the
  `pyproject.toml` version, then publishes to PyPI via **Trusted Publishing**
  (OIDC; no API token stored). The publish job runs in the `pypi` environment
  so the org can require an approval before release.

### One-time prerequisites (must be configured before a real release)

| Item | Status | Action |
|------|--------|--------|
| PyPI project `l9-ci` provisioned | **Unknown** | Confirm the project exists / who owns it |
| PyPI Trusted Publisher for this repo + `publish.yml` + `pypi` environment | **Unknown / not configured** | Configure at pypi.org before tagging a release |
| GitHub `pypi` environment (optional approval gate) | not created here | Create in repo settings if approval is desired |

Until Trusted Publishing is configured, the publish job **fails closed** on a
tag push — it never fakes a successful publish. `workflow_dispatch` remains safe
(build + check only).

### Version / tag note

The only existing tag, `v0.1.0`, points to a commit that predates the merged
review remediations, so it is **not** a usable install ref for current `main`.
`pyproject.toml` is at `1.0.0`. The first real release should be tagged
**`v1.0.0`** (matching the pyproject version); the publish workflow enforces that
tag↔version match.
