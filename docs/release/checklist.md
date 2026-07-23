# Semgrep Provider Release Checklist
## Contracts
- [ ] Finding bundle validates against JSON Schema.
- [ ] Semantic validation passes.
- [ ] Agent-review payload validates.
- [ ] Compatibility fixtures pass.
- [ ] Unsupported schema major versions fail.
## Fixture provenance
<!-- Harness + scaffolding landed: tests/providers/semgrep/test_runtime_fixture.py
     runs the full normalize->validate->project->gate path and SKIPS until the
     fixture at tests/fixtures/semgrep/runtime/results.json is captured. See
     tests/fixtures/semgrep/runtime/provenance.yaml for required fields. -->
- [ ] Runtime Semgrep fixture captured.
- [ ] Semgrep version recorded.
- [ ] Invocation recorded.
- [ ] Input and output checksums recorded.
- [ ] Redaction reviewed.
- [ ] Representative fixture removed or clearly separated.
## Security
- [ ] No source snippets in canonical bundle.
- [ ] No metavariable values in canonical bundle.
- [ ] No absolute paths.
- [ ] No secret-like fields.
- [ ] Environment is allowlisted.
- [ ] Diagnostic output is bounded.
## Determinism
- [ ] Two runs produce byte-identical bundles.
- [ ] Two projections produce byte-identical agent payloads.
- [ ] Generated timestamp is fixed in deterministic tests.
- [ ] Finding IDs remain stable.
- [ ] Evidence IDs remain stable.
## Operational behavior
- [ ] Timeout test passes.
- [ ] Process output limit test passes.
- [ ] Report size limit test passes.
- [ ] Finding count limit test passes.
- [ ] Evidence count limit test passes.
- [ ] Required provider failure is visible.
- [ ] Optional provider failure is visible.
## Integration
- [ ] Core example executed manually.
- [ ] SDK version is pinned.
- [ ] Semgrep version is pinned or constrained.
- [ ] Shadow artifact upload succeeds.
- [ ] Strict mode behavior is understood.
- [ ] Rollback procedure is documented.
## Promotion
- [ ] Experimental to shadow approved.
- [ ] Shadow observation period completed.
- [ ] Supported version range declared.
- [ ] Known limitations accepted.
