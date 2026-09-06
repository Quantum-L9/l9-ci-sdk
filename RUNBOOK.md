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
| Core publication failure | Check artifact upload and governance digest in the `Analyze (central Core)` run | Re-dispatch the matching profile from Core `org-ci.yml` |

## Organization CI (Core)

Organization L9 analysis of this repository is executed by the GitHub
organization required-workflow ruleset from `Quantum-L9/l9-ci-core` `main`
`.github/workflows/org-ci.yml` (required check `Analyze (central Core)`).
This repository holds no Core caller, no Core SHA, and no SDK SHA; there is no
Core pin to update here. `pull_request` and `merge_group` runs are automatic.
Profile smoke tests for `nightly`, `release`, or `supply_chain` are dispatched
from Core's `org-ci.yml` `workflow_dispatch` (`event` input), not from a
workflow in this tree. See `docs/adr/0016-organization-managed-l9-ci.md`.

## Core pin update

Not applicable. A Core change reaches this repository on its next governed
`pull_request` or `merge_group` evaluation with no edit here. Rollback of a
bad Core change happens in Core (`.l9/release-plane.yaml` there), never by
restoring a consumer pin. The SDK revision Core provisions is selected by
Core's `.l9/sdk-compatibility.yaml`; promoting a new SDK revision is a
governed Core change, not an SDK-side edit.

## Evidence and manifest recovery

`MANIFEST.md` and `VALIDATION_REPORT.json` represent the earlier 158-file sealed
bundle. The current tracked inventory contains no canonical manifest generator.
Do not hand-edit generated evidence. Add or restore the authoritative generator,
then regenerate the manifest pair and validation evidence in one controlled PR.

## Incident evidence

Preserve the workflow run URL, commit SHA, profile, governance digest, SDK
revision, raw provider report, canonical bundle, agent payload, and manifest.
Never attach unredacted secrets.
