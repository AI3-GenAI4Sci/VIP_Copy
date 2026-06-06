#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

# Large offline pressure-run template.
#
# NUM_REQUESTS controls total production slots.
# CONCURRENCY controls parallel request pipelines.
# MAX_INFLIGHT_CALLS controls provider pressure; set it below or equal to
# your real provider quota to reduce rate-limit retries.
# STATE_DIR defaults to a shared evolution state directory so positive delta
# evidence can accumulate across large runs.
#
# Example:
#   CONFIRM_LARGE=1 NUM_REQUESTS=1000000 CONCURRENCY=50 bash scripts/run_large_template.sh

if [[ "${CONFIRM_LARGE:-}" != "1" ]]; then
  echo "This script starts a large offline pressure run."
  echo "Set CONFIRM_LARGE=1 to continue."
  echo
  echo "Example:"
  echo "  CONFIRM_LARGE=1 bash scripts/run_large_template.sh"
  exit 2
fi

RUN_ID="${RUN_ID:-million_$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${OUT_DIR:-$RUNS_ROOT/$RUN_ID}"
STATE_DIR="${STATE_DIR:-$RUNS_ROOT/vip_copy_evolution_state}"
NUM_REQUESTS="${NUM_REQUESTS:-1000000}"
CONCURRENCY="${CONCURRENCY:-50}"
MAX_INFLIGHT_CALLS="${MAX_INFLIGHT_CALLS:-50}"

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
  --node-max-attempts "$NODE_MAX_ATTEMPTS"
