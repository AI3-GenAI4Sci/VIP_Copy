---
phase: 08-evolution-wiring-and-runner-debt
plan: 03
subsystem: validation-analytics
tags: [failure-class, index-json, batch-summary, exception-classifier, d8-e]

# Dependency graph
requires:
  - phase: 07-real-llm-validation
    provides: D-19 three-label `classify(exc)` routing and stage-runner failure records
  - phase: 08-evolution-wiring-and-runner-debt
    plan: 08-01
    provides: 180s DeepSeek timeout fact now reflected by provider runtime diagnostics
provides:
  - `failure_class(exc)` seven-label operator-facing outcome classifier
  - `index.json.requests[].failure_class`
  - `batch_summary.json.by_failure_class`
  - runner success/failure records carrying `failure_class`
affects: [08-05, 08-07, 08-12, 08-13, phase-8-real-llm-batch]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Separate routing labels from analytics labels: `classify()` remains D-19 control flow, `failure_class()` is reporting."
    - "Exception analytics use a tuple dispatch table plus cause-chain walk, never message-string sniffing."
    - "Batch aggregations use dict counting so future observed labels do not require branching logic."

key-files:
  created:
    - tests/test_exception_classifier.py
    - tests/test_index_writer.py
    - tests/test_batch_summary_writer.py
  modified:
    - seers_harness/validation/exception_classifier.py
    - seers_harness/validation/runner.py
    - seers_harness/validation/index_writer.py
    - seers_harness/validation/batch_summary_writer.py
    - tests/test_validation_runner.py
    - tests/test_deepseek_rate_limit_facts.py

key-decisions:
  - "Keep `classify(exc)` unchanged as the three-label D-19 fail-fast router."
  - "Map pydantic `ValidationError` to `schema_violation` through a local `_PydanticValidationError` alias."
  - "Treat `TrialFailure` as `runner_bug` for `failure_class` because it is a routing sentinel, not one of the seven analytics categories."
  - "Default missing legacy record `failure_class` fields to `ok` in the index writer."

patterns-established:
  - "Failure records should carry both the sanitized exception string and a fixed enum analytics class."

requirements-completed: []

# Metrics
duration: 36min
completed: 2026-05-27
---

# Phase 08 Plan 08-03: Failure Class Analytics Summary

**Validation outputs now carry a fixed seven-label `failure_class` per request and aggregate those labels in `batch_summary.json`, without changing the D-19 `classify()` routing contract.**

## Performance

- **Duration:** ~36 min
- **Started:** 2026-05-27T07:21:00Z
- **Completed:** 2026-05-27T08:00:00Z
- **Tasks:** 2 / 2
- **Files modified:** 9

## Accomplishments

- Added `FailureClass` and `failure_class(exc)` to `seers_harness/validation/exception_classifier.py`.
- Implemented type-only, cause-chain-aware mapping for `ok`, `auth`, `rate_limit`, `transient`, `malformed_tool_args`, `schema_violation`, and `runner_bug`.
- Added `failure_class` to successful `_run_one_request` records and fail-fast `_run_stage` records.
- Added `failure_class` rows to `index.json`, defaulting legacy rows to `ok`.
- Added `by_failure_class` aggregation to `batch_summary.json`.
- Added tests covering classifier mapping, cause-chain walk, D-19 `classify()` contract preservation, index rows, batch aggregation, and runner record wiring.
- Fixed the stale Phase 6 timeout-fact test that still expected `60` after 08-01 legally changed the runtime fact to `180`.

## Task Commits

1. **Task 1/2 RED: failure-class coverage** - `aba391e` (test)
2. **Task 1/2 GREEN: failure-class analytics wiring** - `714fa36` (feat)
3. **Verification fix from 08-01: timeout fact expectation** - `183519e` (test)

## Files Created/Modified

- `seers_harness/validation/exception_classifier.py` - Adds `FailureClass`, `_FAILURE_CLASS_DISPATCH`, and `failure_class(exc)` beside unchanged `classify(exc)`.
- `seers_harness/validation/runner.py` - Adds `failure_class` import, success records with `"ok"`, and failure records with `failure_class(exc)`.
- `seers_harness/validation/index_writer.py` - Writes `failure_class` into every request row, defaulting to `ok`.
- `seers_harness/validation/batch_summary_writer.py` - Aggregates `by_failure_class` with dict counting.
- `tests/test_exception_classifier.py` - Covers all seven classes, cause-chain walk, and unchanged three-label routing.
- `tests/test_index_writer.py` - Covers row propagation and legacy default behavior.
- `tests/test_batch_summary_writer.py` - Covers aggregation and totals completeness.
- `tests/test_validation_runner.py` - Covers runner success and failure record wiring.
- `tests/test_deepseek_rate_limit_facts.py` - Updates stale timeout-fact expectation from 60 to 180.

## Decisions Made

- `failure_class(None) == "ok"` so success paths do not need fake exceptions.
- The analytics classifier does not call `classify()` because the two functions own different contracts.
- The classifier uses `_FAILURE_CLASS_DISPATCH` tuple entries rather than an `if/elif` taxonomy.
- Unknown exceptions return `runner_bug`, making unresolved root causes visible instead of silently disappearing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated stale timeout fact test after full-suite verification**

- **Found during:** 08-03 close-out full-suite verification.
- **Issue:** `tests/test_deepseek_rate_limit_facts.py::test_default_timeout_seconds_is_sixty` still expected `60`, contradicting 08-01's completed `_DEFAULT_TIMEOUT_SECONDS = 180` change and `deepseek_runtime_facts()` contract.
- **Fix:** Renamed the test to `test_default_timeout_seconds_is_180` and updated the assertion to `180`.
- **Files modified:** `tests/test_deepseek_rate_limit_facts.py`
- **Verification:** Full suite passes: `.venv/bin/python -m pytest -q` -> `278 passed in 1.00s`.
- **Committed in:** `183519e`

---

**Total deviations:** 1 auto-fixed (blocking stale test contract).
**Impact on plan:** No failure-class production scope creep. The fix was necessary to preserve the Phase 8 full-suite gate after 08-01.

## Issues Encountered

- The 08-03 subagent completed RED/GREEN production commits but did not return a completion signal or write `08-03-SUMMARY.md`. The orchestrator used the GSD spot-check fallback: commits were visible, tests passed, and close-out was completed in the main thread.
- The subagent left an untracked `.planning/phases/08-evolution-wiring-and-runner-debt/deferred-items.md` note about the stale timeout test. Since the issue was fixed in `183519e`, that note was not included in this plan's commits.

## Verification

Commands run:

```bash
.venv/bin/python -m pytest -q tests/test_exception_classifier.py tests/test_index_writer.py tests/test_batch_summary_writer.py tests/test_validation_runner.py -x
# 22 passed in 0.08s

.venv/bin/python -m pytest -q tests/test_deepseek_rate_limit_facts.py tests/test_provider_openai_compatible.py tests/test_exception_classifier.py tests/test_index_writer.py tests/test_batch_summary_writer.py tests/test_validation_runner.py -x
# 55 passed in 0.32s

.venv/bin/python -m pytest -q
# 278 passed in 1.00s

grep -c "def failure_class" seers_harness/validation/exception_classifier.py
# 1

grep -c "failure_class" seers_harness/validation/index_writer.py
# 2

grep -c "by_failure_class" seers_harness/validation/batch_summary_writer.py
# 3
```

## User Setup Required

None.

## Next Phase Readiness

Ready for `08-04`: runner cleanup for duplicate delimiter detection, private ContextVar reset, and provider retry kwarg visibility. `failure_class` is now available for the final Phase 8 real-LLM batch and D8-ACC-3 verification.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-27*
