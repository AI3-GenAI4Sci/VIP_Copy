---
phase: 09-acceptance-metrics-evolution-algorithm-closure
plan: 03
subsystem: validation
tags: [runner, batch-summary, behavioral-metrics, posterior-fold, concurrency]

requires:
  - phase: 09-acceptance-metrics-evolution-algorithm-closure
    provides: exploration decisions and rubric reward journal provenance from plans 09-01 and 09-02
provides:
  - Fold-before-summary ordering so M5 reads posterior sample_count state
  - Explicit final_portfolio path from runner to batch_summary behavioral metrics
  - Stage 3 CLI run shape for 30 requests at concurrency 5
  - Tests proving concurrency stays out of exploration selection inputs
affects: [phase-09, validation-runner, batch-summary, behavioral-metrics]

tech-stack:
  added: []
  patterns: [folded posterior passed explicitly to writer layer, CLI execution overrides without exploration coupling]

key-files:
  created:
    - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-03-SUMMARY.md
  modified:
    - seers_harness/validation/runner.py
    - seers_harness/validation/batch_summary_writer.py
    - seers_harness/validation/machine_judges.py
    - tests/test_validation_runner.py
    - tests/test_08_07_behavioral_metrics.py
    - tests/test_batch_summary_writer.py

key-decisions:
  - "M5 reads folded posterior rows through final_portfolio instead of raw portfolio_journal event count."
  - "Stage request count and concurrency are explicit runner execution overrides; select_trial_delta receives only portfolio, applicable_surface, and rng."
  - "Factor count, cache, token, and merged-generation metrics remain records rather than hard acceptance gates."

patterns-established:
  - "Runner folds portfolio_journal.jsonl and applies status transitions before writing batch_summary.json."
  - "batch_summary_writer may pass folded portfolio into machine_judges while staying independent of capture-layer modules."

requirements-completed:
  - D9-EVO-03
  - D9-EVO-07
  - D9-EVO-08
  - D9-EVO-09
  - D9-MET-02
  - D9-MET-03
  - D9-MET-06
  - D9-MET-07
  - D9-GATE-01
  - D9-GATE-02
  - D9-GATE-04

duration: 10min
completed: 2026-05-29
---

# Phase 09 Plan 03: Folded Summary and Run Shape Summary

**Folded portfolio posterior state now reaches batch_summary M5, and Stage 3 can be launched as 30 requests at concurrency 5 without feeding concurrency into exploration.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-29T16:14:02Z
- **Completed:** 2026-05-29T16:23:42Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Moved journal fold and status transition ahead of `write_batch_summary`, so `behavioral_metrics.trial_belief_update_count` reads folded `sample_count`.
- Added a writer-layer `final_portfolio` path into `build_behavioral_report` without importing capture-layer modules.
- Added CLI/programmatic overrides for Stage 3 acceptance: `--num-requests 30 --concurrency 5`.
- Added tests proving concurrency remains an execution fan-out setting and is not passed into `select_trial_delta`.

## Task Commits

1. **Task 1 RED: fold-before-summary failing test** - `ed3fd31` (test)
2. **Task 1 GREEN: folded posterior summary metrics** - `37010fd` (feat)
3. **Task 2 RED: Phase 09 run-shape failing test** - `a4dac6d` (test)
4. **Task 2 GREEN: Stage 3 request/concurrency overrides** - `e39c65e` (feat)

## Files Created/Modified

- `seers_harness/validation/runner.py` - Folds journal before summary, passes folded portfolio to summary writer, and exposes request/concurrency overrides.
- `seers_harness/validation/batch_summary_writer.py` - Accepts `final_portfolio` and forwards it to behavioral report construction.
- `seers_harness/validation/machine_judges.py` - Computes M5 from folded posterior rows when provided.
- `tests/test_validation_runner.py` - Covers fold-before-summary M5 and 30-request concurrency-5 CLI run shape.
- `tests/test_08_07_behavioral_metrics.py` - Keeps behavioral metrics aligned with current merged generation evidence shape.
- `tests/test_batch_summary_writer.py` - Keeps summary helper rows aligned with current index columns.

## Decisions Made

- Chose explicit `final_portfolio` propagation over writing a new folded portfolio artifact because it is the smallest interface and preserves writer-layer separation.
- Kept `_STAGE_CONFIG` defaults intact; Phase 09 acceptance uses CLI overrides rather than rewriting historical Stage 3 defaults.
- Treated concurrency as an execution override only; source assertions confirm exploration selection does not receive concurrency, max-concurrent, or production-pressure inputs.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `tests/` is gitignored in this workspace, so plan-listed test files were staged with targeted `git add -f`. No unlisted test files were staged.
- The workspace contains many pre-existing unrelated uncommitted changes. They were left untouched; only Plan 09-03 listed files and this SUMMARY were committed.
- User explicitly instructed not to update `.planning/STATE.md` or `.planning/ROADMAP.md`; this executor left both for the orchestrator.

## Known Stubs

None. Empty lists found by the stub scan are intentional test fixtures or default empty evidence paths, not UI/rendering stubs.

## Threat Flags

None.

## Verification

- `.venv/bin/python -m pytest tests/test_validation_runner.py::test_fold_portfolio_journal_at_stage_boundary -q` -> RED failed before implementation with `trial_belief_update_count == 0`.
- `.venv/bin/python -m pytest tests/test_validation_runner.py::test_fold_portfolio_journal_at_stage_boundary tests/test_08_07_behavioral_metrics.py::test_build_behavioral_report_happy_path tests/test_batch_summary_writer.py -q` -> `4 passed`.
- `.venv/bin/python -m pytest tests/test_validation_runner.py tests/test_08_07_behavioral_metrics.py tests/test_batch_summary_writer.py -q` -> `46 passed`.
- `.venv/bin/python -m pytest tests/test_validation_runner.py::test_stage3_cli_acceptance_shape_uses_30_requests_at_concurrency_5 -q` -> RED failed before implementation on missing `--concurrency`, then on missing `num_requests` propagation; GREEN passed after implementation.
- `.venv/bin/python -m pytest tests/test_validation_runner.py -k "concurrency or num_requests or exploration" -q` -> `3 passed, 33 deselected`.
- Source assertion for `select_trial_delta` keyword args -> `['applicable_surface', 'portfolio', 'rng']`.
- `.venv/bin/python -m pytest -q` -> `390 passed in 46.84s`.

## User Setup Required

None - no external service configuration required for automated verification. Real Phase 09 acceptance still requires the planned DeepSeek run command after orchestrator scheduling:

```bash
.venv/bin/python -u -m seers_harness.validation.runner --env-file .env.local --stage 3 --num-requests 30 --concurrency 5
```

## Next Phase Readiness

Plan 09-04 can rely on `batch_summary.json.behavioral_metrics.trial_belief_update_count` reflecting folded posterior evidence rather than raw journal presence, and on the runner exposing the real acceptance run shape without exploration using concurrency as an input.

## Self-Check: PASSED

- Key production and test files exist.
- Task commits `ed3fd31`, `37010fd`, `a4dac6d`, and `e39c65e` exist.
- No tracked file deletions were introduced by Plan 09-03 task commits.
- Plan-level targeted tests and full suite passed.
- User-requested STATE/ROADMAP files were not updated by this executor.

---
*Phase: 09-acceptance-metrics-evolution-algorithm-closure*
*Completed: 2026-05-29*
