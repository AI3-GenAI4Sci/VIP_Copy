---
phase: 09-acceptance-metrics-evolution-algorithm-closure
plan: 04
status: completed-real-provider-run
updated_at: 2026-05-30T04:30:00Z
---

# Phase 09 Acceptance Evidence

This ledger separates local preconditions from real acceptance evidence.
Pytest is a prerequisite only. Phase 09 acceptance requires a real DeepSeek
Stage 3 run with 30 requests at concurrency 5.

## Local Pytest Result

Command:

```bash
.venv/bin/python -m pytest tests/test_phase09_acceptance_gates.py tests/test_delta_portfolio.py tests/test_uplift.py tests/test_portfolio_journal.py tests/test_validation_runner.py tests/test_08_07_behavioral_metrics.py tests/test_batch_summary_writer.py -q
```

Result: PASS, `80 passed in 0.90s`.

## Anti-Cheat Test Result

Command:

```bash
.venv/bin/python -m pytest tests/test_phase09_acceptance_gates.py -q
```

Result: PASS, `4 passed in 0.07s`.

Coverage:

- Production source scan is limited to `seers_harness/evolution` and
  `seers_harness/validation`; the test file does not scan itself.
- Forbidden shortcut identifiers and no-trial reasons are absent from live
  exploration code.
- Reward provenance requires `PersonalizedCopyRubricArtifact`,
  `baseline_mean_rubric_score`, and `trial_mean_rubric_score`.
- Mechanism evidence identifiers are present for exploration decision,
  selected delta evidence, trial workspace evidence, journal append evidence,
  folded posterior evidence, and `trial_belief_update_count`.
- Factor count, cache miss, token use, and fixed trial count are not encoded as
  acceptance pass/fail gates in validation source.

## Full Suite Result

Command:

```bash
.venv/bin/python -m pytest -q
```

Result: PASS, `394 passed in 46.90s`.

## Real DeepSeek Command

Command used for Task 3:

```bash
.venv/bin/python -u -m seers_harness.validation.runner --env-file .env.local --stage 3 --num-requests 30 --concurrency 5
```

Secrets handling: `.env.local` is loaded through runner env-file support. The
resolved `DEEPSEEK_API_KEY` value is not printed or copied into this ledger.

## Real Run Status

Real run status: COMPLETED

Failure class: none

Safe error summary: N/A. The runner completed Stage 3 and printed
`stage 3 PASSED` / `all requested stages passed`.

## Real Run Artifacts

Real run id: 20260530T022014Z

Index path: `tests/smoke/.runs/20260530T022014Z/stage3/index.json`

Batch summary path: `tests/smoke/.runs/20260530T022014Z/stage3/batch_summary.json`

Portfolio journal path: `tests/smoke/.runs/20260530T022014Z/portfolio_journal.jsonl`

Sampled request paths:

- `tests/smoke/.runs/20260530T022014Z/stage3/-2222528033296871792`
- `tests/smoke/.runs/20260530T022014Z/stage3/-2223161019833131686`
- `tests/smoke/.runs/20260530T022014Z/stage3/-6833651210813617137`
- `tests/smoke/.runs/20260530T022014Z/stage3/-6833651252302891142`
- `tests/smoke/.runs/20260530T022014Z/stage3/-6833674815337504199`
- `tests/smoke/.runs/20260530T022014Z/stage3/-6833675077757301063`
- `tests/smoke/.runs/20260530T022014Z/stage3/-6833721464958057635`
- `tests/smoke/.runs/20260530T022014Z/stage3/-6833721702418762089`

Completed run facts:

- `index.json` records `n=30` and `concurrency=5`.
- `index.json` has 30 request rows.
- `by_failure_class` is `{"ok": 30}`.
- 30/30 request directories contain `evolution_snapshot.json`.
- 30/30 snapshots contain `exploration_decision`.
- `portfolio_journal.jsonl` contains 30 rubric-derived trial rows.
- `batch_summary.json.behavioral_metrics.trial_belief_update_count` is 3,
  proving the batch summary read folded posterior state.

## Mechanism Evidence Checklist

| Evidence | Status | Notes |
|---|---|---|
| `exploration_decision` for every request | PASS | 30/30 snapshots contain `exploration_decision`. |
| Selected delta when trialing | PASS | 30/30 snapshots trialed with a selected delta id. |
| Trial workspace path when trialing | PASS | Trial workspace evidence exists in request directories for trialed requests. |
| Portfolio journal row when trialing | PASS | `portfolio_journal.jsonl` contains 30 rows. |
| Folded posterior `sample_count` / alpha / beta / status evidence | PASS | Folded posterior evidence reaches `trial_belief_update_count = 3`. |
| `batch_summary.json` M5 reads folded state | PASS | `batch_summary.json` reports folded M5 rather than raw journal row count. |

## Record-Only Metrics

These fields are observations only. They are not pass/fail thresholds and must
not influence exploration.

| Metric | Observation | Acceptance treatment |
|---|---:|---|
| factor_count_p50 | 2.0 | record-only |
| factor_diversity_score | 0.9209781029347837 | record-only |
| copy_candidate_count_p50 | 3.5 | record-only |
| prompt_cache_miss_tokens | 1688178 aggregated from 60 usage files | record-only |
| total_tokens | 21487942 aggregated from 60 usage files | record-only |
| observed trial count | 30 journal rows | explained by exploration decisions, not fixed target |

## Blockers

None for the completed run.

Prior blocked attempt retained for traceability: run `20260529T163211Z`
stopped at 16 rows after DeepSeek returned HTTP 402 `Insufficient Balance`.
That run remains partial evidence only and was superseded by completed run
`20260530T022014Z`.
