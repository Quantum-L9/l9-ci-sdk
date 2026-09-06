# ADR 0016: Organization L9 CI Is Centrally Required; the SDK Owns No Core or SDK Revision
## Status
Accepted
## Context
This repository carried five thin caller workflows (`l9-analysis.yml`,
`l9-analysis-merge.yml`, `l9-analysis-release.yml`,
`l9-analysis-supply-chain.yml`, `l9-nightly.yml`), each a
`uses: Quantum-L9/l9-ci-core/.github/workflows/...@<40-hex Core SHA>`
delegation. The SDK therefore selected a Core revision for its own
organization analysis, held that revision in two different SHAs across the
callers, and needed a coordinated bump plus five `workflow_dispatch` smoke runs
(RUNBOOK "Core pin update") whenever Core changed.

`Quantum-L9/l9-ci-core` has since adopted the release-plane model
(`.l9/release-plane.yaml` there): the GitHub organization required-workflow
ruleset binds governed repositories directly to Core `main`
`.github/workflows/org-ci.yml`. The ruleset (`L9 canonical CI required`) is
active on this repository and requires the `Analyze (central Core)` check;
that check already runs on every pull request here, from Core `main`, beside
the callers. Core's contract states `workflow_copy_allowed: false`,
`core_revision_selection_allowed: false`, and
`sdk_revision_selection_allowed: false` for consumers.

The callers were described as "self-CI dogfood", but a thin caller does not
exercise the tree under review: Core provisions the SDK revision admitted in
Core's `.l9/sdk-compatibility.yaml`, which is exactly what `org-ci.yml` does.
The SDK's real in-tree dogfood is the `semgrep` job of `l9-self-ci.yml`, which
runs this checkout's own `l9-ci semgrep run` and normalization path with no
Core dependency. Removing the callers loses no coverage of the tree.

`l9-nightly.yml` additionally asked Core's nightly kernel for extended tests.
This repository defines no `tests/extended` directory and no extended test
target, so that step was a documented no-op; the full test suite already runs
on every push and pull request through `ci.yml`.

## Decision
- The five Core caller workflows are deleted. No workflow in this repository
  may reference `Quantum-L9/l9-ci-core`, `L9_CORE_REF`, or `L9_SDK_REF`, and
  no `l9-analysis*.yml` or `l9-nightly.yml` caller may return.
  `tests/architecture/test_l9_wiring.py` enforces this under the same
  `ci.yml` gate as every other architecture invariant.
- Organization analysis of this repository is the GitHub organization
  ruleset's: `Quantum-L9/l9-ci-core` `main` `.github/workflows/org-ci.yml`,
  required check `Analyze (central Core)`. A Core change reaches this
  repository on its next governed `pull_request` or `merge_group` evaluation
  with no edit here. Rollback of a bad Core change happens in Core.
- The SDK revision Core provisions is selected by Core
  (`.l9/sdk-compatibility.yaml`), never by this repository. Promoting a new
  SDK revision into the fleet remains a governed Core change.
- `.github/governance/` stays as the input set of `l9-self-ci.yml`
  (classifier, rule modes, thresholds) and as the reference shape of the Core
  governance schema. It is not a copy-in template, and its README says so.
- Repository-owned CI is unchanged: `ci.yml` (required check
  `Lint, type-check, test, coverage`), `l9-self-ci.yml`, the
  `l9-yaml-governance` and `l9-biome-scan` reusables with their dogfood
  callers, `l9-manifest-reconcile.yml`, and `publish.yml`.
- Dependabot's `github-actions` entry is retained: it manages every action
  pin, not only Core, and after this change it has no Core reference to
  propagate.

## Consequences
- Routine Core propagation requires zero work in this repository; the
  "Core pin update" runbook procedure is retired.
- Profile smoke tests for `nightly`, `release`, or `supply_chain` are
  dispatched from Core's `org-ci.yml` (`workflow_dispatch`, `event` input),
  not from a workflow here.
- Core's `docs/central-ci-bridge/CENTRAL_CI_MIGRATION_MATRIX.md` still lists
  this repository as "capability owner — self-CI, not a consumer". That row
  predates the release-plane model and rests on the dogfood reading rejected
  above; it is Core documentation to reconcile in Core, and it does not
  change the ownership recorded in `.l9/ownership.yaml`
  (`workflow_ownership: l9-ci-core`), which this ADR upholds.
- AUD-006 (`.l9/audit-findings.md`, `TODO.md`) is closed by this decision
  rather than by the artifact-handoff plan it had deferred to Core.
