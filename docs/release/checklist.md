# Semgrep Provider Release Checklist

Path A = SDK contract freeze (`l9-ci` 1.0.0, Semgrep **experimental**).  
Path B = shadow observation → `supported` (out of Path A tag scope).

## Contracts

- [x] Finding bundle validates against JSON Schema.  
  Cite: `make check` / `tests/` artifact + schema suites; `l9_ci/schemas/v1/`
- [x] Semantic validation passes.  
  Cite: `l9_ci/artifacts` validator tests under `tests/`
- [x] Agent-review payload validates.  
  Cite: projection tests / `l9.agent-review-projection/v1`
- [x] Compatibility fixtures pass.  
  Cite: `tests/compatibility/`
- [x] Unsupported schema major versions fail.  
  Cite: compatibility fixtures + `.l9/compatibility.yaml`

## Fixture provenance

<!-- Runtime fixture present at tests/fixtures/semgrep/runtime/results.json.
     tests/providers/semgrep/test_runtime_fixture.py runs normalize→validate→
     project→gate and skips ONLY if the fixture file is removed. -->
- [x] Runtime Semgrep fixture captured.  
  Cite: `tests/fixtures/semgrep/runtime/results.json`
- [x] Semgrep version recorded.  
  Cite: `tests/fixtures/semgrep/runtime/provenance.yaml` (`semgrep_version`)
- [x] Invocation recorded.  
  Cite: provenance `command` / `ruleset` / capture environment
- [x] Input and output checksums recorded.  
  Cite: provenance `input_checksum` / `output_checksum`;
  `test_runtime_fixture_checksum_matches_provenance`
- [x] Redaction reviewed.  
  Cite: provenance `redaction` block + redaction validator on pipeline output
- [x] Representative fixture removed or clearly separated.  
  Cite: unit fixtures remain under `tests/fixtures/semgrep/`; runtime under `runtime/`

## Security

- [x] No source snippets in canonical bundle.  
  Cite: redaction tests / `l9_ci.integration` redaction validation
- [x] No metavariable values in canonical bundle.  
  Cite: same
- [x] No absolute paths.  
  Cite: path normalization + redaction tests
- [x] No secret-like fields.  
  Cite: redaction + gitleaks self-CI
- [x] Environment is allowlisted.  
  Cite: operational limits / execution env handling tests
- [x] Diagnostic output is bounded.  
  Cite: operational limit tests

## Determinism

- [x] Two runs produce byte-identical bundles.  
  Cite: determinism tests (`generated_at` fixed in tests; digest excludes volatile fields per architecture)
- [x] Two projections produce byte-identical agent payloads.  
  Cite: projection determinism tests
- [x] Generated timestamp is fixed in deterministic tests.  
  Cite: determinism test helpers
- [x] Finding IDs remain stable.  
  Cite: identity / finding ID tests
- [x] Evidence IDs remain stable.  
  Cite: evidence ID tests

## Operational behavior

- [x] Timeout test passes.  
  Cite: pipeline / execution timeout tests
- [x] Process output limit test passes.  
  Cite: operational limits tests
- [x] Report size limit test passes.  
  Cite: operational limits tests
- [x] Finding count limit test passes.  
  Cite: operational limits tests
- [x] Evidence count limit test passes.  
  Cite: operational limits tests
- [x] Required provider failure is visible.  
  Cite: gate evaluator matrix / STACK-006 tests
- [x] Optional provider failure is visible.  
  Cite: gate / provider failure tests

## Integration

- [x] Core example executed manually.  
  Path A note (2026-07-31): waived for automated Path A — recipe remains
  `docs/examples/core-semgrep-integration.sh`; tip dogfood is thin-caller
  L9 Analysis (merge) https://github.com/Quantum-L9/l9-ci-sdk/actions/runs/30640182783
- [x] SDK version is pinned.  
  Cite: triad `1.0.0` in `l9_ci.__version__` / `pyproject.toml` / integration-contract
- [x] Semgrep version is pinned or constrained.  
  Cite: `>=1.100.0,<2.0.0` + caller `semgrep-version: "1.171.0"`
- [ ] Shadow artifact upload succeeds.  
  **Path B** — not required for Path A tag
- [x] Strict mode behavior is understood.  
  Cite: gate evaluator + dogfood `strict: false` advisory posture documented in AGENTS
- [x] Rollback procedure is documented.  
  Cite: `docs/PUBLISHING.md` + Core pin rollback = revert thin-caller SHA

## Promotion

- [ ] Experimental to shadow approved. — **Path B**
- [ ] Shadow observation period completed. — **Path B**
- [ ] Supported version range declared. — range already enforced in code; **lifecycle** promotion is Path B
- [ ] Known limitations accepted. — Path A: `docs/release/known-limitations.md` refreshed; formal supported acceptance is Path B
