# Migration from Legacy Core Normalization
## Legacy state
The prior design placed scanner parsing in Core through a broad
`normalize_findings.py` script.
That approach mixed:
- provider parsing;
- severity conversion;
- identity construction;
- policy classification;
- artifact production;
- workflow behavior.
## Target state
Provider-native reports are normalized only by `l9-ci-sdk`.
Core invokes the SDK and consumes validated artifacts.
## Migration steps
1. Keep legacy normalization active.
2. Run the SDK Semgrep path in shadow mode.
3. Compare finding counts and native rule IDs.
4. Compare path and severity normalization.
5. Review unresolved identity rates.
6. Validate agent payload projection.
7. Retain both artifacts during observation.
8. Remove Semgrep parsing from Core.
9. Keep Core responsible only for orchestration and publication.
## Rollback
Rollback requires only switching Core back to the legacy path.
Canonical artifacts from failed migration attempts should remain retained for
diagnosis.
## Explicitly not migrated
The following legacy assumptions must not be carried forward:
- provider-plus-severity rule IDs;
- implicit experimental policy keys;
- raw scanner record retention;
- malformed report equals empty findings;
- missing report equals PASS.
