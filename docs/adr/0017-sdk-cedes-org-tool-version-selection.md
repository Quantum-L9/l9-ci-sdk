# ADR 0017: The SDK Cedes Organization Tool-Version Selection to Core
## Status
Accepted. Supersedes [ADR 0011](0011-biome-static-checks.md). Amends
[ADR 0016](0016-organization-managed-l9-ci.md): its Decision bullet listing the
`l9-biome-scan` reusable among retained repository-owned CI no longer holds.
Everything else in ADR 0016 stands.
## Context
ADR 0011 made this repository the host of a consumer-facing reusable workflow,
`.github/workflows/l9-biome-scan.yml`, that selected an exact Biome version
(`2.5.5`) and its binary checksum for every caller. Callers pinned it by SDK
SHA (`l9-biome-scan.yml@f546f122…`: Cursor-Governance
`l9-lint-test-node.yml`, and Core's frozen TypeScript preset and starter). In
effect the SDK was selecting a third-party tool version for organization CI
and rolling it out.

That is not the SDK's authority. `.l9/integration-contract.yaml` lists
"workflow permissions" and "exact provider/tool version selection" under
`Core_owns`, and prohibits "SDK selecting organization rollout policy". Core's
`.l9/architecture.yaml` prohibits "SDK owning GitHub workflow permissions or
organization rollout". The consequence was visible drift: the SDK workflow
installed Biome `2.5.5` while Core's toolchain lock, Core's TypeScript preset
`biome.json` and Cursor-Governance's `biome.json` all named `2.5.8`.

Core now owns the consumer-facing Biome check end to end (CG-TOOLCHAIN-SSOT
lane 1, Quantum-L9/l9-ci-core#212): the version is the `biome` key of Core's
`install-consumer-ci/toolchain-lock.json`, `install-biome` installs a
digest-locked binary, and `run-biome-check` runs `biome ci` from Core's
`org-ci.yml` (advisory) under the organization ruleset. There is no Core→SDK
Biome input contract.

The SDK has no Biome provider: `l9_ci/providers/` contains only Semgrep plus
the SPI and registry, `l9-biome-scan.yml` decided on the `biome ci` exit code
alone, and `AGENTS.md` forbids introducing a second provider opportunistically.
## Decision
- **(a) No consumer-facing reusable for third-party tool rollout.** The SDK
  hosts no `workflow_call` workflow that selects or installs a third-party
  tool version for other repositories. `l9-biome-scan.yml` is deleted, and so
  is its caller template `docs/templates/l9-biome-scan-caller.yml`. Consumers
  get Biome from Core's `org-ci.yml`.
- **(b) Biome is this repository's own dev toolchain**, like ruff and mypy:
  `biome.json`, the `biome-check` pre-commit hook, and an SDK self-CI job
  (`l9-biome-scan-dogfood.yml`, advisory, `contents: read`, no external
  actions, checksum-verified binary). Its version is `2.5.8`, equal to Core's
  lock, because Core's toolchain-alignment check runs in this repository too.
  `tests/biome` binds the four in-repo copies of the version together.
- **(c) Compatibility ranges are SDK facts; exact selection is Core's.**
  `DEFAULT_SEMGREP_VERSION_POLICY` (`>=1.100.0,<2.0.0`) states which Semgrep
  outputs the normalizer has been validated against and fails closed outside
  them; it stays. The exact Semgrep version for organization CI is Core's
  (`toolchain-lock.json` `semgrep`). The self-CI pin `L9_SEMGREP_VERSION` is
  repository-scoped and must lie inside the range;
  `tests/architecture/test_toolchain_pin_alignment.py` enforces that against
  the imported policy.
- **(d) Biome findings normalization is not built.** If it is ever needed it
  is a new provider (SPI, the release-policy `experimental` bar) with its own
  ADR.
- **(e) ADR 0016 amended.** ADR 0016 recorded "the `l9-yaml-governance`
  and `l9-biome-scan` reusables with their dogfood callers" as unchanged
  repository-owned CI. For Biome that is replaced by (a) and (b): the
  reusable is removed and only the self-CI job remains. The
  `l9-yaml-governance` reusable is unaffected by this ADR.
## Consequences
- Immutable caller pins (`l9-biome-scan.yml@f546f122…`) keep resolving,
  because a commit SHA never changes; they receive no further updates. `main`
  no longer offers the reusable.
- Migration order for callers: Core's `org-ci` Biome step goes live first;
  then each caller is removed (Cursor-Governance
  `.github/workflows/l9-lint-test-node.yml:50`; Core's frozen preset and
  starter are retired in Core). Removing a caller before Core's step is live
  would drop Biome coverage for that repository.
- ADR 0011 is superseded. Its record of why Biome is the JS/TS/JSON formatter
  owner stands; only the hosting and version-selection decisions change.
