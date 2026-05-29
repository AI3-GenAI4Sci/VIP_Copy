---
phase: 09-acceptance-metrics-evolution-algorithm-closure
plan: 04
status: local-gates-passed-real-run-pending
updated_at: 2026-05-29T16:30:11Z
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

Real run status: PENDING

Failure class: N/A

Safe error summary: N/A

## Real Run Artifacts

Real run id: PENDING

Index path: PENDING

Batch summary path: PENDING

Portfolio journal path: PENDING

Sampled request paths:

- PENDING

## Mechanism Evidence Checklist

| Evidence | Status | Notes |
|---|---|---|
| `exploration_decision` for every request | PENDING | Requires real Stage 3 artifacts. |
| Selected delta when trialing | PENDING | Requires real Stage 3 artifacts. |
| Trial workspace path when trialing | PENDING | Requires real Stage 3 artifacts. |
| Portfolio journal row when trialing | PENDING | Requires `portfolio_journal.jsonl`. |
| Folded posterior `sample_count` / alpha / beta / status evidence | PENDING | Requires folded portfolio state in summary M5 path. |
| `batch_summary.json` M5 reads folded state | PENDING | Requires real Stage 3 `batch_summary.json`. |

## Record-Only Metrics

These fields are observations only. They are not pass/fail thresholds and must
not influence exploration.

| Metric | Observation | Acceptance treatment |
|---|---:|---|
| factor_count_p50 | PENDING | record-only |
| cache miss | PENDING | record-only |
| token use | PENDING | record-only |
| observed trial count | PENDING | explained by exploration decisions, not fixed target |

## Blockers

None during local gates.
