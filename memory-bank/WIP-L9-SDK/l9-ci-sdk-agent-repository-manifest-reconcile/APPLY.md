# Apply this feature branch overlay

Base repository: `Quantum-L9/l9-ci-sdk`
Base ref inspected: `bfaf4d29a775f5801e8dad932000ec8451d4217a`
Feature branch name: `agent/repository-manifest-reconcile`

Copy the overlay files into a clean checkout, then apply the edits in `EXISTING_FILE_EDITS.patch`.

```bash
unzip l9-ci-sdk-agent-repository-manifest-reconcile.zip
rsync -a l9-ci-sdk-agent-repository-manifest-reconcile/ /path/to/l9-ci-sdk/
cd /path/to/l9-ci-sdk
git apply EXISTING_FILE_EDITS.patch
python -m pytest -q tests/repository/test_manifest.py tests/commands/test_manifest.py
PYTHONPATH=. python -m l9_ci manifest generate --repository-root . --output MANIFEST.md --tracked-only
```
