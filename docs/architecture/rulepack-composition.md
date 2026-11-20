# Rulepack Composition

`compose_rulepack` resolves the effective packaged Semgrep rulepack to exact
content. It realizes `L9-CI-SDK-003` and `L9-CI-SDK-004` (ADR 0020, Proposed).

## What a composition is

The organization baseline for each selected language, plus every language and
framework pack whose selector matches, plus any product rule file the caller
is authorized to add. The result names every rule file by SHA-256, every rule
ID, and one `content_digest` over the whole.

The registry is `l9_ci/rulesets/semgrep/packs.yaml`. A rule directory that is
not registered there is never composed; a test fails if a packaged rule
directory is unregistered.

| Pack | Kind | Status | Selected by |
| --- | --- | --- | --- |
| `python-baseline` | baseline | active | language `python` |
| `typescript-baseline` | baseline | active | language `typescript` |
| `python-portable` | language | candidate | language `python`, and only with `include_candidates` |

No framework pack is registered. The mechanism accepts one (`kind: framework`,
selected by a framework name the caller takes from the capability inventory);
`docs/harvest/semgrep-donor-ledger.yaml` records why the Odoo donor rules have
not been carried in.

## What is refused

`compose_rulepack` raises `RulepackCompositionError`, and
`l9-ci semgrep compose` exits 2, for:

- a language with no baseline pack, or a framework with no pack;
- an exclusion that names a baseline rule, or a rule nothing composes;
- a product rule file that defines a rule ID a packaged rule already uses;
- two composed sources that define the same rule ID;
- a rule file that cannot be read or has no rules.

A subordinate source can add rules and can leave out a non-baseline rule. It
cannot remove or replace a baseline rule.

## Reproducibility

Packaged files and product files are pinned by content. A registry label
(`p/python`) names mutable remote content: it is recorded under
`unpinned_sources`, and the composition then reports `reproducible: false`.
The default `l9-ci semgrep run` profile includes a registry ruleset, so a run
under that profile is not content-reproducible today. This is reported, not
changed here.

## What this does not do

- It does not scan. `l9-ci semgrep run` is unchanged and still scans the
  language baseline directory selected by its profile.
- It does not decide requiredness or enforcement. Core does.
- It retires no rule at any consumer.

Schema: `l9_ci/schemas/v1/rulepack-composition.schema.json`
(`l9.semgrep-rulepack-composition/v1`).

## Harvested rules

A rule taken from a consumer carries `metadata.l9.harvest` with the donor
repository, head, path and blob, ships in a `candidate` pack in `shadow` mode,
and has an annotated `semgrep --test` fixture under
`tests/fixtures/semgrep/rules/packs/<pack>/`. Its disposition row is in
`docs/harvest/semgrep-donor-ledger.yaml`, and `validate_harvest_ledger`
refuses a row that consolidates a rule without a named central rule and both
witnesses.
