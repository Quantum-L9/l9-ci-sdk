# l9-ci SDK

Reusable Python CLI for L9 CI compliance checks. The SDK owns scanner and gate logic so GitHub Actions workflows stay thin and reusable.

## Installation

The SDK is consumed by `l9-ci-core` workflows as a runtime CLI. Until it is
published to a package index, install it from this repo pinned to a commit:

```bash
python -m pip install "l9-ci @ git+https://github.com/Quantum-L9/l9-ci-sdk.git@<COMMIT_SHA>"
```

Once published, `python -m pip install l9-ci` is the target. Private-repo
installs, the publish workflow, and the version/tag policy are documented in
[docs/PUBLISHING.md](docs/PUBLISHING.md).

## Commands

```bash
l9-ci check-transport-packet .
l9-ci check-deprecated-api .
l9-ci fix-deprecated-api .
l9-ci terminology-guard . --include app --include engine --include tests
l9-ci banned-imports . --module fastapi --path-prefix engine/ --allow engine/handlers.py
l9-ci gate --result validate=success --result lint=success --result test=success --required validate,lint,test
```

## Source lineage

Harvested and normalized from Enrichment.Inference.Engine and Cognitive.Engine.Graphs. Enrichment supplied the CI chassis and gate pattern. Cognitive supplied the L9 compliance scanners.


## File Enumeration Modes

Scanner commands use a centralized Git-aware file enumerator. Default `auto` mode uses `git ls-files` when a repository is present and filesystem fallback when no Git context exists.

```bash
l9-ci check-transport-packet . --file-mode git_tracked
l9-ci check-transport-packet . --file-mode working_tree
l9-ci check-transport-packet . --file-mode filesystem
```

- `git_tracked`: deterministic CI mode; scans tracked files only.
- `working_tree`: local pre-stage mode; includes untracked non-ignored files.
- `filesystem`: fallback for bootstrap directories or archive inspection.

## Phase 4: Local-First Pipeline Runner

`l9-ci run-pipeline` runs CI stages through the SDK governance runtime. GitHub Actions should call stage-specific commands and use matrix-safe artifact paths.

```bash
l9-ci run-pipeline --stage validate --emit-dir artifacts/ci
l9-ci run-pipeline --stage test --matrix python=3.12 --emit-dir artifacts/ci
```

Matrix mode never writes to a shared `ci_summary.json` path unless the caller provides a unique matrix-specific output file.

