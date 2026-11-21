# Central finding waivers (`l9.finding-waivers/v1`)

Status: CTO decision 2026-11-21 (lane L1-CANARY-FIXES). Required rules accept no
inline `nosemgrep` and no consumer `.semgrepignore` (#128). A required finding
is waived only by a central ledger entry. Before this, Core's
`defaults/waivers.yaml` (`l9.waivers/v1`) validated only consumer `waiver_refs`
pointers, and `gate evaluate` took no waiver input, so no waiver could reach
the gate.

## Ledger

```yaml
schema: l9.finding-waivers/v1
waivers:
  - id: SDK-PROVIDER-SUBPROCESS-REQUEST-NAME
    owner: L1/SDK
    reason: ...
    created: 2026-11-21
    expires: 2027-02-21
    scope:
      repository: Quantum-L9/l9-ci-sdk
      provider_id: semgrep
      provider_rule_id: python.django.security.injection.command.subprocess-injection.subprocess-injection
      path: l9_ci/providers/semgrep/provider.py
    fingerprint: f65ae3b056b2c34fdec05fa7b48591263a961da1b449dc86bd31491a14329b40
```

Schema: [`finding-waivers.schema.json`](../../l9_ci/schemas/v1/finding-waivers.schema.json).
Loader and matcher: `l9_ci/policy/waivers.py`.

## Semantics

- **One finding.** An entry matches only a finding whose repository, provider,
  provider rule ID, primary path and `Finding.fingerprint` all equal the
  entry's. The fingerprint covers the exact span and the provider
  discriminator, so a change to the waived code makes a new finding and the
  waiver stops matching it.
- **Expiry.** An entry applies from `created` through `expires` inclusive.
  Outside that window it applies to nothing. The finding keeps its policy
  classification, and the bundle's `limitations` record the expired or
  not-yet-in-force entry. An active entry that matched nothing is also
  recorded.
- **Effect.** Only a `blocking` classification changes: its mode becomes
  `advisory` and `waiver_id` names the entry. Policy key, version and
  resolution status are kept.
- **Central only.** The ledger comes from `--waivers` on every `l9-ci semgrep`
  command that classifies findings (`run`, `normalize`), together with
  `--repository <owner>/<name>` and an optional `--waiver-date`. A ledger
  inside `--root` is refused, so a consumer cannot waive its own findings.
- **Fail closed.** A malformed entry refuses the whole ledger and the run
  fails. No partially read ledger ever applies.

Witnesses: `tests/policy/test_finding_waivers.py`. Its fixture is the real
finding Core reported on SDK #135, run 44843278484.

## Core change

1. Add the ledger next to `semgrep-policy.yaml`
   (`.github/actions/resolve-governance/finding-waivers.yaml`) with the first
   entry above.
2. Stage it with the policy and pass
   `--waivers <staged ledger> --repository "${GITHUB_REPOSITORY}"` to every
   `l9-ci semgrep run`, both the primary instance and the required instances.
3. Promote the SDK revision that contains this change.
