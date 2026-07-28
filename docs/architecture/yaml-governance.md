---
# YAML Governance

SDK-owned static checks for workflow YAML, governance JSON-as-YAML, Action
pins, actionlint, and zizmor. See [ADR 0010](../adr/0010-yaml-governance-static-checks.md).

## Layout

| Path | Role |
|---|---|
| `.github/workflows/l9-yaml-governance.yml` | Reusable `workflow_call` |
| `.github/workflows/l9-yaml-governance-dogfood.yml` | This repo’s dogfood caller |
| `lint/yamllint-infra.yml` | Strict infra yamllint profile |
| `lint/yamllint-data.yml` | Structural data yamllint profile |
| `lint/check_governance_json.py` | Strict JSON governance pack |
| `lint/check_action_pins.py` | SHA pins + permissions guards |
| `docs/templates/l9-yaml-governance-caller.yml` | Downstream caller template |

Tool configs live under root `lint/` (same convention as `ruff.toml`). They do
**not** live under `.github/lint/`. Workflows remain under `.github/workflows/`
because GitHub Actions requires that discovery path.

## Reusable inputs

| Input | Default | Notes |
|---|---|---|
| `infra-paths` | `.github/ .l9/ .semgrep/` | Strict yamllint |
| `data-paths` | `''` (disabled) | Dogfood sets `tests/fixtures/` |
| `config-root` | `lint` | Yamllint configs |
| `tools-root` | `lint` | Python checkers |
| `enforce-actionlint` | `true` | Fail on findings |
| `enforce-zizmor` | `true` | Dogfood sets `false` initially |

## Local validation

```bash
python3 lint/check_governance_json.py .
python3 lint/check_action_pins.py .
yamllint --strict -c lint/yamllint-infra.yml .github/ .l9/ .semgrep/
yamllint -c lint/yamllint-data.yml tests/fixtures/
pytest tests/yaml -q
```

## Downstream adoption

1. Copy `lint/` from this repository into the consumer root.
2. Copy `docs/templates/l9-yaml-governance-caller.yml` to
   `.github/workflows/l9-yaml-governance.yml`.
3. Replace the zeroed SDK SHA with a full 40-character commit that contains
   this capability.
4. Adjust `infra-paths` / `data-paths` for the consumer tree.
5. Keep `permissions: contents: read`. Do not grant `security-events: write`
   for SARIF (intentionally unsupported).

Do **not** pin `Quantum-L9/.github` or `Quantum-L9/l9-ci-core` for this
workflow.
