# VALIDATION — CI enablement (l9-ci-sdk)

Local evidence gathered before opening the PR. Commands run from the repo root
inside a git checkout (matching CI).

## Blocking gate — pytest (with the new contract tests)

```
$ pytest -q
........................................................................  [100%]
76 passed
```

The 2 new tests in `tests/test_agent_payload_contract.py` exercise the emitter
contract end to end: `run-pipeline --emit-dir` writes `*_ci_summary.json`, and
`gate --emit-agent-payload` produces a payload carrying every top-level key
required by `l9-ci-core :: schemas/agent-review-payload.schema.json` (verified
separately to validate against that schema with `jsonschema`).

## Advisory gates (measured, not weakened)

```
$ ruff check .           -> Found 46 errors      (advisory)
$ mypy l9_ci --strict    -> Found 17 errors in 3 files (advisory)
```

These run `continue-on-error: true`. Flip to blocking only once driven to zero.

## Workflow structure

Both `pr-checks.yml` and `pr-repair.yml` parse as YAML and each has `on`,
`jobs`, `permissions`, and steps in every job (PyYAML renders `on:` as boolean
`True`; normalized before asserting).

## Secret / fork safety

- `gitguardian` and `sonar` are restricted to same-repo events and detect their
  secret; when absent they skip with a warning (cannot turn a PR red on a missing
  private-repo secret).
- No `pull_request_target`. No secrets are committed (diff grepped before push).

## Sonar config + remaining unknowns

`sonar.projectKey` and `sonar.organization` are NOT unknowns: `pr-checks.yml`
derives `projectKey` as `<owner>_<name>` (SonarCloud's GitHub import convention)
and defaults `organization` to `quantum-l9` (override via the org-level
`SONAR_ORGANIZATION` variable), passing both via action `args`.
`sonar-project.properties` is org-level only. The real remaining prerequisites
are Sonar-side project provisioning and org-token (`SONAR_TOKEN`) visibility to
this private repo; that and the PR_Repair `repository_dispatch` handler are
enumerated in MANIFEST.md.
