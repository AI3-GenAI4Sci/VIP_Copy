---
phase: 08-evolution-wiring-and-runner-debt
plan: 07
subsystem: validation-metrics
tags: [behavioral-metrics, m1-m5, batch-summary, acceptance]

# Dependency graph
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    plan: 08-06
    provides: trial token cost and portfolio update inputs available
provides:
  - M1-M5 behavioral metric compute functions
  - build_behavioral_report(stage_dir) aggregator
  - batch_summary.json.behavioral_metrics top-level field
affects: [08-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Behavioral metrics are pure writer-layer computations over index/evidence/snapshot files."
    - "Missing metric evidence returns explicit defaults rather than raising or inventing data."
    - "Tracked plan-specific tests live in tests/test_08_07_behavioral_metrics.py because tests/ is ignored."

key-files:
  created:
    - tests/test_08_07_behavioral_metrics.py
  modified:
    - seers_harness/validation/machine_judges.py
    - seers_harness/validation/batch_summary_writer.py

key-decisions:
  - "Use codepoint-level token sets for factor-diversity text Jaccard, matching the existing CJK-safe overlap rule."
  - "Treat missing factor artifacts as missing evidence, not underspecified requests, so M3b returns the documented trivial 1.0 when no underspec population exists."
  - "Do not fabricate portfolio rows for M4/M5 when snapshots lack row details; default values surface the evidence gap."

patterns-established:
  - "batch_summary_writer may import machine_judges writer-layer aggregators, while capture-layer modules remain untouched."

requirements-completed: []

# Metrics
duration: 28min
completed: 2026-05-27
---

# Phase 08 Plan 08-07: Behavioral Metrics Summary

**M1-M5 behavioral acceptance metrics are now emitted in `batch_summary.json` under `behavioral_metrics`.**

## Performance

- **Duration:** ~28 min
- **Started:** 2026-05-27T09:22:00Z
- **Completed:** 2026-05-27T09:50:00Z
- **Tasks:** 3 / 3
- **Files modified:** 3

## Accomplishments

- Added compute functions in `machine_judges.py`:
  - `compute_factor_count_p50`
  - `compute_factor_diversity`
  - `compute_copy_candidate_count_p50`
  - `compute_reflection_trigger_rate`
  - `compute_delta_diversity`
  - `compute_belief_update_count`
- Added `build_behavioral_report(stage_dir)` to aggregate M1-M5 from `index.json`, per-request evidence artifacts, tool-call JSONL, and evolution snapshots.
- Added `batch_summary_writer` integration so every `batch_summary.json` has a top-level `behavioral_metrics` dict.
- Added focused tracked coverage in `tests/test_08_07_behavioral_metrics.py`.

## Task Commits

1. **M1-M5 behavioral metrics** - `634aae9` (feat)

## Files Created/Modified

- `seers_harness/validation/machine_judges.py` - Adds metric compute functions and aggregator.
- `seers_harness/validation/batch_summary_writer.py` - Emits `behavioral_metrics`.
- `tests/test_08_07_behavioral_metrics.py` - Covers M1-M5, missing-evidence defaults, and writer integration.

## Decisions Made

- The aggregator skips missing evidence and returns explicit defaults; it does not raise or estimate.
- `compute_reflection_trigger_rate([])` returns `1.0` per the plan's "0 underspec -> trivially pass" rule.
- M4/M5 consume portfolio-row details when snapshots contain `portfolio`, `final_portfolio`, or `delta_portfolio`. If only `delta_portfolio_after` ids are present, M4 can count ids but cannot claim target/change-type diversity.

## Deviations from Plan

- The plan referenced `tests/test_machine_judges.py`, but `tests/` is mostly ignored and only a small subset is tracked. Added a narrow tracked test file instead of re-adding historical ignored tests.
- Current `evolution_snapshot.json` reducer does not persist full portfolio rows. This plan does not invent them; real batch M4/M5 may still expose a gap unless a later plan persists portfolio details.

## Issues Encountered

- Initial missing-evidence test expected M3b `0.0`; corrected to the documented `1.0` trivial-pass behavior when there are no underspecified requests to evaluate.

## Verification

Commands run:

```bash
.venv/bin/python -m pytest -q tests/test_08_07_behavioral_metrics.py -x
# 8 passed in 0.04s

.venv/bin/python -m pytest -q tests/test_batch_summary_writer.py tests/test_08_07_behavioral_metrics.py -x
# 10 passed in 0.04s

.venv/bin/python -m pytest -q
# 299 passed in 1.08s

grep -c "def compute_factor_count_p50\\|def compute_factor_diversity\\|def compute_copy_candidate_count_p50\\|def compute_reflection_trigger_rate\\|def compute_delta_diversity\\|def compute_belief_update_count\\|def build_behavioral_report" seers_harness/validation/machine_judges.py
# 7

grep -c "behavioral_metrics" seers_harness/validation/batch_summary_writer.py
# 1
```

## User Setup Required

None.

## Next Phase Readiness

Ready for `08-08`: transient retry/backoff. Behavioral metrics are now present in summaries, but final phase acceptance still needs real batch evidence for M1-M5.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-27*
