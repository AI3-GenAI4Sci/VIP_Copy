---
phase: 08-evolution-wiring-and-runner-debt
plan: G4
subsystem: evolution-bandit + validation-runner
tags: [bandit, paired-control, journal, status-machine, trial-signal, F-08-D]
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    plan: G3
    provides: valid target_skill paths, observable skipped trials, and distill evidence
  - phase: 06-evolution-chain-production-hardening
    plan: 06-02
    provides: select_trial_delta, belief_mean, update_after_trial, trajectory helpers
provides:
  - ProductionSignalWindow baseline-only rolling signal source
  - TrialUplift paired-control evaluator decoupled from raw rubric score
  - append-only portfolio_journal.jsonl plus fold_portfolio_journal
  - Wilson-LCB status transitions through apply_status_transitions
  - run_request_baseline paired-control helper
  - runner.py trial gate using select_trial_delta, baseline + trial pairing, journal append, stage-boundary fold
affects:
  - 08-G5
  - Stage 3 real-LLM acceptance evidence
tech-stack:
  added: [collections.deque, threading.Lock, pydantic BaseModel, math]
  patterns:
    - "baseline-only signal window; trial outcomes never feed trial pressure"
    - "journal-then-fold portfolio updates, no mid-request direct mutation"
    - "paired control runs baseline before patched trial on the same scenario"
key-files:
  created:
    - seers_harness/evolution/trial_signal.py
    - seers_harness/evolution/uplift.py
    - seers_harness/evolution/portfolio_journal.py
    - seers_harness/evolution/status_machine.py
    - tests/test_trial_signal.py
    - tests/test_uplift.py
    - tests/test_portfolio_journal.py
    - tests/test_status_machine.py
    - tests/test_trial_runner_baseline.py
  modified:
    - seers_harness/evolution/trial_runner.py
    - seers_harness/validation/runner.py
    - tests/test_validation_runner.py
key-decisions:
  - "Do not modify seers_harness/evolution/delta_portfolio.py; 06-02 functions are wired through as-is."
  - "Production pressure excludes the current request from the in-flight count, so serial stages do not self-suppress trials."
  - "run_request_trial failure writes a negative journal entry; portfolio mutation still waits for stage-boundary fold."
  - "Status-machine token-cost p95 accepts per-delta journal token deltas when available and falls back to average only when no distribution is supplied."
patterns-established:
  - "Selection is read-only over the current portfolio; mutation happens only via append-only journal plus single-thread fold."
  - "Runner tests should validate journal entries for request-level trial outcomes and folded portfolio counts for stage-level effects."
requirements-completed: []
metrics:
  duration: 70min
  completed: 2026-05-28T04:58:00Z
  tests_added: 26
  tests_total: 377
---

# Phase 08 Plan G4: Bandit Wiring Summary

**The runner now uses runtime-observable trial signals, `select_trial_delta`, paired baseline/trial control, append-only journal updates, and Wilson-LCB status transitions.**

## Performance

- **Duration:** ~70 min
- **Completed:** 2026-05-28T04:58:00Z
- **Tests added:** 26
- **Full suite:** 377 passed

## Accomplishments

- Added `ProductionSignalWindow` with thread-safe baseline-only rolling outcomes and `concurrency_pressure`.
- Added `TrialUplift` / `compute_uplift` for paired baseline/trial comparisons.
- Added `PortfolioJournalEntry`, `append_journal_entry`, `read_journal_entries`, and `fold_portfolio_journal`.
- Added `wilson_lcb` and `apply_status_transitions`.
- Added `run_request_baseline` as the no-patch paired-control path.
- Replaced runner’s deterministic “try every portfolio row” loop with:
  - `select_trial_delta(...)`
  - `_patch_from_portfolio_row(...)`
  - `run_request_baseline(...)`
  - `run_request_trial(...)`
  - `compute_uplift(...)`
  - `append_journal_entry(...)`
  - stage-boundary `fold_portfolio_journal(...)` + `apply_status_transitions(...)`

## Task Commits

- `ca1ea21` — recovery commit containing G4 bandit/journal/status wiring, paired-control trial path, Stage3-only bootstrap recovery, usage evidence aggregation, and tests.

## Files Created/Modified

- `seers_harness/evolution/trial_signal.py` — real-source pressure signals.
- `seers_harness/evolution/uplift.py` — paired-control uplift decision.
- `seers_harness/evolution/portfolio_journal.py` — append-only journal and fold reducer.
- `seers_harness/evolution/status_machine.py` — Wilson-LCB status transitions.
- `seers_harness/evolution/trial_runner.py` — `run_request_baseline`.
- `seers_harness/validation/runner.py` — trial gate, paired control, journal append, fold/status at stage boundary.
- New tests for each module plus runner integration updates.

## Deviations from Plan

- `status_machine` supports optional `token_cost_deltas_by_delta` for real p95 from journal entries. When no distribution is available, it falls back to average token delta from the row, because `DeltaPortfolioRow` does not store per-trial token deltas.
- `run_request_trial` failures now produce negative journal entries instead of direct portfolio mutation. This is intentional journal-then-fold behavior and supersedes older deterministic-loop assertions.
- `nodes=[]` test seams use portfolio `applicable_surface` as a fallback; production paths still use actual node `skill_name`/`id`.

## Verification

```bash
.venv/bin/python -m pytest tests/test_trial_signal.py tests/test_uplift.py tests/test_portfolio_journal.py tests/test_status_machine.py tests/test_trial_runner_baseline.py tests/test_trial_runner.py tests/test_delta_portfolio.py tests/test_validation_runner.py -q
# 79 passed in 0.65s

grep -c "select_trial_delta(" seers_harness/validation/runner.py
grep -c "run_request_baseline(" seers_harness/validation/runner.py
grep -c "append_journal_entry(" seers_harness/validation/runner.py
grep -c "fold_portfolio_journal(" seers_harness/validation/runner.py
grep -c "apply_status_transitions(" seers_harness/validation/runner.py
# each returned 1

git diff -- seers_harness/evolution/delta_portfolio.py
# no diff

.venv/bin/python -m pytest -q
# 377 passed in 46.64s
```

## Next Phase Readiness

Proceed to **08-G5**: real DeepSeek Stage 3 (`n=20`, `c=20`) acceptance batch, verification document, and final user spot-check. G4’s local evidence confirms runner mechanics; G5 must supply the real-provider evidence.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-28*
