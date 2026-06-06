#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

# Resume an existing OUT_DIR. The script reads run_manifest.json when present
# so production users do not need to remember the original NUM_REQUESTS,
# CONCURRENCY, MAX_INFLIGHT_CALLS, or STATE_DIR values.
#
# Example:
#   bash scripts/resume.sh .runs/starter_canary_20260606T120000Z

OUT_DIR="${1:-${OUT_DIR:-}}"
if [[ -z "$OUT_DIR" ]]; then
  echo "Usage: bash scripts/resume.sh .runs/<run_id>"
  echo "Or set OUT_DIR=.runs/<run_id>."
  exit 2
fi

MANIFEST="$OUT_DIR/run_manifest.json"
if [[ -f "$MANIFEST" ]]; then
  NUM_REQUESTS="${NUM_REQUESTS:-$(vip_copy_manifest_get "$MANIFEST" "config.num_requests")}"
  CONCURRENCY="${CONCURRENCY:-$(vip_copy_manifest_get "$MANIFEST" "config.concurrency")}"
  STATE_DIR="${STATE_DIR:-$(vip_copy_manifest_get "$MANIFEST" "config.state_dir")}"
  MAX_INFLIGHT_CALLS="${MAX_INFLIGHT_CALLS:-$(vip_copy_manifest_get "$MANIFEST" "config.provider.max_inflight_calls")}"
fi

NUM_REQUESTS="${NUM_REQUESTS:-15}"
CONCURRENCY="${CONCURRENCY:-3}"
MAX_INFLIGHT_CALLS="${MAX_INFLIGHT_CALLS:-$CONCURRENCY}"

vip_copy_prepare_env_args
vip_copy_prepare_state_args
vip_copy_print_run

"${VIP_COPY_RUNNER[@]}" \
  "${VIP_COPY_ENV_ARGS[@]}" \
  --out-dir "$OUT_DIR" \
  "${VIP_COPY_STATE_ARGS[@]}" \
  --num-requests "$NUM_REQUESTS" \
  --concurrency "$CONCURRENCY" \
  --timeout "$TIMEOUT" \
  --call-deadline "$CALL_DEADLINE" \
  --max-inflight-calls "$MAX_INFLIGHT_CALLS" \
  --node-max-attempts "$NODE_MAX_ATTEMPTS" \
  --resume
