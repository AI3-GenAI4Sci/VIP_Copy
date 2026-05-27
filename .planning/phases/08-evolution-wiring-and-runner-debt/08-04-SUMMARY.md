---
phase: 08-evolution-wiring-and-runner-debt
plan: 04
subsystem: validation-runner
tags: [runner-cleanup, delimiter, contextvar, max-retries, wr-03, wr-04, in-08]

# Dependency graph
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    plan: 08-03
    provides: runner failure-class wiring now present before runner cleanup
provides:
  - Runner CSV delimiter detection uses the canonical intake helper
  - Runner current-node cleanup uses public `reset_current_node_id(token)`
  - Provider retry budget is visible as `_RUNNER_PROVIDER_MAX_RETRIES`
affects: [08-05, 08-09, 08-10, 08-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Runner should call public helper APIs instead of private module state."
    - "Audit-sensitive constants should be explicit rather than hidden behind string construction."

key-files:
  created: []
  modified:
    - seers_harness/validation/runner.py

key-decisions:
  - "Remove the duplicate runner-local `_detect_delimiter` helper and use `request_preprocessor.detect_delimiter`."
  - "Keep the existing finally reset try/except semantics unchanged; only swap the private ContextVar access for the public helper."
  - "Represent the provider SDK retry budget with `_RUNNER_PROVIDER_MAX_RETRIES: int = 3` and pass it directly to `deepseek_provider_from_env`."

patterns-established:
  - "Pure runner cleanup plans should be grep-verifiable with no behavior expansion."

requirements-completed: []

# Metrics
duration: 14min
completed: 2026-05-27
---

# Phase 08 Plan 08-04: Runner Wiring Debt Cleanup Summary

**Runner cleanup removed three pre-F wiring hazards: duplicate delimiter logic, private ContextVar reset access, and scan-evasive provider retry kwargs.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-05-27T08:00:00Z
- **Completed:** 2026-05-27T08:14:00Z
- **Tasks:** 3 / 3
- **Files modified:** 1

## Accomplishments

- Replaced `_build_scratch_csv`'s runner-local `_detect_delimiter(csv_path)` call with canonical `detect_delimiter(csv_path)` from `seers_harness.intake.request_preprocessor`.
- Deleted the duplicate `_detect_delimiter` helper from `runner.py`.
- Replaced private `_current_node_id as _cv` reset access with public `reset_current_node_id(token)`.
- Removed `_PROVIDER_BUDGET_KEY` and `"max_" + "retries"` string assembly.
- Added `_RUNNER_PROVIDER_MAX_RETRIES: int = 3` and passed it explicitly to `deepseek_provider_from_env(max_retries=_RUNNER_PROVIDER_MAX_RETRIES)`.

## Task Commits

1. **Tasks 1-3: runner cleanup sweep** - `d5af9ff` (refactor)

## Files Created/Modified

- `seers_harness/validation/runner.py` - Deletes duplicate helper, uses public reset helper, and makes the provider retry budget audit-visible.

## Decisions Made

- Kept the existing `try/except Exception: pass` around context reset exactly as planned; 08-10 owns later cleanup/finally behavior.
- Did not change provider retry semantics. The value remains 3 and still applies only to the provider SDK call.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The 08-04 subagent completed the production commit but did not return a completion signal or write `08-04-SUMMARY.md`. The orchestrator used spot-check fallback: commit was visible, grep gates passed, and close-out was completed in the main thread.

## Verification

Commands run:

```bash
.venv/bin/python -m pytest -q tests/test_validation_runner.py -x
# 7 passed in 0.09s

.venv/bin/python -m pytest -q
# 278 passed in 1.02s

grep -c "_detect_delimiter" seers_harness/validation/runner.py
# 0

grep -c "detect_delimiter(csv_path)" seers_harness/validation/runner.py
# 1

grep -c "_current_node_id as _cv" seers_harness/validation/runner.py
# 0

grep -c "reset_current_node_id(token)" seers_harness/validation/runner.py
# 1

grep -c "_PROVIDER_BUDGET_KEY" seers_harness/validation/runner.py
# 0

grep -c '"max_" + "retries"' seers_harness/validation/runner.py
# 0

grep -c "deepseek_provider_from_env(max_retries=_RUNNER_PROVIDER_MAX_RETRIES)" seers_harness/validation/runner.py
# 1

grep -c "_RUNNER_PROVIDER_MAX_RETRIES" seers_harness/validation/runner.py
# 2
```

## User Setup Required

None.

## Next Phase Readiness

Ready for `08-05`: runner-to-evolution wiring. The runner file is cleaner before the larger F connection work starts.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-27*
