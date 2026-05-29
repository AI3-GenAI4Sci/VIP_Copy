---
phase: 09-acceptance-metrics-evolution-algorithm-closure
plan: 02
subsystem: evolution
tags: [rubric-reward, portfolio-journal, posterior-update, status-machine]

requires:
  - phase: 09-acceptance-metrics-evolution-algorithm-closure
    provides: explicit exploration decisions and trial selection evidence
provides:
  - Rubric-only trial reward helper based on baseline/trial mean total_score
  - Portfolio journal rows carrying baseline/trial rubric means and score delta
  - Runner trial journal migration from behavioral/token reward proxies to rubric provenance
  - Status transitions based on rubric win/loss posterior evidence only
affects: [phase-09, evolution-posterior, validation-runner, acceptance-gates]

tech-stack:
  added: []
  patterns: [typed rubric artifact reward, append-only JSONL provenance, compatibility-only ignored token inputs]

key-files:
  created:
    - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-02-SUMMARY.md
  modified:
    - seers_harness/evolution/uplift.py
    - seers_harness/evolution/portfolio_journal.py
    - seers_harness/evolution/status_machine.py
    - seers_harness/validation/runner.py
    - tests/test_uplift.py
    - tests/test_portfolio_journal.py
    - tests/test_status_machine.py
    - tests/test_validation_runner.py

key-decisions:
  - "Trial reward success is true only when trial_mean_rubric_score is strictly greater than baseline_mean_rubric_score."
  - "Token cost and behavioral metrics remain record-only provenance; they do not decide reward or lifecycle status."
  - "Legacy status-machine token-cost parameters are retained only as ignored compatibility inputs."

patterns-established:
  - "Reward helpers consume typed PersonalizedCopyRubricArtifact values and derive request-level means from judgments[*].total_score."
  - "Journal rows persist audit provenance for the binary posterior reward before fold replay updates alpha/beta/sample_count."

requirements-completed:
  - D9-EVO-07
  - D9-EVO-08
  - D9-EVO-09
  - D9-EVO-10
  - D9-GATE-04

duration: 21min
completed: 2026-05-29
---

# Phase 09 Plan 02: Rubric Reward Provenance Summary

**Rubric mean score now drives trial reward, posterior journal fold, and status lifecycle decisions without token-cost vetoes.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-05-29T15:49:30Z
- **Completed:** 2026-05-29T16:10:25Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Replaced old `TrialOutcome` uplift semantics with typed `PersonalizedCopyRubricArtifact` mean-score comparison.
- Extended journal entries with `baseline_mean_rubric_score`, `trial_mean_rubric_score`, and `score_delta`, while keeping extra fields forbidden.
- Migrated the runner trial append path to load baseline/trial rubric artifacts, compute rubric-derived success, and persist auditable reward provenance.
- Removed token-cost lifecycle blocking from status transitions; promotion/rejection now depends on sample count and rubric win/loss evidence.

## Task Commits

1. **Task 1 RED: rubric uplift tests** - `b98ba57` (test)
2. **Task 1 GREEN: rubric mean reward helper** - `4bad983` (feat)
3. **Task 2: rubric journal evidence and runner migration** - `79dd80d` (feat)
4. **Task 3: remove token-cost status blocker** - `fa95077` (feat)

## Files Created/Modified

- `seers_harness/evolution/uplift.py` - Computes reward from baseline/trial rubric mean scores.
- `seers_harness/evolution/portfolio_journal.py` - Persists rubric mean provenance and folds binary success into posterior counters.
- `seers_harness/evolution/status_machine.py` - Applies lifecycle transitions from posterior evidence only.
- `seers_harness/validation/runner.py` - Loads trial rubric artifacts and appends rubric-derived journal rows.
- `tests/test_uplift.py` - Covers strict mean-score reward behavior and empty rubric artifacts.
- `tests/test_portfolio_journal.py` - Covers provenance persistence, fold replay, and extra-field rejection.
- `tests/test_status_machine.py` - Covers token cost no longer blocking promotion.
- `tests/test_validation_runner.py` - Covers runner journal rows with rubric means and rubric-derived success.

## Decisions Made

- Empty rubric artifacts produce a deterministic mean of `0.0`, so missing/empty judgments fail closed without crashing.
- Runner keeps behavioral metric lift in journal rows for analysis only, computed as trial minus baseline, but `success` comes only from rubric means.
- Status-machine token-cost arguments remain accepted to avoid unrelated callsite churn, but are explicitly ignored.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `tests/` is gitignored in this workspace, so plan-listed test files were staged with targeted `git add -f`. No other ignored files were staged.
- The workspace contains many pre-existing unrelated uncommitted changes. They were left untouched per execution constraints.

## Known Stubs

None.

## Threat Flags

None.

## Verification

- `.venv/bin/python -m pytest tests/test_uplift.py -q` -> `4 passed`
- `python - <<'PY' ... uplift source assertions ... PY` -> passed
- `.venv/bin/python -m pytest tests/test_portfolio_journal.py tests/test_validation_runner.py -k "journal or trial or rubric" -q` -> `13 passed, 28 deselected`
- `.venv/bin/python -m pytest tests/test_status_machine.py -q` -> `6 passed`
- `.venv/bin/python -m pytest tests/test_uplift.py tests/test_portfolio_journal.py tests/test_status_machine.py tests/test_validation_runner.py -q` -> `51 passed`
- `.venv/bin/python -m pytest -q` -> `389 passed`

## User Setup Required

None.

## Next Phase Readiness

Plan 09-03 can consume journal rows whose posterior reward is auditable from rubric means, and status transitions no longer let token/cost records veto rubric win evidence.

## Self-Check: PASSED

- Key production and test files exist.
- Task commits `b98ba57`, `4bad983`, `79dd80d`, and `fa95077` exist.
- No tracked file deletions were introduced by task commits.
- User-requested STATE/ROADMAP files were not updated by this executor.

---
*Phase: 09-acceptance-metrics-evolution-algorithm-closure*
*Completed: 2026-05-29*
