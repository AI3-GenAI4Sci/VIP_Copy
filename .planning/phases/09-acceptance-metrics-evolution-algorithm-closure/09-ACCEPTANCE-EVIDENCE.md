---
phase: 09-acceptance-metrics-evolution-algorithm-closure
plan: 04
status: blocked-real-provider-balance
updated_at: 2026-05-29T17:08:00Z
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

Command planned for Task 3:

```bash
.venv/bin/python -u -m seers_harness.validation.runner --env-file .env.local --stage 3 --num-requests 30 --concurrency 5
```

Secrets handling: `.env.local` is loaded through runner env-file support. The
resolved `DEEPSEEK_API_KEY` value is not printed or copied into this ledger.

## Real Run Status

Real run status: BLOCKED

Failure class: auth

Safe error summary: DeepSeek returned HTTP 402 `Insufficient Balance` during
Stage 3. The runner fail-fasted and exited non-zero before completing the
required 30-request concurrency-5 acceptance run.

## Real Run Artifacts

Real run id: 20260529T163211Z

Index path: `tests/smoke/.runs/20260529T163211Z/stage3/index.json`

Batch summary path: `tests/smoke/.runs/20260529T163211Z/stage3/batch_summary.json`

Portfolio journal path: `tests/smoke/.runs/20260529T163211Z/portfolio_journal.jsonl`

Sampled request paths:

- `tests/smoke/.runs/20260529T163211Z/stage3/-2223161019833131686`
- `tests/smoke/.runs/20260529T163211Z/stage3/-6833651210813617137`
- `tests/smoke/.runs/20260529T163211Z/stage3/-6833721702418762089`
- `tests/smoke/.runs/20260529T163211Z/stage3/-6833791596394007611`
- `tests/smoke/.runs/20260529T163211Z/stage3/-6833932762567548368`
- `tests/smoke/.runs/20260529T163211Z/stage3/-6834003288630524187`

Partial run facts:

- Command reached portfolio bootstrap and produced 3 proposals.
- Command started Stage 3 with `n=30 concurrency=5`.
- `index.json` contains 16 rows before fail-fast: `ok=10`, `auth=6`.
- `portfolio_journal.jsonl` contains 10 rows.
- `batch_summary.json` exists but is partial-run evidence only, not acceptance
  completion evidence.

## Mechanism Evidence Checklist

| Evidence | Status | Notes |
|---|---|---|
| `exploration_decision` for every request | BLOCKED | Partial artifacts show 15/16 written snapshots with exploration decisions; the run did not complete all 30 requests. |
| Selected delta when trialing | PARTIAL | Partial artifacts include 10 trialed snapshot directories. |
| Trial workspace path when trialing | PARTIAL | Trial workspace evidence exists in partial request directories only. |
| Portfolio journal row when trialing | PARTIAL | `portfolio_journal.jsonl` contains 10 rows before fail-fast. |
| Folded posterior `sample_count` / alpha / beta / status evidence | PARTIAL | Partial `batch_summary.json` reports folded `trial_belief_update_count = 3`; not acceptance because run failed. |
| `batch_summary.json` M5 reads folded state | PARTIAL | M5 read folded partial state; the 30-request run is blocked by provider balance. |

## Record-Only Metrics

These fields are observations only. They are not pass/fail thresholds and must
not influence exploration.

| Metric | Observation | Acceptance treatment |
|---|---:|---|
| factor_count_p50 | 2.0 partial-run observation | record-only |
| cache miss | Not summarized in partial ledger | record-only |
| token use | Not summarized in partial ledger | record-only |
| observed trial count | 10 partial journal rows | explained by exploration decisions, not fixed target |

## Blockers

- Real Stage 3 acceptance is blocked by DeepSeek account balance/quota:
  provider returned HTTP 402 `Insufficient Balance`.
- Local gates are complete and green, but D9-GATE-01 is not satisfied because
  the real 30-request concurrency-5 run did not complete.
