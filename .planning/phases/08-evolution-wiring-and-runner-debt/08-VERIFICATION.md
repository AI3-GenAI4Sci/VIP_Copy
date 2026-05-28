---
status: gaps_found
phase: 08-evolution-wiring-and-runner-debt
batch_id: 20260528T070707Z
commit_of_record: fc686da
code_under_test: committed recovery through trial skill-root wiring
acceptance_gates: 8
verified_at: 2026-05-28T07:40:44Z
verifier: codex
---

# Phase 8 Verification

Phase 8 gap-closure cannot be marked passed. The latest real DeepSeek Stage 3 rerun was launched with `--env-file .env.local --stage 3` and `set -o pipefail`; Stage 3 reached the real c=20 phase after portfolio bootstrap, but request `-6833932762567548368` failed after exhausting 4 parse attempts on malformed `factor_discovery` tool-call JSON.

This rerun shows the G2/G3 recovery path advanced beyond the previous failure:

- Stage3-only bootstrap completed the full current-code request.
- `distill_after_stage1` produced 2 delta proposals.
- Per-node evidence wrote aggregate `usage.json` plus `usage_turns.jsonl`.

It also exposed a remaining runner evidence gap: request-level `evolution_snapshot.json` files did not record the visible bootstrap portfolio, so Stage 3 snapshots still showed `delta_portfolio_before: []` and `trials: []`. A local TDD fix now writes the visible portfolio IDs at request start; this requires a rerun after DeepSeek balance is restored.

A follow-up verifier audit found a stricter blocker: trial workspaces were patched on disk, but the runtime still read production SKILL prose for model prompts. Local TDD fixes now route patched trials through an isolated temp skill root, keep baseline/control prompts on the production root, exclude baseline/control from `trials[]`, include `delta_id` on trial snapshot rows, and write artifact-derived behavioral metric lift into journal entries. This also requires a fresh real Stage 3 rerun.

Evidence:
- Run log: `.planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/runner-20260528T070707Z.log`
- Stage artifact dir: `tests/smoke/.runs/20260528T070707Z/stage3/`
- Bootstrap artifact dir: `tests/smoke/.runs/20260528T070707Z/portfolio_bootstrap/`
- Index: `tests/smoke/.runs/20260528T070707Z/stage3/index.json`
- Batch summary: `tests/smoke/.runs/20260528T070707Z/stage3/batch_summary.json`

## Truths Verification

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D8-ACC-1 Stage 3 batch completes without timeout / stale env / unhandled transient | FAIL | Batch `20260528T070707Z` reached `stage 3: n=20 concurrency=20`, then failed fast on `malformed_tool_args`; final log line says `stage 3 FAILED`. |
| 2 | F-08-B fix: every Stage 3 request has 3 production-node `messages.jsonl[0].content` entries > 100 bytes | FAIL | Stage 3 aborted after one `factor_discovery` parse failure. 19 rows completed OK, but the failed row lacks downstream node evidence. |
| 3 | F-08-C fix: copy_generation `prompt_cache_miss` mean is within [500, 5000] tokens | FAIL | 19 copy usage files; aggregate `prompt_cache_miss_tokens` mean = 16328.11, min 13770, max 18805. This is above the signed band. |
| 4 | F-08-01 fix: at least 5/20 requests trigger a trial | FAIL | 20 Stage 3 snapshots now record the visible deltas `d1_brand_register_awareness` and `d2_sensory_anchor_requirement`, but `trials[]` total remains 0. |
| 5 | F-08-D Gap 8 fix: at least one delta status transition and a portfolio journal entry | FAIL | `portfolio_journal.jsonl` is absent; `batch_summary.json.behavioral_metrics.trial_belief_update_count` = 0. |
| 6 | D8-ACC-3 retained: `failure_class` in `index.json`, and `by_failure_class` in `batch_summary.json` | PASS | `index.json` has 20 rows with `failure_class`; `batch_summary.json.by_failure_class` is `{malformed_tool_args: 1, ok: 19}`. |
| 7 | D8-ACC-5: 7 scheduled WR/IN items closed to phase-8 commit refs | FAIL | `07-WRIN-TRIAGE.md` remains scheduled/blocked; Stage 3 has not passed. |
| 8 | Manual copy-quality spot-check of 5 sampled request outputs | NOT_EVALUATED | G5 is `autonomous: false`, but Stage 3 failed before acceptance. A manual spot-check cannot turn a failed batch into passed. |

## Batch Artifact Counts

- Request dirs: 20
- `usage_turns.jsonl` files: 61
- Stage 3 snapshots: 20; all show visible `delta_portfolio_before = [d1_brand_register_awareness, d2_sensory_anchor_requirement]`
- `copy_generation` usage files: 19; aggregate `prompt_cache_miss_tokens` mean 16328.11, min 13770, max 18805
- `index.json` exists and covers 20 rows
- `batch_summary.json` exists and reports `malformed_tool_args: 1`, `ok: 19`
- `portfolio_journal.jsonl` does not exist

## Root Evidence

The failing provider response exhausted the parse retry budget:

`ProviderResponseError: Failed to parse tool_call.arguments for node factor_discovery`

The raw snippet contains an unescaped quoted phrase inside a JSON string:

`说明她对"吃进去的美丽"已产生主动兴趣`

This is a real-provider malformed tool-call-arguments failure. Unlike earlier runs, the batch now proves the Stage 3 requests saw the bootstrap portfolio, but no trial was selected before fail-fast completion.

## Gaps

1. Stage 3 fail-fast remains an acceptance blocker due to malformed DeepSeek tool-call JSON after 4 parse attempts.
2. Copy-generation cache-miss evidence is now aggregated correctly, but the observed partial-run mean remains above the signed [500, 5000] band.
3. Trial triggering still has not passed real acceptance: visible portfolio is present, but `trials[]` and journal remain empty.
4. Trial patching, baseline/control snapshot semantics, behavioral uplift logging, and 402 classification are fixed locally and covered by tests, but still require a real Stage 3 run with selected trials to prove end-to-end.
5. `07-WRIN-TRIAGE.md` cannot be closed until a new Stage 3 acceptance run passes.

## Closure

Phase 8 status: `gaps_found`.

Next action is a GSD recovery pass, not Phase 8 pass/closeout:
- commit the local snapshot visibility and 402 classification fixes after full tests pass;
- commit the trial skill-root / baseline snapshot / behavioral-uplift audit fixes after full tests pass;
- address the remaining malformed tool-call JSON pattern or decide whether this real-provider failure is an accepted external limitation;
- address trial selection pressure now that visible portfolio propagation is proven but no trials selected;
- address the copy cache-miss target band or update the signed target if the new aggregate measurement invalidates it;
- rerun real DeepSeek Stage 3 with `set -o pipefail`;
- verify successful completion, cache-miss band, non-empty real trials with `delta_id`, journal/status transitions, and behavioral uplift entries;
- only then run the locked manual spot-check and close `07-WRIN-TRIAGE.md`.
