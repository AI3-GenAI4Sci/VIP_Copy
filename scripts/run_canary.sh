#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

# Production canary starter.
#
# NUM_REQUESTS controls batch size; increase it for more stable aggregate
# metrics, decrease it for faster checks.
# CONCURRENCY controls parallel request pipelines.
# MAX_INFLIGHT_CALLS caps provider pressure and should respect API quota.
# STATE_DIR shares delta portfolio state across runs when long-term evolution
# is desired.
#
# Example:
#   NUM_REQUESTS=500 CONCURRENCY=50 MAX_INFLIGHT_CALLS=50 bash scripts/run_canary.sh

RUN_ID="${RUN_ID:-starter_canary_$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${OUT_DIR:-$RUNS_ROOT/$RUN_ID}"
NUM_REQUESTS="${NUM_REQUESTS:-50}"
CONCURRENCY="${CONCURRENCY:-10}"
MAX_INFLIGHT_CALLS="${MAX_INFLIGHT_CALLS:-$CONCURRENCY}"

vip_copy_prepare_env_args
vip_copy_prepare_state_args
vip_copy_print_run

REQUEST_ARGS=()
if [[ -n "${REQUEST_IDS:-}" ]]; then
  for request_id in $REQUEST_IDS; do
    REQUEST_ARGS+=(--request-id "$request_id")
  done
else
  REQUEST_ARGS=(--num-requests "$NUM_REQUESTS")
fi

"${VIP_COPY_RUNNER[@]}" \
  "${VIP_COPY_ENV_ARGS[@]}" \
  --out-dir "$OUT_DIR" \
  "${VIP_COPY_STATE_ARGS[@]}" \
  "${REQUEST_ARGS[@]}" \
  --concurrency "$CONCURRENCY" \
  --timeout "$TIMEOUT" \
  --call-deadline "$CALL_DEADLINE" \
  --max-inflight-calls "$MAX_INFLIGHT_CALLS" \
  --node-max-attempts "$NODE_MAX_ATTEMPTS"
