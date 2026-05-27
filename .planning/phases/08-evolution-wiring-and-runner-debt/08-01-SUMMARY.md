---
phase: 08-evolution-wiring-and-runner-debt
plan: 01
subsystem: provider-runtime
tags: [deepseek, timeout, provider, real-llm-hardening, d8-a]

# Dependency graph
requires:
  - phase: 07-real-llm-validation
    provides: 2026-05-26 real-LLM root-cause evidence that 60s DeepSeek timeout prematurely killed reasoning-model requests
provides:
  - DeepSeek provider default timeout raised to 180s through a single module-level constant
  - Runtime facts now report the same default timeout source used by provider construction
  - Unit coverage for default timeout, runtime facts, and env override behavior
affects: [08-02, 08-03, 08-12, 08-13, phase-7-real-llm-rerun]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Provider runtime defaults are represented by a single module-level constant and reused by diagnostics"

key-files:
  created:
    - tests/test_provider_openai_compatible.py
  modified:
    - seers_harness/provider_runtime/openai_compatible.py

key-decisions:
  - "Use `_DEFAULT_TIMEOUT_SECONDS = 180` as the single source of truth for both `deepseek_provider_from_env()` and `deepseek_runtime_facts()`."
  - "Leave SDK `max_retries` and parse-retry behavior unchanged; this plan only changes the HTTP response timeout default."
  - "Use the project `.venv` Python for pytest; the system Python 3.13 pytest entrypoint segfaults during pytest capture initialization before project tests load."

patterns-established:
  - "D8-A provider default changes must be proven both through constructed client kwargs and runtime fact reporting."

requirements-completed: []

# Metrics
duration: 18min
completed: 2026-05-27
---

# Phase 08 Plan 08-01: DeepSeek Timeout Default Summary

**DeepSeek provider construction and runtime diagnostics now share a 180s default timeout, preserving env overrides and leaving SDK retry behavior untouched.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-27T06:45:59Z
- **Completed:** 2026-05-27T07:03:22Z
- **Tasks:** 1 / 1
- **Files modified:** 2

## Accomplishments

- Added `_DEFAULT_TIMEOUT_SECONDS = 180` in `seers_harness/provider_runtime/openai_compatible.py`.
- Updated `deepseek_runtime_facts()["default_timeout_seconds"]` to read the same constant.
- Updated `deepseek_provider_from_env()` so unset `DEEPSEEK_TIMEOUT_SECONDS` constructs the OpenAI client with `timeout=180.0`.
- Added tests covering the 180s default, runtime facts, and env override behavior.

## Task Commits

1. **Task 1 RED: default-timeout tests** - `4fa4164` (test)
2. **Task 1 GREEN: 180s provider default** - `de8536c` (feat)

## Files Created/Modified

- `seers_harness/provider_runtime/openai_compatible.py` - Adds the timeout default constant and reuses it in provider construction plus runtime facts.
- `tests/test_provider_openai_compatible.py` - Adds coverage for default timeout 180s, runtime facts 180s, and `DEEPSEEK_TIMEOUT_SECONDS` override.

## Decisions Made

- Kept the env override path intact: `DEEPSEEK_TIMEOUT_SECONDS=240` still yields `timeout=240.0`.
- Did not alter `DEEPSEEK_SDK_MAX_RETRIES`, `max_retries`, parse retries, or any connect-timeout behavior.
- Used `.venv/bin/python -m pytest` for verification because `/opt/miniconda3/bin/python -m pytest` segfaulted in pytest startup before project collection.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The system Python 3.13 pytest entrypoint exited 139 while importing pytest capture support, before loading project tests. Root cause was isolated to the test runner environment, not the provider code. The project `.venv` uses Python 3.12.12 and pytest 9.0.3; it produced the expected RED failure (`60.0 == 180.0`) and then the GREEN pass.
- `tests/` is ignored by `.gitignore`; the plan explicitly required adding tests, so `tests/test_provider_openai_compatible.py` was added with `git add -f`.

## Verification

Commands run:

```bash
.venv/bin/python -m pytest -q tests/test_provider_openai_compatible.py -x
# 19 passed in 0.24s

grep -c "_DEFAULT_TIMEOUT_SECONDS" seers_harness/provider_runtime/openai_compatible.py
# 3

grep -c '"60"' seers_harness/provider_runtime/openai_compatible.py
# 0

grep -n -E 'default_timeout_seconds.*60|SDK_MAX_RETRIES|max_retries|connect' seers_harness/provider_runtime/openai_compatible.py
# only existing max_retries / SDK_MAX_RETRIES lines; no timeout 60 or connect-timeout changes
```

## User Setup Required

None.

## Next Phase Readiness

Ready for `08-02`: runner `--env-file` support. The provider can now survive DeepSeek reasoning-model TTFB above 60 seconds unless the operator explicitly overrides the timeout lower.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-27*
