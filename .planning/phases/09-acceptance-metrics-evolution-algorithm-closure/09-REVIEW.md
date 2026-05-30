---
phase: 09-acceptance-metrics-evolution-algorithm-closure
reviewed: 2026-05-30T04:50:24Z
depth: deep
files_reviewed: 26
files_reviewed_list:
  - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-01-SUMMARY.md
  - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-02-SUMMARY.md
  - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-03-SUMMARY.md
  - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-04-SUMMARY.md
  - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-05-SUMMARY.md
  - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-ACCEPTANCE-EVIDENCE.md
  - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CASE-READING.md
  - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-MERGED-NODE-ASSESSMENT.md
  - seers_harness/evolution/delta_portfolio.py
  - seers_harness/evolution/portfolio_journal.py
  - seers_harness/evolution/status_machine.py
  - seers_harness/evolution/uplift.py
  - seers_harness/validation/batch_summary_writer.py
  - seers_harness/validation/evolution_snapshot.py
  - seers_harness/validation/machine_judges.py
  - seers_harness/validation/runner.py
  - tests/test_08_07_behavioral_metrics.py
  - tests/test_batch_summary_writer.py
  - tests/test_delta_portfolio.py
  - tests/test_phase09_acceptance_gates.py
  - tests/test_phase09_skill_contract.py
  - tests/test_portfolio_journal.py
  - tests/test_status_machine.py
  - tests/test_uplift.py
  - tests/test_validation_runner.py
  - workflow-skills/current/personalized-copy-generation/SKILL.md
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
resolved_at: 2026-05-30T05:05:00Z
---

# Phase 09: Code Review Report

**Reviewed:** 2026-05-30T04:50:24Z
**Depth:** deep
**Files Reviewed:** 26
**Status:** clean

## Summary

Reviewed Phase 09 plans/summaries, acceptance evidence, bounded case reading, merged-node assessment, and the implementation/test changes from `af069ab..HEAD`.

The implementation has two blocking correctness defects in the evolution loop. Both affect the acceptance claims: posterior state can be over-counted by replaying old journal rows, and trial selection can choose deltas for the wrong target skill because the runner no longer passes target-skill constraints into the selector.

## Critical Issues

### CR-01: Portfolio Journal Is Replayed Into Already-Folded State At Every Stage Boundary

**File:** `seers_harness/validation/runner.py:1179`

**Issue:** `_run_stage` folds the entire append-only `portfolio_journal.jsonl` into the live in-memory `delta_portfolio` at the end of each stage:

```python
delta_portfolio[:] = fold_portfolio_journal(journal_path, delta_portfolio)
```

`fold_portfolio_journal` replays every row in the journal into whatever portfolio object it receives. Because `run()` keeps the same `delta_portfolio` across stages, a normal multi-stage run folds Stage 2 rows once at the end of Stage 2 and then folds those same Stage 2 rows again at the end of Stage 3, along with Stage 3 rows. The function is not idempotent: replaying one journal row twice changes `sample_count` from 1 to 2 and `belief_alpha` from 2.0 to 3.0 for a single success.

This corrupts posterior evidence (`sample_count`, `belief_alpha`, `belief_beta`, status transitions) and can change future `exploration_decision` behavior and `batch_summary.json.behavioral_metrics.trial_belief_update_count`. The current tests only cover a single stage with a fresh portfolio, so they miss the cross-stage replay path.

**Fix:** Fold from a clean base portfolio plus the complete journal, or track and apply only new journal rows since the last fold. A minimal fix is to keep immutable base rows and derive `final_portfolio` for summaries without mutating already-folded state:

```python
base_portfolio = [row.model_copy(deep=True) for row in delta_portfolio]
final_portfolio = fold_portfolio_journal(journal_path, base_portfolio)
final_portfolio = apply_status_transitions(final_portfolio, ...)
delta_portfolio[:] = final_portfolio
```

If `delta_portfolio` must remain live across stages, also persist a consumed journal offset/count and fold only entries after that offset. Add a regression test that runs two stages against one `out_dir`, writes one trial in Stage 2 and one in Stage 3, and asserts Stage 2's row is counted exactly once.

**Resolution:** Fixed by recording the journal entry count at stage start and
folding only entries appended during the current stage. The fold logic now uses
`fold_portfolio_entries(...)` so `_run_stage` does not replay prior-stage rows
into an already-folded live portfolio.

**Regression:** `tests/test_validation_runner.py::test_fold_portfolio_journal_does_not_replay_prior_stage_rows`
failed before the fix with `sample_count == 3`; it now passes with
`sample_count == 2`.

### CR-02: Runner Selects Deltas By Surface Only, So A Delta For Another Skill Can Be Trialed

**File:** `seers_harness/validation/runner.py:819`

**Issue:** `select_trial_delta` supports `target_skill`, but `_run_one_request` calls it without that argument:

```python
decision = select_trial_delta(
    portfolio=delta_portfolio,
    applicable_surface=applicable_surface,
    rng=_trial_rng,
)
```

That makes eligibility depend only on `applicable_surface`. `_applicable_surface_for` also injects broad aliases like `product_detail_card` and `recommendation_feed` for the merged generation node. As a result, any experimental row with one of those broad surfaces can be selected even when `row.target_skill` is unrelated to the node being run. The selected row is then patched via `_patch_from_portfolio_row`, so the trial can mutate and evaluate the wrong skill while the snapshot and journal claim the delta was valid evidence for this request.

I reproduced this with a row targeting `current/unrelated-skill/SKILL.md` and `applicable_surface=["product_detail_card"]`; the runner surface helper emits `product_detail_card`, and `select_trial_delta` returns `should_trial=True` for the unrelated delta.

**Fix:** Pass an explicit target constraint from the runner into the selector, and require tests for target mismatch:

```python
decision = select_trial_delta(
    portfolio=delta_portfolio,
    applicable_surface=applicable_surface,
    target_skill="current/personalized-copy-generation/SKILL.md",
    rng=_trial_rng,
)
```

If multiple node targets can be trialed, derive the allowed target skills from `nodes` and filter before selection rather than relying on broad surface tags. Add a unit test where a row shares `applicable_surface` with the request but has a different `target_skill`; it must produce `no_eligible_delta` and no trial workspace or journal row.

**Resolution:** Fixed by deriving `current/{skill_name}/SKILL.md` from the
active node list and passing it as `target_skill` to `select_trial_delta(...)`.
This keeps broad surface aliases useful for display/surface matching without
letting unrelated skill deltas become eligible.

**Regression:** `tests/test_validation_runner.py::test_run_one_request_rejects_delta_for_wrong_target_skill`
failed before the fix because the unrelated delta was selected; it now records
`no_eligible_delta` and writes no journal row.

## Resolution Summary

- `tests/test_validation_runner.py::test_run_one_request_rejects_delta_for_wrong_target_skill` -> PASS
- `tests/test_validation_runner.py::test_fold_portfolio_journal_does_not_replay_prior_stage_rows` -> PASS
- `.venv/bin/python -m pytest tests/test_validation_runner.py tests/test_portfolio_journal.py tests/test_delta_portfolio.py -q` -> PASS, `64 passed`

---

_Reviewed: 2026-05-30T04:50:24Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
