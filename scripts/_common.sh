#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

if [[ -n "${VIP_COPY_BIN:-}" ]]; then
  VIP_COPY_RUNNER=("$VIP_COPY_BIN")
elif [[ -x ".venv/bin/vip-copy" ]]; then
  VIP_COPY_RUNNER=(".venv/bin/vip-copy")
else
  VIP_COPY_RUNNER=("$PYTHON_BIN" "-m" "seers_harness.validation.runner")
fi

RUNS_ROOT="${RUNS_ROOT:-.runs}"
ENV_FILE="${ENV_FILE:-.env.local}"
TIMEOUT="${TIMEOUT:-300}"
CALL_DEADLINE="${CALL_DEADLINE:-300}"
NODE_MAX_ATTEMPTS="${NODE_MAX_ATTEMPTS:-3}"

mkdir -p "$RUNS_ROOT"

vip_copy_prepare_env_args() {
  VIP_COPY_ENV_ARGS=()
  if [[ -n "${ENV_FILE:-}" ]]; then
    if [[ ! -f "$ENV_FILE" ]]; then
      echo "Missing env file: $ENV_FILE"
      echo "Create it or run with ENV_FILE= when DEEPSEEK_API_KEY is already exported."
      exit 2
    fi
    VIP_COPY_ENV_ARGS=(--env-file "$ENV_FILE")
  fi
}

vip_copy_prepare_state_args() {
  VIP_COPY_STATE_ARGS=()
  if [[ -n "${STATE_DIR:-}" ]]; then
    VIP_COPY_STATE_ARGS=(--state-dir "$STATE_DIR")
  fi
}

vip_copy_manifest_get() {
  local manifest_path="$1"
  local dotted_key="$2"
  "$PYTHON_BIN" -c '
import json
import sys

manifest_path, dotted_key = sys.argv[1], sys.argv[2]
with open(manifest_path, "r", encoding="utf-8") as f:
    value = json.load(f)
for part in dotted_key.split("."):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break
print("" if value is None else value)
' "$manifest_path" "$dotted_key"
}

vip_copy_print_run() {
  echo
  echo "VIP COPY"
  echo "repo: $REPO_ROOT"
  echo "runner: ${VIP_COPY_RUNNER[*]}"
  echo "env_file: ${ENV_FILE:-<exported env>}"
  echo "out_dir: ${OUT_DIR:-<auto>}"
  echo
}
