# Semgrep Ruleset Profiles

## Status

Active. Shipped as SDK package data at `l9_ci/rulesets/semgrep/profiles.yaml`
and resolved through `l9_ci.rulesets.semgrep`.

## What a profile is

A **profile** is a named, versioned, deterministic selection over the config
sources the packaged `l9-ci semgrep run` command composes for one language. It
lets a downstream consumer pin one profile name instead of re-deriving the
`--config` composition per repository, and keeps that selection reproducible
across SDK upgrades.

A profile chooses among **already-packaged** config sources only. It never:

- introduces a second scanner provider;
- performs SARIF projection or any GitHub upload;
- promotes a rule to blocking (rollout mode stays governed by
  `.github/governance/promotion-policy.yaml` and each rule's `metadata.mode`);
- authors or mutates rules.

## The two config sources a profile selects

For a given `--language`, one execution can compose two packaged sources:

| Selector | Config source |
|---|---|
| `include_registry_ruleset` | Community registry ruleset for the language (`p/python`, `p/typescript`). |
| `include_l9_ruleset` | SDK-packaged L9 baseline ruleset directory (`l9_ci/rulesets/semgrep/<language>/`). |

Caller-supplied `--extra-config` values are always appended after the
profile-selected sources, and `--no-registry-config` still suppresses the
registry ruleset even when the profile would include it.

## Registry contract (`profiles.yaml`)

- `schema` must equal `l9.semgrep-profiles/v1`.
- `metadata.provider_id` must equal `semgrep` (parity with the identity map).
- `metadata.version` is the registry version (major.minor.patch).
- `default_profile` must name a defined profile; it is applied when `--profile`
  is omitted and must reproduce the pre-profile default composition (registry
  ruleset + L9 ruleset), so omitting `--profile` stays backward-compatible.
- each entry under `profiles` carries a non-empty `description` and the two
  boolean selectors `include_registry_ruleset` and `include_l9_ruleset`.

Resolution fails closed: a missing registry, an unexpected schema, a
`default_profile` that is not defined, a profile missing a selector, or an
unknown `--profile` name all raise rather than silently scanning with an
unintended composition.

## Shipped profiles

| Profile | Registry ruleset | L9 ruleset | Use |
|---|---|---|---|
| `l9-standard` (default) | yes | yes | The default composition every consumer inherits; equivalent to the pre-profile behaviour. |
| `l9-baseline` | no | yes | The versioned L9 rules with no community-registry dependency. |

## Extension limits

- Add a profile by adding an entry under `profiles` and bumping
  `metadata.version`. Keep `default_profile` backward-compatible.
- Do not add selectors that reach outside the two packaged config sources
  above — a profile is a selection, not a place to introduce new providers,
  projections, or uploads (those are out of scope for this SDK surface).
- The profile registry is validated by
  `tests/rulesets/test_semgrep_ruleset_parity.py` (schema, default resolution,
  provider parity with the identity map, and authored-rule parity) and shipped
  into the wheel under test by `tests/rulesets/test_packaging.py`.

## Resolution API

`l9_ci.rulesets.semgrep` exposes:

- `default_profile_name() -> str` — the profile applied when `--profile` is
  omitted;
- `profile_names() -> tuple[str, ...]` — deterministically sorted profile
  names (used for the CLI `--profile` choices);
- `resolve_profile(name) -> SemgrepProfile` — resolve a name to its selectors,
  raising `ValueError` for an unknown profile;
- `profiles_path() -> Path` — the packaged registry path.
