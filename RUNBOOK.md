<!-- L9_META
l9_schema: 1
repo: l9-ci-sdk
path: RUNBOOK.md
layer: control_plane
owner: platform
status: active
version: 1.0.0
updated: 2026-07-27
/L9_META -->
# Operations Runbook

## Local preflight

```bash
python -m pip install -r requirements-ci.txt
ruff check .
ruff format --check .
mypy l9_ci
pytest -q
PYTHONPATH=. python -m l9_ci providers list
PYTHONPATH=. python -m l9_ci providers detect --root .
```

## Failure routing

| Symptom | First action | Recovery |
|---|---|---|
| New secret finding | Stop merge, remove secret, rotate credential | Re-run self-CI on clean history |
| Ruff/format warning | Run Ruff locally | Commit mechanical fixes |
| mypy warning | Fix contract types at source | Re-run `mypy l9_ci` |
| Semgrep execution failure | Validate ruleset and raw JSON path | Re-run without swallowing execution errors |
| Bundle validation failure | Inspect schema and semantic diagnostics | Fix producer or report; never coerce PASS |
| Unresolved identity in strict mode | Add approved identity mapping or L9-authored rule metadata | Keep advisory until explicit resolution exists |
| Core publication failure | Check artifact upload, governance digest, Core pin | Re-dispatch the matching profile |

## Profile smoke tests

Each `l9-analysis*.yml` caller supports `workflow_dispatch`. Use the caller that
matches the intended profile: `pr_fast`, `merge`, `nightly`, `release`, or
`supply_chain`.

## Core pin update

1. Resolve and review the target `l9-ci-core` commit.
2. Update every literal `uses: Quantum-L9/l9-ci-core/...@<sha>` together.
3. Run all five profile callers with `workflow_dispatch`.
4. Verify artifact manifest, bundle validation, agent payload, and published check.
5. Roll back all callers to the prior SHA if any profile regresses.

## Evidence and manifest recovery

`MANIFEST.md` and `VALIDATION_REPORT.json` represent the earlier 158-file sealed
bundle. The current tracked inventory contains no canonical manifest generator.
Do not hand-edit generated evidence. Add or restore the authoritative generator,
then regenerate the manifest pair and validation evidence in one controlled PR.

## Incident evidence

Preserve the workflow run URL, commit SHA, profile, governance digest, SDK
revision, raw provider report, canonical bundle, agent payload, and manifest.
Never attach unredacted secrets.
