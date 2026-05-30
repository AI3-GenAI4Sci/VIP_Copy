---
phase: 09-acceptance-metrics-evolution-algorithm-closure
plan: 04
subsystem: validation
tags: [acceptance-gates, real-deepseek, evidence-ledger, anti-cheat]

requires:
  - phase: 09-acceptance-metrics-evolution-algorithm-closure
    provides: runner run shape and folded posterior summary path from plan 09-03
provides:
  - Phase 09 production-source anti-cheat gates
  - Acceptance evidence ledger separating local gates from real evidence
  - Completed real DeepSeek Stage 3 run with 30 requests at concurrency 5
affects: [phase-09, acceptance-evidence, validation-runner]

tech-stack:
  added: []
  patterns: [source anti-cheat tests, real-run evidence ledger]

key-files:
  created:
    - tests/test_phase09_acceptance_gates.py
    - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-ACCEPTANCE-EVIDENCE.md
    - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-04-SUMMARY.md
  modified: []

key-decisions:
  - "Pytest and FakeProvider evidence are recorded as local preconditions, not acceptance substitutes."
  - "Real acceptance evidence comes from DeepSeek run 20260530T022014Z: 30 requests, concurrency 5, by_failure_class ok=30."
  - "Factor count, cache miss, token use, and observed trial count are record-only observations."

requirements-completed:
  - D9-MET-01
  - D9-MET-03
  - D9-MET-04
  - D9-MET-06
  - D9-MET-07
  - D9-GATE-01
  - D9-GATE-02
  - D9-GATE-03
  - D9-GATE-04
  - D9-GATE-05

completed: 2026-05-30
---

# Phase 09 Plan 04: Acceptance Gates and Real Evidence Summary

**Phase 09 now has source-level anti-cheat gates and completed real DeepSeek acceptance evidence.**

## Accomplishments

- Added `tests/test_phase09_acceptance_gates.py` to scan production source for forbidden exploration shortcuts, reward-provenance shortcuts, missing mechanism evidence, and old fixed acceptance gates.
- Created `09-ACCEPTANCE-EVIDENCE.md` as the acceptance ledger.
- Re-ran the blocked DeepSeek acceptance command after balance was restored.
- Recorded completed run `20260530T022014Z`: Stage 3, 30 requests, concurrency 5, `by_failure_class.ok = 30`.

## Task Commits

1. **Task 1: anti-cheat gates** - `09b2031`
2. **Task 2: local acceptance ledger** - `a24838a`
3. **Task 3 blocked attempt evidence** - `946960f`
4. **Task 3 completion evidence** - pending this summary commit

## Real Run Evidence

- Command: `.venv/bin/python -u -m seers_harness.validation.runner --env-file .env.local --stage 3 --num-requests 30 --concurrency 5`
- Run id: `20260530T022014Z`
- Index: `tests/smoke/.runs/20260530T022014Z/stage3/index.json`
- Batch summary: `tests/smoke/.runs/20260530T022014Z/stage3/batch_summary.json`
- Journal: `tests/smoke/.runs/20260530T022014Z/portfolio_journal.jsonl`
- Result: 30/30 rows, `by_failure_class = {"ok": 30}`
- Mechanism: 30/30 snapshots contain `exploration_decision`; 30 journal rows were written.
- Folded M5: `trial_belief_update_count = 3`.

## Record-Only Observations

- `factor_count_p50`: 2.0
- `factor_diversity_score`: 0.9209781029347837
- `copy_candidate_count_p50`: 3.5
- Aggregated `prompt_cache_miss_tokens`: 1688178
- Aggregated `total_tokens`: 21487942
- Observed trial count: 30 journal rows, explained by exploration decisions rather than a fixed target.

## Deviations from Plan

### Provider Blocker and Resume

- **Found during:** Task 3 first real-run attempt
- **Issue:** DeepSeek returned HTTP 402 `Insufficient Balance` during run `20260529T163211Z`, stopping at 16/30 rows.
- **Fix:** Recorded the blocked attempt in the ledger, waited for balance restoration, then resumed Task 3 without re-running completed plans or local gates.
- **Verification:** Completed run `20260530T022014Z` passed all requested Stage 3 work.

**Total deviations:** 1 provider-blocked checkpoint resolved by resume.
**Impact:** No acceptance shortcut was taken; the partial run remains traceability only.

## Verification

- `.venv/bin/python -m pytest tests/test_phase09_acceptance_gates.py -q` -> `4 passed`
- `.venv/bin/python -m pytest -q` -> `394 passed` before real-run resume
- Real command -> runner printed `stage 3 PASSED` and `all requested stages passed`
- Ledger assertion for `Real run status: COMPLETED`, concrete paths, `exploration_decision`, and no current `BLOCKED` status -> passed

## Next Phase Readiness

Plan 09-05 can now perform bounded case reading and merged-node assessment from completed real run `20260530T022014Z`.

## Self-Check: PASSED

- Anti-cheat test file exists.
- Acceptance ledger records completed real run evidence.
- Real run has 30 request rows and `by_failure_class.ok = 30`.
- `09-04-SUMMARY.md` created.
