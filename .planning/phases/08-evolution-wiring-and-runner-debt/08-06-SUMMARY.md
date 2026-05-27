---
phase: 08-evolution-wiring-and-runner-debt
plan: 06
subsystem: evolution-trial-runner
tags: [token-cost, trial-outcome, runtime-trace, in-01]

# Dependency graph
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    plan: 08-05
    provides: runner trial loop feeds TrialOutcome back into portfolio rows
provides:
  - Tool-loop usage is aggregated into ToolLoopResult
  - WorkflowRuntime tool_loop_summary events carry usage
  - TrialOutcome.token_cost_observed is populated from runtime.trace usage totals
affects: [08-07, 08-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Usage follows the existing ProviderResult.usage → ToolLoopResult → WorkflowRuntime.trace path."
    - "TrialOutcome remains schema-stable; IN-01 only populates the existing token_cost_observed field."
    - "Missing usage remains a measured zero, with no heuristic fallback."

key-files:
  created:
    - tests/test_08_06_token_cost_observed.py
  modified:
    - seers_harness/agentic/tool_loop.py
    - seers_harness/workflow/dag_runner.py
    - seers_harness/evolution/trial_runner.py

key-decisions:
  - "Expanded the implementation from trial_runner-only to the minimal real data path, because dag_runner previously did not emit usage in runtime.trace."
  - "Kept token_cost_observed exception-path behavior unchanged; failed trials retain the dataclass default 0."
  - "Added a small tracked 08-06-specific test file rather than re-adding the ignored historical tests directory."

patterns-established:
  - "Trace-derived outcome fields should be covered by a narrow tests/test_08_06_* file when tests/ is ignored."

requirements-completed: []

# Metrics
duration: 30min
completed: 2026-05-27
---

# Phase 08 Plan 08-06: Trial Token Cost Summary

**Trial token cost is now real trace data, not a dead default: provider usage flows through the tool loop into runtime trace, and trials sum it into `TrialOutcome.token_cost_observed`.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-27T08:41:00Z
- **Completed:** 2026-05-27T09:11:00Z
- **Tasks:** 1 / 1
- **Files modified:** 4

## Accomplishments

- Added `ToolLoopResult.usage` and aggregated numeric `ProviderResult.usage` fields across successful tool-loop turns.
- Added `usage` to `WorkflowRuntime`'s `tool_loop_summary` trace event.
- Populated `TrialOutcome.token_cost_observed` from `runtime.trace[*].usage.total_tokens` on the trial success path.
- Added focused tests for:
  - tool-loop usage aggregation,
  - dag-runner trace usage emission,
  - trial outcome token-cost observation from the real trace path,
  - zero behavior when usage is missing.

## Task Commits

1. **IN-01 token-cost observation** - `96cf898` (feat)

## Files Created/Modified

- `seers_harness/agentic/tool_loop.py` - Aggregates usage into `ToolLoopResult`.
- `seers_harness/workflow/dag_runner.py` - Emits usage in `tool_loop_summary`.
- `seers_harness/evolution/trial_runner.py` - Sums trace usage into `TrialOutcome.token_cost_observed`.
- `tests/test_08_06_token_cost_observed.py` - Focused tracked tests for the full usage path.

## Decisions Made

- The plan listed only `trial_runner.py`, but the current `dag_runner.py` trace did not yet include usage. A trial-runner-only change would have passed synthetic tests while leaving real DeepSeek trials at `token_cost_observed == 0`, so the minimal upstream propagation was included.
- Kept `tool_loop.py` within its 50-80 visible-line budget by making the usage helper compact; line-budget test passes at 80 visible lines.

## Deviations from Plan

- Modified `seers_harness/agentic/tool_loop.py` and `seers_harness/workflow/dag_runner.py` in addition to `trial_runner.py`. This was necessary to avoid manufactured evidence: `runtime.trace` must carry usage before `trial_runner` can truthfully observe it.
- Test file path differs from the plan's `tests/test_trial_runner_smoke.py`; the repository does not contain that file. Because `tests/` is ignored, a narrow tracked file `tests/test_08_06_token_cost_observed.py` was added for this plan.

## Issues Encountered

- An initial full-suite run failed the `tool_loop.py` visible-line budget after adding usage aggregation. The helper was compressed without changing behavior, and the line count returned to 80.

## Verification

Commands run:

```bash
.venv/bin/python -m pytest -q tests/test_08_06_token_cost_observed.py -x
# 4 passed in 0.08s

.venv/bin/python -m pytest -q
# 291 passed in 1.05s

grep -c "token_cost_observed = sum" seers_harness/evolution/trial_runner.py
# 1

grep -c '"usage": result.usage' seers_harness/workflow/dag_runner.py
# 1

grep -c "usage=dict(usage)" seers_harness/agentic/tool_loop.py
# 1
```

## User Setup Required

None.

## Next Phase Readiness

Ready for `08-07`: M1-M5 behavioral metrics can now rely on non-default trial token-cost evidence and belief counter updates.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-27*
