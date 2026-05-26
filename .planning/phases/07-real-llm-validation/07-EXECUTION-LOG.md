# Phase 7 Plan 07-06 — Real-LLM Execution Log

**Run timestamp (UTC start):** 2026-05-26T11:41:36Z
**Wall-clock duration:** 1 second (Stage 1 fail-fast on the very first request)
**Exit code:** 1 (`run()` returned 1 because Stage 1 did not pass)
**Run directory:** `tests/smoke/.runs/20260526T114136Z/` (git-ignored per D-09)
**Invocation:** `python -m seers_harness.validation.runner` (single default invocation, no `--stage` flag)
**Inter-stage human checkpoint:** none (D-07 honoured — the run was a single CLI invocation)

## Per-stage results

| Stage | N planned | N executed | VAL-01 pass | VAL-02 pass | VAL-04 pass | fail-list count | reflow_triggered count | trial_selected count | Status |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | **FAIL-FAST** |
| 2 | 20 | — | — | — | — | — | — | — | not started (D-02 stop after Stage 1) |
| 3 | 20 | — | — | — | — | — | — | — | not started (D-02 stop after Stage 1) |

Stage 1 produced exactly the canonical artifact tree on disk:

```
tests/smoke/.runs/20260526T114136Z/stage1/index.json
tests/smoke/.runs/20260526T114136Z/stage1/batch_summary.json
tests/smoke/.runs/20260526T114136Z/stage1/-6834635816105165003/evolution_snapshot.json
```

Per-node `evidence/<node_id>/{messages.jsonl, tool_calls.jsonl, artifact.json, usage.json}` were NOT written for Stage 1's single request because the `factor_discovery` node failed before any provider call completed (the 401 was returned on the first request to DeepSeek), so `RecordingProvider` had no records to flush. `flush_evidence` was called inside `_run_one_request`'s `finally` block (per the writer contract from 07-02) but received an empty `request_log` and produced no JSONL files. This is the documented behaviour — partial artifacts are kept (D-02), and an empty capture log on a fail-fast first-call exception is consistent with the writer's degradation rule.

## Evolution snapshot per stage

| Stage | portfolio_before len | portfolio_after len | trials count | trial outcomes |
|---:|---:|---:|---:|---|
| 1 | 0 | 0 | 0 | none — expected per D-18 (portfolio starts empty; Stage 1 N=1 produces zero trials) |
| 2 | n/a | n/a | n/a | stage not started |
| 3 | n/a | n/a | n/a | stage not started |

Zero trials in Stage 1 is **NOT** a failure per D-18 — it is the expected baseline. The Stage 1 fail-fast was caused by a separate, prior, provider-level failure (see below); the empty-trials evidence is independent.

## Fail-fast classification (D-19)

**Stage that stopped:** Stage 1 (request 1 / 1)
**Classified label:** `infra_error` (printed by the runner: `[runner] stage 1 req -6834635816105165003: infra_error -> fail-fast`)
**Exception class actually raised at the runner boundary:** `RuntimeError`
**Truncated exception_message (≤200 chars):** `Node factor_discovery failed after 1 attempts`

### Underlying cause chain

The 401 was wrapped twice before it reached `exception_classifier.classify`:

1. `OpenAICompatibleProvider.generate_with_tools` raised
   `seers_harness.core.errors.ProviderAuthError("AuthenticationError(Error code: 401 - {'error': {'message': 'Authentication Fails, Your api key: ****92c7 is invalid', ...}})")`
   — this is the canonical DeepSeek auth failure.
2. `dag_runner._run_node` caught the `ProviderAuthError`, exhausted its attempt budget (`max_attempts=1` for that node), and re-raised
   `RuntimeError("Node factor_discovery failed after 1 attempts")` via `from last_error`.
3. `_run_one_request` let that `RuntimeError` propagate; `_run_stage` ran it through `classify(exc)`, and because `RuntimeError` is NOT in the explicit allow-list (`TrialFailure`, `ProviderRateLimitError`, `ProviderTransientError`, `ProviderAuthError`, `ProviderResponseError`), the default fallback `infra_error` was returned.

### Observation (not a fix)

The classifier's contract from 07-04 was to **never silently absorb** unknown exceptions, and the default of `infra_error` is the correct conservative behaviour. However, the routing **did NOT pierce the `dag_runner` re-raise**, so the on-disk record under-reports a `provider_error` as `infra_error`. This is a **finding for downstream review**, not a runner bug to fix in this plan — per the user's instruction to never wrapper-retry or modify the runner here, and per D-19 saying classification is by exception class only (never by message string or `__cause__` traversal). The cause chain is preserved in this log for the case-analysis step.

## Resume instruction (if the user fixes the upstream issue)

The 401 indicates DeepSeek rejected the API key whose suffix is `****92c7`. The shell-level `DEEPSEEK_API_KEY` was set (length 35), so the rejection is on DeepSeek's side, not on env-loading. To re-run after rotating the key:

```bash
# After confirming the key is valid against DeepSeek directly:
python -m seers_harness.validation.runner --stage 1   # bring-up
# then if Stage 1 passes, re-run the full pipeline:
python -m seers_harness.validation.runner             # all three stages, no checkpoint
```

This is a **re-run flag**, not an inter-stage checkpoint (D-07 still holds — the `--stage` flag is for retries after fixing a failure).

## Manual review queue

`batch_summary.json["manual_review_queue"]` for Stage 1 is **empty `[]`** — the only request fail-listed under VAL-01/02/04 carries an `exception` field, which the writer treats as a fail-list entry but not a manual-review-queue entry (the queue is reserved for VAL-03 / VAL-05 / VAL-06 navigational stratification, which requires successful artifacts to read). No node_ids are routed to D-13 manual buckets in this run because no request produced a valid artifact.

When (and only when) the pipeline produces real successful Stage-2 / Stage-3 evidence, the manual review queue will populate per D-13 / D-15 / D-16. As of this run, the queue is intentionally empty.

## VAL-03 / VAL-05 / VAL-06 verdicts

VAL-03 / VAL-05 / VAL-06 verdicts: deferred to manual case reading in `case_analysis.md` per D-13/D-14. **No verdicts are recorded here — that is structurally impossible without successful Stage-2 / Stage-3 artifacts to read.**

## Self-Check: FAILED

The plan's `<must_haves>` cannot all be confirmed against on-disk evidence:

- **`tests/smoke/.runs/<timestamp>/` exists with the full canonical artifact tree:** PARTIAL — `index.json`, `batch_summary.json`, and `evolution_snapshot.json` exist for Stage 1; per-node `evidence/<node_id>/{messages.jsonl, tool_calls.jsonl, artifact.json, usage.json}` do NOT exist (no provider call ever returned a payload to record).
- **The runner is invoked exactly once and drives Stage 1 → 2 → 3 end-to-end:** PARTIAL — invoked exactly once (CONFIRMED), but Stage 2 and Stage 3 were not driven because Stage 1 fail-fasted (D-02 contract).
- **Each stage produces its own `.runs/<ts>/` directory or a stage-named subdir:** CONFIRMED for Stage 1 (`stage1/`); not applicable for Stages 2/3 (not started).
- **`batch_summary.json` totals reflect machine-judged VAL-01/02/04 pass counts:** CONFIRMED — totals correctly read 0/0/0 with the failed node listed in all three fail-lists.
- **`evolution_snapshot.json` contains `delta_portfolio_before`, `delta_portfolio_after`, `trials[]`:** CONFIRMED — all three keys present with empty arrays (D-18 expected).
- **Zero trials in Stage 1 / early Stage 2 is recorded as expected behaviour:** CONFIRMED — recorded above as expected per D-18.
- **If any stage fails-fast, the run stops there with partial artifacts kept and the failure logged with the exception class:** CONFIRMED — Stage 1 stopped, Stages 2/3 not started, partial artifacts are on disk, exception class `infra_error` (with the underlying `RuntimeError` and the deeper `ProviderAuthError` cause chain) recorded in this log.
- **Case-analysis is NOT performed in this plan:** CONFIRMED — VAL-03/05/06 verdicts deferred per D-13/D-14.

The `must_have` that did **not** hold is the first one (full canonical artifact tree across all three stages). This is a **legitimate, expected partial** under the D-02 fail-fast contract — Stages 2 and 3 were correctly NOT started because Stage 1 did not pass.

## Closing summary

- **Total DeepSeek calls across stages:** 1 attempted, 0 successful (the single attempt returned 401 before any tool call landed).
- **Total cost (sum of per-node `usage.json` `total_tokens`):** **0** (no `usage.json` was written — the first call failed before a payload returned).
- **Trial counts per stage:** Stage 1 = 0 (expected per D-18); Stages 2/3 not started.
- **Pointer to downstream case-reading:** `.planning/phases/07-real-llm-validation/case_analysis.md` (skeleton from 07-05; cannot be populated until a successful run produces real Stage-2 / Stage-3 evidence).
