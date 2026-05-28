---
status: gaps_found
phase: 08-evolution-wiring-and-runner-debt
batch_id: 20260528T032645Z
commit_of_record: 3851d4ddc4a92bb18b9082e09ee56f5874b585b5
code_under_test: uncommitted local G2-G4 working tree
acceptance_gates: 8
verified_at: 2026-05-28T04:05:00Z
verifier: codex + gsd-verifier subagent 019e6cb4-9a8f-72e0-a30e-b90ff5b3ca5c
---

# Phase 8 Verification

Phase 8 gap-closure cannot be marked passed. The real DeepSeek Stage 3 batch was launched with `--env-file .env.local --stage 3`, but request `-6833651210813617137` failed at `factor_discovery` with malformed tool-call JSON and the runner stopped Stage 3 as failed.

Evidence:
- Run log: `.planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/runner-20260528T032645Z.log`
- Stage artifact dir: `tests/smoke/.runs/20260528T032645Z/stage3/`
- Index: `tests/smoke/.runs/20260528T032645Z/stage3/index.json`
- Batch summary: `tests/smoke/.runs/20260528T032645Z/stage3/batch_summary.json`

## Truths Verification

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D8-ACC-1 Stage 3 batch completes without timeout / stale env / unhandled transient | FAIL | Log lines 1-5 show env-file loaded and Stage 3 c=20 started, then `provider_error -> fail-fast`; final log line says `stage 3 FAILED`. |
| 2 | F-08-B fix: every Stage 3 request has 3 production-node `messages.jsonl[0].content` entries > 100 bytes | FAIL | 58 captured messages had min 5452 bytes, so SKILL prose is present where captured; expected 60 messages. The failed request is missing `copy_generation` and `personalized_copy_rubric` evidence. |
| 3 | F-08-C fix: copy_generation `prompt_cache_miss` mean is within [500, 5000] tokens | FAIL | 19 copy usage files; mean `prompt_cache_miss_tokens` = 247.42, median 274, min 34, max 316. This is below the signed target band. |
| 4 | F-08-01 fix: at least 5/20 requests trigger a trial | FAIL | 20 `evolution_snapshot.json` files; `trials[]` total = 0; `trial_workspace` dirs = 0. |
| 5 | F-08-D Gap 8 fix: at least one delta status transition and a portfolio journal entry | FAIL | `portfolio_journal.jsonl` is absent; `batch_summary.json.behavioral_metrics.trial_belief_update_count` = 0. |
| 6 | D8-ACC-3 retained: `failure_class` in `index.json`, and `by_failure_class` in `batch_summary.json` | PASS | `index.json` has 20 request rows with failure classes `ok` and `malformed_tool_args`; `batch_summary.json.by_failure_class` is `{malformed_tool_args: 1, ok: 19}`. |
| 7 | D8-ACC-5: 7 scheduled WR/IN items closed to phase-8 commit refs | FAIL | `07-WRIN-TRIAGE.md` remains scheduled/blocked; Stage 3 failed and G2-G4 work is not yet represented by a clean GSD commit chain. |
| 8 | Manual copy-quality spot-check of 5 sampled request outputs | NOT_EVALUATED | G5 is `autonomous: false`, but Stage 3 failed before acceptance. A manual spot-check cannot turn a failed batch into passed. |

## Batch Artifact Counts

- Request dirs: 20
- `factor_discovery` evidence messages: 20; usage files: 20; artifacts: 19
- `copy_generation` evidence messages: 19; usage files: 19; artifacts: 19
- `personalized_copy_rubric` evidence messages: 19; usage files: 19; artifacts: 19
- Message content lengths across captured evidence: count 58, min 5452, mean 5664.3, max 6041
- `index.json` exists and covers 20 rows
- `batch_summary.json` exists and reports `malformed_tool_args: 1`, `ok: 19`
- `portfolio_journal.jsonl` does not exist

## Root Evidence

The failing provider response failed JSON parsing in `openai_compatible.py:_parse_args`:

`ProviderResponseError: Failed to parse tool_call.arguments for node factor_discovery`

The raw snippet includes an unescaped quote inside `user_side_signal`:

`呈现"为他人购物为主、偶尔为自己停留"的模式`

This is a real-provider malformed tool-call-arguments failure, not a mock-provider or unit-test issue.

## Gaps

1. Stage 3 fail-fast remains an acceptance blocker.
2. The G2 context disclosure target did not hold in real copy-generation usage: prompt cache miss stayed below the signed [500, 5000] target band.
3. The G4 trial mechanism did not trigger in the Stage 3 batch: no selected deltas, no trial workspaces, no journal, no status transitions.
4. `07-WRIN-TRIAGE.md` cannot be closed until a clean Phase 8 commit chain exists and a new Stage 3 acceptance run passes.
5. GSD close-out recovery is needed: G2-G4 summaries exist, but the corresponding code changes are still local/uncommitted in this checkout.

## Closure

Phase 8 status: `gaps_found`.

Next action is a GSD recovery pass, not Phase 8 pass/closeout:
- restore a clean GSD commit chain for G2-G4 or explicitly supersede those local changes;
- fix the Stage 3 malformed-tool-args handling/root cause;
- restore cache-miss target evidence and trial triggering;
- re-run real DeepSeek Stage 3;
- only then run the locked manual spot-check and close `07-WRIN-TRIAGE.md`.
