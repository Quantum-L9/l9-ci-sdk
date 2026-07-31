#!/usr/bin/env bash
# AUD-008: install Active required-check ruleset for SDK self-validation on main.
#
# Zero GitHub UI. Idempotent create-or-reuse by ruleset name.
#
# Creates / updates:
#   - Tracking GitHub issue (title contains AUD-008)
#   - Active repository branch ruleset from docs/release/aud008-ruleset.json
#   - docs/release/aud008-receipt.json
#
# Receipt schema (docs/release/aud008-receipt.json):
# {
#   "schema": "l9.aud008-receipt/v1",
#   "created_at": "<ISO-8601>",
#   "updated_at": "<ISO-8601>",
#   "repo": "Quantum-L9/l9-ci-sdk",
#   "ruleset_name": "SDK self-validation required on main",
#   "required_check_context": "Lint, type-check, test, coverage",
#   "required_check_integration_id": 15368,
#   "AUD_008_ISSUE_URL": "<https://github.com/.../issues/N>",
#   "AUD_008_RULESET_URL": "<https://github.com/.../rules/<id>>",
#   "AUD_008_NEGATIVE_PROOF_URL": null | "<https://github.com/.../pull/N>",
#   "AUD_008_POSITIVE_PROOF_URL": null | "<https://github.com/.../pull/N>",
#   "negative_merge_blocked_error": null | "<stderr from gh pr merge>",
#   "ruleset_id": <int>,
#   "issue_number": <int>
# }
#
# Usage:
#   scripts/aud008_install_required_check.sh
#   scripts/aud008_install_required_check.sh --set-negative <pr-url> --merge-error-file <path>
#   scripts/aud008_install_required_check.sh --set-positive <pr-url>
#
# Env:
#   OWNER / REPO (default Quantum-L9 / l9-ci-sdk)
#   RECEIPT_PATH / RULESET_JSON (optional overrides)

set -euo pipefail

OWNER="${OWNER:-Quantum-L9}"
REPO="${REPO:-l9-ci-sdk}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULESET_JSON="${RULESET_JSON:-$ROOT/docs/release/aud008-ruleset.json}"
RECEIPT_PATH="${RECEIPT_PATH:-$ROOT/docs/release/aud008-receipt.json}"
RULESET_NAME="SDK self-validation required on main"
CHECK_CONTEXT="Lint, type-check, test, coverage"
INTEGRATION_ID=15368
ISSUE_TITLE="AUD-008: require SDK self-validation check on main"

SET_NEGATIVE=""
SET_POSITIVE=""
MERGE_ERROR_FILE=""

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --set-negative)
      SET_NEGATIVE="${2:?}"
      shift 2
      ;;
    --set-positive)
      SET_POSITIVE="${2:?}"
      shift 2
      ;;
    --merge-error-file)
      MERGE_ERROR_FILE="${2:?}"
      shift 2
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      echo "unknown arg: $1" >&2
      usage 2
      ;;
  esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 2; }; }
need gh
need jq
need python3

[[ -f "$RULESET_JSON" ]] || { echo "missing ruleset payload: $RULESET_JSON" >&2; exit 2; }

iso_now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

read_receipt() {
  if [[ -f "$RECEIPT_PATH" ]]; then
    cat "$RECEIPT_PATH"
  else
    cat <<EOF
{
  "schema": "l9.aud008-receipt/v1",
  "created_at": "$(iso_now)",
  "updated_at": "$(iso_now)",
  "repo": "${OWNER}/${REPO}",
  "ruleset_name": "${RULESET_NAME}",
  "required_check_context": "${CHECK_CONTEXT}",
  "required_check_integration_id": ${INTEGRATION_ID},
  "AUD_008_ISSUE_URL": null,
  "AUD_008_RULESET_URL": null,
  "AUD_008_NEGATIVE_PROOF_URL": null,
  "AUD_008_POSITIVE_PROOF_URL": null,
  "negative_merge_blocked_error": null,
  "ruleset_id": null,
  "issue_number": null
}
EOF
  fi
}

write_receipt_json() {
  local tmp
  tmp="$(mktemp)"
  printf '%s\n' "$1" | jq --sort-keys '.' >"$tmp"
  mv "$tmp" "$RECEIPT_PATH"
  echo "wrote $RECEIPT_PATH"
}

# --- Proof-URL update mode (no live GitHub mutation beyond receipt) ----------
if [[ -n "$SET_NEGATIVE" || -n "$SET_POSITIVE" ]]; then
  receipt="$(read_receipt)"
  updated="$(iso_now)"
  merge_err="null"
  if [[ -n "$MERGE_ERROR_FILE" ]]; then
    merge_err="$(jq -Rs '.' <"$MERGE_ERROR_FILE")"
  fi
  out="$receipt"
  out="$(jq --arg u "$updated" '.updated_at = $u' <<<"$out")"
  if [[ -n "$SET_NEGATIVE" ]]; then
    out="$(jq --arg u "$SET_NEGATIVE" '.AUD_008_NEGATIVE_PROOF_URL = $u' <<<"$out")"
    if [[ "$merge_err" != "null" ]]; then
      out="$(jq --argjson e "$merge_err" '.negative_merge_blocked_error = $e' <<<"$out")"
    fi
  fi
  if [[ -n "$SET_POSITIVE" ]]; then
    out="$(jq --arg u "$SET_POSITIVE" '.AUD_008_POSITIVE_PROOF_URL = $u' <<<"$out")"
  fi
  write_receipt_json "$out"
  exit 0
fi

# --- Validate ruleset payload against frozen AUD-008 contract ---------------
python3 - "$RULESET_JSON" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
assert data["name"] == "SDK self-validation required on main", data["name"]
assert data["enforcement"] == "active", data["enforcement"]
assert data["target"] == "branch", data["target"]
assert data["conditions"]["ref_name"]["include"] == ["refs/heads/main"], data["conditions"]
bypass = data["bypass_actors"]
assert any(a.get("actor_type") == "OrganizationAdmin" and a.get("bypass_mode") == "always" for a in bypass), bypass
rules = data["rules"]
rsc = next(r for r in rules if r["type"] == "required_status_checks")
checks = rsc["parameters"]["required_status_checks"]
assert len(checks) == 1, checks
assert checks[0]["context"] == "Lint, type-check, test, coverage", checks[0]
assert checks[0]["integration_id"] == 15368, checks[0]
print("ruleset payload OK")
PY

# --- Tracking issue (idempotent by title search) ----------------------------
existing_issue="$(
  gh issue list --repo "${OWNER}/${REPO}" --state all --search "AUD-008 in:title" --json number,title,url,state \
    --jq "[.[] | select(.title | test(\"^AUD-008\"))] | .[0] // empty"
)"
if [[ -n "$existing_issue" && "$existing_issue" != "null" ]]; then
  issue_number="$(jq -r '.number' <<<"$existing_issue")"
  issue_url="$(jq -r '.url' <<<"$existing_issue")"
  echo "reusing issue #${issue_number}: ${issue_url}"
else
  body="$(cat <<'EOF'
## AUD-008 required-check ruleset

Install an **Active** repository branch ruleset that requires the SDK
self-validation check on `main`:

- Check context (exact): `Lint, type-check, test, coverage`
- Integration: GitHub Actions (`integration_id` 15368)
- Ruleset name: `SDK self-validation required on main`
- Target: `refs/heads/main`
- Admin bypass: OrganizationAdmin / always

Automation: `scripts/aud008_install_required_check.sh` +
`docs/release/aud008-ruleset.json`.

Proofs (negative blocked merge + positive green merge) are recorded in
`docs/release/aud008-receipt.json` and later sealed into
`docs/release/evidence-map.yaml`.
EOF
)"
  issue_url="$(
    gh issue create --repo "${OWNER}/${REPO}" \
      --title "$ISSUE_TITLE" \
      --body "$body"
  )"
  issue_number="$(basename "$issue_url")"
  echo "created issue #${issue_number}: ${issue_url}"
fi

# --- Ruleset create-or-reuse by name ----------------------------------------
ruleset_list="$(gh api "repos/${OWNER}/${REPO}/rulesets")"
existing_id="$(
  jq -r --arg n "$RULESET_NAME" '.[] | select(.name == $n) | .id' <<<"$ruleset_list" | head -n1
)"

payload="$(cat "$RULESET_JSON")"
if [[ -n "$existing_id" && "$existing_id" != "null" ]]; then
  echo "updating existing ruleset id=${existing_id}"
  ruleset_resp="$(
    gh api --method PUT "repos/${OWNER}/${REPO}/rulesets/${existing_id}" \
      --input - <<<"$payload"
  )"
else
  echo "creating ruleset '${RULESET_NAME}'"
  ruleset_resp="$(
    gh api --method POST "repos/${OWNER}/${REPO}/rulesets" \
      --input - <<<"$payload"
  )"
fi

ruleset_id="$(jq -r '.id' <<<"$ruleset_resp")"
ruleset_html="$(jq -r '._links.html.href // empty' <<<"$ruleset_resp")"
if [[ -z "$ruleset_html" || "$ruleset_html" == "null" ]]; then
  # Stable HTML URL for repository rulesets
  ruleset_html="https://github.com/${OWNER}/${REPO}/rules/${ruleset_id}"
fi

enforcement="$(jq -r '.enforcement' <<<"$ruleset_resp")"
[[ "$enforcement" == "active" ]] || {
  echo "ruleset enforcement is '${enforcement}', expected active" >&2
  exit 1
}

echo "ruleset id=${ruleset_id} html=${ruleset_html} enforcement=${enforcement}"

# --- Write / merge receipt --------------------------------------------------
prev="$(read_receipt)"
created="$(jq -r '.created_at // empty' <<<"$prev")"
[[ -n "$created" && "$created" != "null" ]] || created="$(iso_now)"
neg="$(jq -r '.AUD_008_NEGATIVE_PROOF_URL // empty' <<<"$prev")"
pos="$(jq -r '.AUD_008_POSITIVE_PROOF_URL // empty' <<<"$prev")"
neg_err="$(jq -c '.negative_merge_blocked_error // null' <<<"$prev")"

receipt="$(
  jq -n \
    --arg schema "l9.aud008-receipt/v1" \
    --arg created "$created" \
    --arg updated "$(iso_now)" \
    --arg repo "${OWNER}/${REPO}" \
    --arg rname "$RULESET_NAME" \
    --arg ctx "$CHECK_CONTEXT" \
    --argjson iid "$INTEGRATION_ID" \
    --arg issue_url "$issue_url" \
    --argjson issue_number "$issue_number" \
    --arg ruleset_url "$ruleset_html" \
    --argjson ruleset_id "$ruleset_id" \
    --arg neg "${neg:-}" \
    --arg pos "${pos:-}" \
    --argjson neg_err "$neg_err" \
    '
    {
      schema: $schema,
      created_at: $created,
      updated_at: $updated,
      repo: $repo,
      ruleset_name: $rname,
      required_check_context: $ctx,
      required_check_integration_id: $iid,
      AUD_008_ISSUE_URL: $issue_url,
      AUD_008_RULESET_URL: $ruleset_url,
      AUD_008_NEGATIVE_PROOF_URL: (if $neg == "" then null else $neg end),
      AUD_008_POSITIVE_PROOF_URL: (if $pos == "" then null else $pos end),
      negative_merge_blocked_error: $neg_err,
      ruleset_id: $ruleset_id,
      issue_number: $issue_number
    }
    '
)"

write_receipt_json "$receipt"
echo "AUD-008 install complete"
