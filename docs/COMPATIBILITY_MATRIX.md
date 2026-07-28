<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: docs/COMPATIBILITY_MATRIX.md
layer: docs
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Compatibility Matrix

| Axis | Supported/current | Source |
|---|---|---|
| Python runtime | `>=3.11`; upper bound not declared | `.l9/tool-stack.yaml` |
| Self-CI default Python | `3.12` | `.github/workflows/l9-self-ci.yml` |
| SDK runtime | `1.0.0` | `l9_ci.__version__` |
| Artifact protocol | `l9.finding-bundle/v1` | `.l9/compatibility.yaml` |
| Schema version | `1.0.0` | `.l9/compatibility.yaml` |
| JSON Schema | Draft 2020-12 | `.l9/tool-stack.yaml` |
| `jsonschema` | `>=4.18,<5` | `requirements.txt` |
| `referencing` | `>=0.30,<1` | `requirements.txt` |
| `PyYAML` | `>=6,<7` | `requirements.txt` |
| Ruff | `>=0.15,<0.17`; pre-commit `v0.15.5` | CI requirements and pre-commit |
| mypy | `>=1.19` | `requirements-ci.txt` |
| pytest | `>=8,<10` | `requirements-ci.txt` |
| Core integration | Pinned commit `f7a4ee8c...` | profile workflows |
| Packaging | Source over `PYTHONPATH`; no `pyproject.toml` | runtime contract |

## Reader rules

Strict and tolerant readers both reject unsupported artifact major versions and
broken references. Tolerant readers may preserve unknown optional fields, while
strict readers reject unknown enum values and unresolved required
classifications.

## Change rules

- Removing/renaming fields requires a schema major.
- Adding enum members requires a schema minor.
- Changing identity inputs requires a schema major.
- Canonical ordering changes require compatibility review.
- Schema validation never replaces semantic validation.
