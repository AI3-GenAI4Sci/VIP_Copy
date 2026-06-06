#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

# Small production starter.
#
# NUM_REQUESTS controls how many request_id slots enter this run.
# CONCURRENCY controls how many request pipelines run in parallel.
# MAX_INFLIGHT_CALLS caps provider API calls across all pipelines; keep it
# near CONCURRENCY unless your provider quota is higher.
# STATE_DIR optionally points to shared evolution memory across runs.
#
# Example:
#   NUM_REQUESTS=30 CONCURRENCY=5 bash scripts/run_quick.sh

RUN_ID="${RUN_ID:-starter_small_$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${OUT_DIR:-$RUNS_ROOT/$RUN_ID}"
NUM_REQUESTS="${NUM_REQUESTS:-15}"
CONCURRENCY="${CONCURRENCY:-3}"
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
