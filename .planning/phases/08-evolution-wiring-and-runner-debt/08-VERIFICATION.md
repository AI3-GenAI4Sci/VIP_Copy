---
status: gaps_found
phase: 08-evolution-wiring-and-runner-debt
batch_id: 20260528T055154Z
commit_of_record: e8a850e2f762f60cba035d928cb6d07e02fe7413 + local recovery fixes
code_under_test: committed G2-G4 recovery plus local snapshot/error-classification fixes
acceptance_gates: 8
verified_at: 2026-05-28T06:27:26Z
verifier: codex
---

# Phase 8 Verification

Phase 8 gap-closure cannot be marked passed. A fresh real DeepSeek Stage 3 rerun was launched with `--env-file .env.local --stage 3` and `set -o pipefail`; Stage 3 reached the real c=20 phase after portfolio bootstrap, but failed fast when DeepSeek returned `402 Insufficient Balance` during `copy_generation`.

This rerun shows the G2/G3 recovery path advanced beyond the previous failure:

- Stage3-only bootstrap completed the full current-code request.
- `distill_after_stage1` produced 3 delta proposals.
- Per-node evidence wrote aggregate `usage.json` plus `usage_turns.jsonl`.

It also exposed a remaining runner evidence gap: request-level `evolution_snapshot.json` files did not record the visible bootstrap portfolio, so Stage 3 snapshots still showed `delta_portfolio_before: []` and `trials: []`. A local TDD fix now writes the visible portfolio IDs at request start; this requires a rerun after DeepSeek balance is restored.

Evidence:
- Run log: `.planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/runner-20260528T055154Z.log`
- Stage artifact dir: `tests/smoke/.runs/20260528T055154Z/stage3/`
- Bootstrap artifact dir: `tests/smoke/.runs/20260528T055154Z/portfolio_bootstrap/`
- Index: `tests/smoke/.runs/20260528T055154Z/stage3/index.json`
- Batch summary: `tests/smoke/.runs/20260528T055154Z/stage3/batch_summary.json`

## Truths Verification

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D8-ACC-1 Stage 3 batch completes without timeout / stale env / unhandled transient | FAIL | Batch `20260528T055154Z` reached `stage 3: n=20 concurrency=20`, then failed fast on DeepSeek `402 Insufficient Balance`; final log line says `stage 3 FAILED`. |
| 2 | F-08-B fix: every Stage 3 request has 3 production-node `messages.jsonl[0].content` entries > 100 bytes | FAIL | Stage 3 aborted before all requests completed; partial evidence exists for 20 request dirs but not all three nodes per request. |
| 3 | F-08-C fix: copy_generation `prompt_cache_miss` mean is within [500, 5000] tokens | FAIL | New aggregate writer is active, but partial copy usage mean across 21 captured copy calls was 15154.62 tokens, above the signed band; failed batch cannot satisfy acceptance. |
| 4 | F-08-01 fix: at least 5/20 requests trigger a trial | FAIL | 20 Stage 3 snapshots had `trials[]` total = 0. Root-cause finding: snapshots did not record the visible bootstrap portfolio; local TDD fix now records it at request start. |
| 5 | F-08-D Gap 8 fix: at least one delta status transition and a portfolio journal entry | FAIL | `portfolio_journal.jsonl` is absent; `batch_summary.json.behavioral_metrics.trial_belief_update_count` = 0. |
| 6 | D8-ACC-3 retained: `failure_class` in `index.json`, and `by_failure_class` in `batch_summary.json` | FAIL | `index.json` / `batch_summary.json` were written, but DeepSeek 402 surfaced as `runner_bug` in drained rows. Local TDD fix now classifies 402 / insufficient balance as non-retryable `auth`. |
| 7 | D8-ACC-5: 7 scheduled WR/IN items closed to phase-8 commit refs | FAIL | `07-WRIN-TRIAGE.md` remains scheduled/blocked; Stage 3 has not passed. |
| 8 | Manual copy-quality spot-check of 5 sampled request outputs | NOT_EVALUATED | G5 is `autonomous: false`, but Stage 3 failed before acceptance. A manual spot-check cannot turn a failed batch into passed. |

## Batch Artifact Counts

- Request dirs: 20
- `usage.json` files: 49
- `usage_turns.jsonl` files: 49
- Partial `copy_generation` usage files: 21; aggregate `prompt_cache_miss_tokens` mean 15154.62, min 8184, max 19663
- `index.json` exists and covers 20 rows
- `batch_summary.json` exists and reports `runner_bug: 16`, `ok: 4` before the local 402 classification fix
- `portfolio_journal.jsonl` does not exist

## Root Evidence

The prior `malformed_tool_args` failure did not recur before the new blocker. The fresh fail-fast root error is:

`openai.APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient Balance', ...}}`

The runner then drained in-flight requests and wrote partial artifacts. The new local root-cause finding is independent of the balance blocker: Stage 3-only bootstrap returned 3 deltas, but request snapshots still recorded empty visible portfolios because `_run_one_request` did not emit a `portfolio_assembled` event for the incoming runtime portfolio.

## Gaps

1. Stage 3 fail-fast remains an acceptance blocker until DeepSeek balance is restored and a new run passes.
2. Copy-generation cache-miss evidence is now aggregated correctly, but the observed partial-run mean is above the signed [500, 5000] band; this must be rechecked in the next successful run.
3. Trial triggering still has not passed real acceptance; local TDD fix now records visible portfolios in snapshots so the next run can distinguish selection pressure from portfolio propagation.
4. DeepSeek 402 was misclassified as `runner_bug`; local TDD fix now routes 402 / insufficient balance to non-retryable `auth`.
5. `07-WRIN-TRIAGE.md` cannot be closed until a new Stage 3 acceptance run passes.

## Closure

Phase 8 status: `gaps_found`.

Next action is a GSD recovery pass, not Phase 8 pass/closeout:
- commit the local snapshot visibility and 402 classification fixes after full tests pass;
- restore DeepSeek account balance / API quota;
- rerun real DeepSeek Stage 3 with `set -o pipefail`;
- verify cache-miss band, non-empty visible portfolio snapshots, trial triggering, and journal/status transitions;
- only then run the locked manual spot-check and close `07-WRIN-TRIAGE.md`.
