---
phase: 08-evolution-wiring-and-runner-debt
plan: 05
subsystem: validation-runner
tags: [evolution-wiring, distill, trials, portfolio, d8-f]

# Dependency graph
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    plan: 08-04
    provides: runner cleanup completed before F wiring
provides:
  - Stage 1 pass triggers distill-skill-deltas once
  - Distilled deltas assemble into the in-process delta portfolio
  - Stage 2/3 request success path trials modify_skill portfolio rows
  - Trial outcomes fold back into portfolio belief counters
affects: [08-06, 08-07, 08-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Runner evolution state starts empty and is populated only from Stage 1 trace distillation."
    - "Portfolio updates use pure transforms and write returned rows back into the active list."
    - "Unsupported or drifted delta targets skip trial without fallback seed patches."

key-files:
  created: []
  modified:
    - seers_harness/validation/runner.py
    - tests/test_validation_runner.py

key-decisions:
  - "Use the existing `DeltaDistillationArtifact.deltas` field; no compatibility shim for plan text that said proposals."
  - "Keep `ValidationError` unhandled in `_distill_after_stage1` so schema violations remain fail-fast."
  - "Do not modify `trial_runner.py` to carry portfolio delta ids; preserve its current fallback trial id contract."

patterns-established:
  - "Distill evidence is built from the canonical Stage 1 per-node evidence directory."
  - "Runner-to-trial wiring is grep-verifiable through `_distill_after_stage1`, `_patch_from_portfolio_row`, `run_request_trial`, and `update_after_trial`."

requirements-completed: []

# Metrics
duration: 24min
completed: 2026-05-27
---

# Phase 08 Plan 08-05: Evolution Wiring Summary

**Runner evolution wiring is now live: Stage 1 distills deltas from trace evidence, later stages trial portfolio rows, and observed outcomes update portfolio counters.**

## Performance

- **Duration:** ~24 min
- **Started:** 2026-05-27T08:14:00Z
- **Completed:** 2026-05-27T08:38:00Z
- **Tasks:** 3 / 3
- **Files modified:** 2

## Accomplishments

- Added `LIVE_SKILL_ROOT` and three runner helpers:
  - `_build_trajectory_payload(...)` reads Stage 1 artifacts, tool calls, and usage into the distill payload.
  - `_distill_after_stage1(...)` runs `distill-skill-deltas` via `run_skill_via_tools`, validates `DeltaDistillationArtifact`, logs firing evidence, and calls `assemble_portfolio`.
  - `_patch_from_portfolio_row(...)` converts only existing `modify_skill` rows into `SkillDeltaPatch`.
- Extended `_run_one_request(...)` with explicit `delta_portfolio` and `live_skill_root` kwargs.
- Added the post-host trial loop: each supported portfolio row runs `run_request_trial`, writes trial events into `evolution_snapshot.json`, and updates the row with `update_after_trial`.
- Extended `_run_stage(...)` and `run(...)` to pass the live portfolio and skill root through every request.
- Replaced the old `_delta_portfolio_empty` audit anchor with real empty-at-start portfolio state populated only by Stage 1 distillation.
- Updated validation-runner tests for trial firing, empty portfolio behavior, trial failure continuation, skip paths, distill success, zero-delta distill, schema fail-fast, and stage-level distill gating.

## Task Commits

1. **RED coverage: evolution wiring tests** - `f074bf2` (test)
2. **GREEN implementation: runner evolution trials** - `d5bdc1e` (feat)

## Files Created/Modified

- `seers_harness/validation/runner.py` - Adds distill helper, portfolio patching, request trial loop, and stage/run wiring.
- `tests/test_validation_runner.py` - Adds and adjusts runner evolution wiring coverage.

## Decisions Made

- Used `DeltaDistillationArtifact.deltas`, which is the actual current model field, instead of the older plan wording `proposals`.
- Wrote the returned `update_after_trial(...)` row back into `delta_portfolio[index]` because the portfolio API is intentionally pure.
- Kept non-`modify_skill` and missing-target rows as skip cases, not failures, and did not add any fallback seed delta.
- Kept `ValidationError` unwrapped at the runner boundary.

## Deviations from Plan

- The invalid-artifact test uses a monkeypatched `run_skill_via_tools` result to exercise `_distill_after_stage1` directly. The real tool handler converts invalid submit payloads into tool-loop errors before the runner sees a final artifact, so direct injection is the correct boundary test for the runner's no-catch contract.

## Issues Encountered

- The previous subagent did not produce implementation changes, so the main thread completed the GREEN work inline.
- The plan text referenced `artifact.proposals`, but the current model and tool schema use `artifact.deltas`.

## Verification

Commands run:

```bash
.venv/bin/python -m pytest -q tests/test_validation_runner.py -k "trial or distill" -x
# 7 passed, 9 deselected in 0.13s

.venv/bin/python -m pytest -q tests/test_validation_runner.py -x
# 16 passed in 0.13s

.venv/bin/python -m pytest -q
# 287 passed in 1.07s

grep -c "def _build_trajectory_payload" seers_harness/validation/runner.py
# 1

grep -c "def _distill_after_stage1" seers_harness/validation/runner.py
# 1

grep -c "def _patch_from_portfolio_row" seers_harness/validation/runner.py
# 1

grep -c "run_request_trial" seers_harness/validation/runner.py
# 2

grep -c "update_after_trial" seers_harness/validation/runner.py
# 2

grep -c "_delta_portfolio_empty" seers_harness/validation/runner.py
# 0
```

## User Setup Required

None.

## Next Phase Readiness

Ready for `08-06`: IN-01 token-cost observation, which can now build on real trial outcomes and updated portfolio counters.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-27*
