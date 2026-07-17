#!/usr/bin/env bash
set -euo pipefail
ROOT="${ROOT:-.}"
RAW_DIR="${RAW_DIR:-artifacts/raw/semgrep}"
L9_DIR="${L9_DIR:-artifacts/l9}"
mkdir -p "${RAW_DIR}" "${L9_DIR}"
SNAPSHOT_ID="$(git -C "${ROOT}" rev-parse HEAD)"
SDK_VERSION="$(python -c 'import importlib.metadata; print(importlib.metadata.version("l9-ci-sdk"))')"
SEMGREP_VERSION="$(semgrep --version)"
semgrep scan \
  --config "${SEMGREP_CONFIG:?SEMGREP_CONFIG is required}" \
  --json-output "${RAW_DIR}/results.json" \
  "${ROOT}"
l9-ci semgrep normalize \
  --input "${RAW_DIR}/results.json" \
  --output "${L9_DIR}/finding-bundle.json" \
  --root "${ROOT}" \
  --snapshot-id "${SNAPSHOT_ID}" \
  --revision "${SNAPSHOT_ID}" \
  --provider-version "${SEMGREP_VERSION}" \
  --identity-map .l9/semgrep-identity-map.yaml \
  --policy .github/governance/rule-modes.yaml \
  --required \
  --strict
l9-ci compatibility check \
  --bundle "${L9_DIR}/finding-bundle.json" \
  --minimum-SDK-version "${SDK_VERSION}"
l9-ci bundle validate \
  "${L9_DIR}/finding-bundle.json"
l9-ci bundle project-agent-payload \
  --input "${L9_DIR}/finding-bundle.json" \
  --output "${L9_DIR}/agent-review-payload.json" \
  --strict
