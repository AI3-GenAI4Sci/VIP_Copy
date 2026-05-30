---
phase: 09-acceptance-metrics-evolution-algorithm-closure
verified: 2026-05-30T05:05:10Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 9: Acceptance Metrics & Evolution Algorithm Closure Verification Report

**Phase Goal:** Close the acceptance-metrics and evolution-algorithm gaps with explicit exploration decisions, rubric-only reward provenance, folded posterior evidence, bounded merged-node case reading, and a real 30-request concurrency-5 validation run.
**Verified:** 2026-05-30T05:05:10Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Every request can produce an explicit `exploration_decision`; no-trial reasons are structural/evidence-based. | VERIFIED | `select_trial_delta(...)` returns `ExplorationDecision` with allowed `NoTrialReason` values in `seers_harness/evolution/delta_portfolio.py`; runner appends `_exploration_decision_event(decision)` before trial/no-trial branching; real run has 30/30 snapshots with `exploration_decision`. |
| 2 | Old pressure/probability shortcuts are absent from production exploration and snapshot surfaces. | VERIFIED | `rg` found no `token_budget_pressure`, `production_pressure`, `trial_prob`, random/static skip, hardcoded force, artificial/manual prior, or `trial_gate` tokens in `seers_harness/evolution` and `seers_harness/validation`; `tests/test_phase09_acceptance_gates.py` passed. |
| 3 | Trial selection uses Thompson sampling over eligible experimental deltas and filters by target skill. | VERIFIED | `select_trial_delta` samples `rng.betavariate(row.belief_alpha, row.belief_beta)` over eligible rows; `_run_one_request` passes `target_skill=_target_skill_for_nodes(nodes)`. CR-02 regression `test_run_one_request_rejects_delta_for_wrong_target_skill` passed. |
| 4 | Trial reward and posterior updates use rubric-only provenance. | VERIFIED | `compute_uplift` consumes typed `PersonalizedCopyRubricArtifact` and sets `is_positive` only via `trial_mean_rubric_score > baseline_mean_rubric_score`; real journal has 30 rows, all with rubric mean fields, and every `success` matches the mean comparison. |
| 5 | Delta lifecycle transitions are based on rubric win/loss posterior evidence, not token-cost blocking. | VERIFIED | `apply_status_transitions` ignores token-cost compatibility args and transitions from `sample_count`, success/failure counts, and Wilson LCB only; status-machine tests are included in the full suite. |
| 6 | Journal rows are folded before M5 summary reads posterior state, without replaying old stage rows. | VERIFIED | `_run_stage` records `journal_entries_before`, folds only `new_entries` with `fold_portfolio_entries`, applies status transitions, then calls `write_batch_summary(final_portfolio=delta_portfolio)`. CR-01 regression `test_fold_portfolio_journal_does_not_replay_prior_stage_rows` passed; real `trial_belief_update_count` is 3. |
| 7 | Real Phase 09 validation completed as 30 requests at concurrency 5 with all rows ok. | VERIFIED | `tests/smoke/.runs/20260530T022014Z/stage3/index.json` has `n=30`, `concurrency=5`, and 30 request rows; `batch_summary.json.by_failure_class == {"ok": 30}`; journal has 30 rows. |
| 8 | Acceptance metrics are reclassified as mechanism evidence and record-only observations, not old hard gates. | VERIFIED | `09-ACCEPTANCE-EVIDENCE.md` records factor/cache/token/trial count as record-only; source anti-cheat test scans validation source for numeric acceptance comparisons and passed. |
| 9 | Bounded merged-node case reading and repair decision are evidence-linked and preserve the merged production path. | VERIFIED | `09-CASE-READING.md` contains 8 sampled requests with 40 existing evidence paths; sampled artifacts have factors, candidates, rubric judgments, snapshots, and valid `source_factor_id` links. `09-MERGED-NODE-ASSESSMENT.md` keeps merged production path and limits repair to SKILL wording; `tests/test_phase09_skill_contract.py` passed. |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `seers_harness/evolution/delta_portfolio.py` | Exploration decision contract, allowed reasons, information trigger, Thompson selection | VERIFIED | Exists, substantive, wired into runner; target filtering present. |
| `seers_harness/validation/evolution_snapshot.py` | Snapshot reducer for `exploration_decision` | VERIFIED | Emits top-level `exploration_decision`; no old `trial_gate` key. |
| `seers_harness/validation/runner.py` | Exploration, rubric reward, fold-before-summary, run-shape wiring | VERIFIED | Calls selector, runs baseline/trial rubric paths, appends journal, folds new entries, supports `--num-requests 30 --concurrency 5`. |
| `seers_harness/evolution/uplift.py` | Rubric-only reward helper | VERIFIED | Uses `PersonalizedCopyRubricArtifact.judgments[*].total_score`; token/behavior fields are record-only. |
| `seers_harness/evolution/portfolio_journal.py` | Journal rubric provenance and fold helpers | VERIFIED | `PortfolioJournalEntry` forbids extras and carries rubric mean fields; fold updates posterior from binary success. |
| `seers_harness/evolution/status_machine.py` | Rubric posterior lifecycle transitions | VERIFIED | Token-cost args are compatibility-only and ignored. |
| `seers_harness/validation/batch_summary_writer.py` and `machine_judges.py` | Folded M5 reporting | VERIFIED | `final_portfolio` flows to `build_behavioral_report`; M5 counts folded `sample_count > 0`. |
| `tests/test_phase09_acceptance_gates.py` | Anti-cheat source gates | VERIFIED | Ran and passed with skill contract tests: `7 passed in 0.08s`. |
| `09-ACCEPTANCE-EVIDENCE.md` | Real-run ledger | VERIFIED | Records completed run `20260530T022014Z`; direct JSON checks confirmed 30 rows, concurrency 5, ok=30. |
| `09-CASE-READING.md` and `09-MERGED-NODE-ASSESSMENT.md` | Bounded reading and merged-node verdict | VERIFIED | 8 request readings tied to existing artifacts; repair decision is lightweight SKILL wording only. |
| `workflow-skills/current/personalized-copy-generation/SKILL.md` | Guarded wording repair | VERIFIED | Contract test confirms merged path, plural distinctness, semantic linkage, and absence of forcing patterns. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `runner.py` | `delta_portfolio.py` | `select_trial_delta(... target_skill=..., rng=...)` | WIRED | Selection receives portfolio, surfaces, target skill, and rng; no pressure/probability inputs. |
| `runner.py` | `evolution_snapshot.py` | `_exploration_decision_event` then `write_evolution_snapshot` | WIRED | Every real-run request snapshot contains `exploration_decision`. |
| `runner.py` | `uplift.py` | Baseline/trial rubric artifacts passed to `compute_uplift` | WIRED | Journal rows persist baseline/trial means and score delta. |
| `runner.py` | `portfolio_journal.py` | `append_journal_entry`, `read_journal_entries`, `fold_portfolio_entries` | WIRED | Real journal has 30 rubric-derived rows; fold replay regression is covered. |
| `runner.py` | `batch_summary_writer.py` | `write_batch_summary(... final_portfolio=delta_portfolio)` | WIRED | Real summary reports folded M5 value 3. |
| `09-ACCEPTANCE-EVIDENCE.md` | `09-CASE-READING.md` | Completed run id and sampled request paths | WIRED | 40 referenced case-reading evidence paths exist. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `evolution_snapshot.json` | `exploration_decision` | Runner event from `ExplorationDecision.model_dump()` | Yes - 30/30 real snapshots populated | FLOWING |
| `portfolio_journal.jsonl` | rubric means / `success` | Baseline and trial `personalized_copy_rubric` artifacts via `compute_uplift` | Yes - 30 rows; success matches rubric comparison | FLOWING |
| `batch_summary.json.behavioral_metrics.trial_belief_update_count` | folded posterior `sample_count` | `fold_portfolio_entries(new_entries, delta_portfolio)` then `final_portfolio` | Yes - real summary reports 3 | FLOWING |
| `09-CASE-READING.md` | sampled observations | Real run request artifacts under `tests/smoke/.runs/20260530T022014Z/stage3` | Yes - all 40 referenced paths exist | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| CR-01/CR-02 regressions stay fixed | `.venv/bin/python -m pytest tests/test_validation_runner.py::test_run_one_request_rejects_delta_for_wrong_target_skill tests/test_validation_runner.py::test_fold_portfolio_journal_does_not_replay_prior_stage_rows -q` | `2 passed in 0.11s` | PASS |
| Phase 09 anti-cheat and SKILL contract gates | `.venv/bin/python -m pytest tests/test_phase09_acceptance_gates.py tests/test_phase09_skill_contract.py -q` | `7 passed in 0.08s` | PASS |
| Full test suite | `.venv/bin/python -m pytest -q` | `399 passed in 46.91s` | PASS |
| Real-run artifact facts | Python JSON check over run `20260530T022014Z` | n=30, concurrency=5, rows=30, ok=30, journal rows=30, snapshots missing=0 | PASS |

### Probe Execution

No phase-declared `probe-*.sh` files were found or required. Step 7c skipped.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| D9-EVO-01..06 | 09-01 | Explicit exploration decisions, no pressure/probability shortcuts, Thompson selection | SATISFIED | Selector/snapshot/runner code plus anti-cheat tests and real snapshots. |
| D9-EVO-07..10 | 09-02 | Rubric-only reward, posterior fold, lifecycle from win/loss evidence | SATISFIED | `uplift.py`, `portfolio_journal.py`, `status_machine.py`, journal data, tests. |
| D9-MET-01..07 | 09-03/09-04/09-05 | Replace old metric thresholds, folded M5, real 30x5 run, bounded reading | SATISFIED | Ledger, real run JSON, case reading, summary writer flow. |
| D9-MERGE-01..09 | 09-05 | Preserve merged path; assess and lightly repair from bounded evidence | SATISFIED | Case reading, merged assessment, SKILL contract test. |
| D9-GATE-01..05 | 09-01..09-05 | Real evidence, mechanism evidence, anti-cheat, reward provenance, bounded reading | SATISFIED | Real run `20260530T022014Z`, anti-cheat tests, rubric journal, bounded case reading. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| None | - | - | - | No blocker anti-patterns found in Phase 09 touched production/test/SKILL surfaces. Static `return []` / `return {}` matches are normal empty-state helpers, not stubs feeding user-visible output. |

### Human Verification Required

None. The phase includes bounded qualitative case reading, but the required artifact is already populated from real run evidence and its referenced files exist. No additional visual, external-service, or manual UAT item is needed for this verifier decision.

### Gaps Summary

No gaps found. The previously reviewed CR-01 and CR-02 blockers are fixed in code and covered by regression tests. The real-run acceptance evidence is present and internally consistent.

---

_Verified: 2026-05-30T05:05:10Z_
_Verifier: the agent (gsd-verifier)_
