---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-05-26T12:45:00.000Z"
progress:
  total_phases: 7
  completed_phases: 2
  total_plans: 16
  completed_plans: 17
  percent: 35
last_gate_trip: 07-06/Task2 retry (Stage 2 fail-fast on real-LLM malformed tool_call.arguments JSON — DeepSeek truncation at char 3617, classified `infra_error` per D-19; runner mechanics held)
---

# Project State

## Current Position

Phase: 07 (real-llm-validation) — EXECUTING (07-06 PARTIAL after retry)
Plan: 6 of 6 attempted; 07-06 PARTIAL — retried after the prior 401, the new run completed Stage 1 (PASS) and Stage 2 req 1 (PASS), then fail-fasted on Stage 2 req 2 (`-6834636343439087307`) when DeepSeek returned malformed `tool_call.arguments` JSON truncated at char 3617 mid-string in a factor's `evidence_refs.path`. `_parse_args` raised `ProviderResponseError`; `dag_runner` re-wrapped as `RuntimeError`; `_run_stage` classified as `infra_error` per D-19; Stage 3 was correctly not started per D-02. The full canonical artifact tree is on disk under `tests/smoke/.runs/20260526T115449Z/`: 2 fully successful per-request evidence captures (Stage 1 `-6834635816105165003`, Stage 2 `-6834635816105165003`) plus 1 partial-on-fail-fast capture for the malformed-JSON failure. Wall-clock 2655s (~44m15s), 126 111 tokens consumed, >99% prompt-cache hit rate per node. The runner's D-01/D-02/D-07/D-09/D-12/D-17/D-18/D-19/D-22 contracts ALL held; what fail-fasted was a real-LLM payload-shape behavioural finding, not a runner defect. The 2 successful artifacts are sufficient for the downstream case-reader to begin populating `case_analysis.md` per D-13/D-14. Resume: either gate-out the malformed-JSON request and rerun `--stage 2` then `--stage 3`, OR begin manual case-reading on the existing artifacts (case-reading is outside execute-phase).

- Focus: Real-LLM Validation (VAL-01..06) at batch 20 against DeepSeek `/beta`.
- Status: 07-04 (stage-runner) complete 2026-05-26 — `seers_harness/validation/exception_classifier.py` (D-19 three-label router: `TrialFailure`/`classify`/`is_trial_failure`, isinstance allow-list, `infra_error` default never silently absorbs) and `seers_harness/validation/runner.py` (CLI `python -m seers_harness.validation.runner` with optional `--stage {1,2,3}` running default Stage 1→2→3 end-to-end with NO inter-stage human checkpoint per D-07; matrix `{1: (1,1), 2: (20,1), 3: (20,20)}` per D-01; fail-fast at request level per D-02; max_retries=3 on the underlying OpenAI client only per D-03 with no wrapper retry; no token cap per D-06; empty `delta_portfolio` at process start per D-18; trial isolation reused via `apply_delta_patch_temporarily` per D-21; output under `tests/smoke/.runs/<ts>/` per D-09; Stage 3 one-shot c=20 with PROD-02 rationale and D-04 rate-mask acknowledgement verbatim in module docstring). Validation package `__init__.py` extended additively. Wave 3 (07-04) complete; only 07-06 (real-LLM execution + evidence, autonomous=false) remains.
- Verified baseline: 251 workspace tests pass (1 skipped) after Phase 6, unchanged after 07-01, 07-02, 07-03, and 07-04.

## Completed Work

| Phase | Completed Plans | Evidence |
|---|---:|---|
| 1. Schema + Tools Foundation | 2 | `01-01-SUMMARY.md`, `01-02-SUMMARY.md` |
| 2. Single Provider Path | 2 | `02-01-SUMMARY.md`, `02-02-SUMMARY.md` |
| 3. Tool Loop + DAG Integration | 3 | `03-01-SUMMARY.md`, `03-02-SUMMARY.md`, `03-03-SUMMARY.md` |
| 4. SKILL.md Prose Rewrites | 1 | `04-SUMMARY.md` |
| 5. Cleanup, Deletes, Tests, Regression | 4 | `05-SUMMARY.md` (plans 05-01..05-04) |
| 6. Evolution Chain + Production Hardening | 5 | `06-01-SUMMARY.md` … `06-05-SUMMARY.md` |
| 7. Real-LLM Validation (in progress) | 5 | `07-05-SUMMARY.md` (case-analysis template), `07-01-SUMMARY.md` (evolution observability hooks), `07-02-SUMMARY.md` (evidence capture layer — RecordingProvider + flush_evidence), `07-03-SUMMARY.md` (batch index writers — machine_judges + index_writer + batch_summary_writer), `07-04-SUMMARY.md` (stage runner — exception_classifier + runner CLI); `07-06-SUMMARY.md` PARTIAL (retry — Stage 1 PASS + Stage 2 partial fail-fast on real-LLM malformed JSON; 2 successful real-DeepSeek artifacts + 1 partial-on-fail-fast capture on disk under `tests/smoke/.runs/20260526T115449Z/`; runner D-01/D-02/D-07/D-09/D-12/D-17/D-18/D-19/D-22 contracts held end-to-end under both 401 and malformed-JSON failure modes) |

## Active Watchlist

- **07-06 PARTIAL retry — Stage 2 fail-fasted on real-LLM malformed `tool_call.arguments` JSON for request `-6834636343439087307`.** DeepSeek returned a truncated payload at char 3617 mid-string in a factor's `evidence_refs.path`; `_parse_args` raised `ProviderResponseError`; `dag_runner` re-wrapped as `RuntimeError`; `classify(exc)` routed to `infra_error` (D-19 default). Stage 3 was correctly not started per D-02. The deeper `ProviderResponseError` cause chain is preserved in `07-EXECUTION-LOG.md` for downstream audit. Resume options: (a) gate-out the bad request_id and rerun `--stage 2` then `--stage 3`; (b) harden `_parse_args` to tolerate truncated tool_call.arguments (Phase 7 follow-up, not 07-06 scope); (c) begin manual case-reading on the 2 existing successful artifacts (`stage1/-6834635816105165003`, `stage2/-6834635816105165003`).

- **Deferred observation: classify() under-reports both `ProviderAuthError` and `ProviderResponseError` as `infra_error`** when the cause is wrapped by `dag_runner._run_node` into a `RuntimeError`. Validated under TWO real-LLM failure paths now (prior 401 + this run's malformed-JSON). Per D-19 ("classification is by exception class only, never the message string, never the cause chain") this is the correct contracted behaviour, but it makes the on-disk label diverge from the true upstream cause. The full cause chain is preserved in the EXECUTION-LOG so auditors can recover the truth. **Tagged as a future review point**, not a fix for 07-06 — patching it would violate the 07-04 contract.

- **Real-LLM cost calibration finding (07-06 retry): `deepseek-v4-pro` reasoning-model latency is ~5min per node, ~15min per 3-node request, ~44min for ~7 attempted calls.** Original 10-25 min budget estimate was based on `deepseek-chat`-class latencies. Phase 7 follow-up budgets should plan for ~15min per 3-node request, NOT a full-pipeline 10-25min envelope. Prompt-cache hit rate >99% per node — real cost is dominated by completion + reasoning tokens, not prompt setup.

- Phase 7 stage 3 (real concurrency target=20) may surface real DeepSeek
  rate-limit ceilings that Phase 6's PROD-02 fact-recording probe did not
  see at FakeProvider load. Plan must accept that `max_retries=3` masks
  per-call ceilings — this is observation, not stabilisation.

- Phase 6 evolution observability hooks (trial selection, reflow event,
  portfolio before/after) are now exposed as a thin `events: list[dict] | None`
  seam on `assemble_portfolio` and `run_request_trial` (07-01 complete) plus
  the `write_evolution_snapshot` reducer in `seers_harness.validation`. The
  default-None paths preserve Phase 6 behaviour byte-identically; downstream
  plans (07-03 / 07-04) consume the events to build per-request
  `evolution_snapshot.json` evidence.

- Phase 7 evidence-capture layer (07-02 complete) — `RecordingProvider`
  is the content-neutral proxy that the stage runner (07-04) wraps around
  `OpenAICompatibleProvider`; it appends one captured record per
  `generate_with_tools` call into a shared `request_log`. `flush_evidence`
  materialises the canonical per-node `messages.jsonl` / `tool_calls.jsonl` /
  `artifact.json` / `usage.json` layout — all four files use
  `ensure_ascii=False` so Chinese reasoning_content is human-legible during
  case analysis.

- Phase 7 batch index writers (07-03 complete) — `machine_judges` exposes
  pure VAL-01/02/04 judges plus the four D-16 column extractors.
  `index_writer.write_index(...)` materialises `index.json` with one row
  per request carrying `len_covers_product_ids` (E1, sort desc),
  `len_transferable_disposition_text` (SHARED column for E2 sort asc and
  E3 sort desc — same column at opposite directions per D-16),
  `transferable_disposition_text` (raw-text passthrough — NOT an
  E-dimension), `literal_overlap_user_signal_vs_transferable_disposition`
  (E4, sort desc) plus VAL-01/02/04 booleans (VAL-03 is `null` per
  D-13/D-14), `reflow_triggered` (D-12), `trial_selected_delta_id`
  (D-10), and an exception passthrough. `batch_summary_writer` aggregates
  totals, per-VAL fail_lists, and a bounded `manual_review_queue`
  (D-13/D-12/D-10 union, capped at 30 with `<truncated: N more>` sentinel
  per D-16 reading scope). Writer layer is isolated from the 07-02
  capture layer (D-22d): zero imports of `recording_provider` /
  `evidence_writer` in the three new files.

- Phase 7 stage runner (07-04 complete) — `seers_harness/validation/runner.py`
  exposes the CLI `python -m seers_harness.validation.runner [--stage {1,2,3}]
  [--out-dir PATH] [--csv PATH] [--num-requests N]`. Default invocation
  runs Stage 1 → 2 → 3 end-to-end with NO inter-stage human checkpoint
  (D-07); matrix is `{1: (1,1), 2: (20,1), 3: (20,20)}` per D-01;
  Stage 3 runs concurrency=20 one-shot (PROD-02 rationale + D-04
  rate-mask acknowledgement in module docstring). Fail-fast at request
  level (D-02); provider-side max_retries=3 only (D-03), no wrapper
  retry; no token cap (D-06); empty `delta_portfolio` at process start
  (D-18); trial isolation reused via `apply_delta_patch_temporarily`
  (D-21); output under git-ignored `tests/smoke/.runs/<ts>/` (D-09).
  Provider injection: `provider_factory` + `scenario_loader` +
  `nodes_factory` + `request_ids` are DI seams — tests inject fakes
  without monkey-patching; the runner does NOT bake any DEEPSEEK_API_KEY
  into source. `seers_harness/validation/exception_classifier.py`
  exports `classify(exc) -> "trial_failure" | "provider_error" |
  "infra_error"`, `is_trial_failure(exc)`, and the `TrialFailure`
  sentinel — D-19 three-label router with explicit isinstance allow-list
  and `infra_error` default that never silently absorbs.

- `harness-runtime/` remains untouched until reviewed release promotion.

## Deferred

| Item | Reason |
|---|---|
| Real-DeepSeek concurrency tuning / circuit-breaker / rate-limit absorber | Phase 7 stage 3 only observes; tuning is a follow-up phase. |
| Trial isolation upgrade to git worktree | Pre-deployment ADR review; current `shutil.copytree` mechanism meets Phase 7 audit needs. |
| Hand/eye/mirror taxonomy review | ADR-01-PRINCIPLE-01 review candidate; not Phase 7 scope. |
| Fuzzy-match / cross-request cluster sampling for VAL-05 | E5(a)/(b) deferred; E1-E4 are the locked extreme-sample dimensions. |
| Reference v2 emitter implementation | Phase 6 designs v2 only; emitter work is post-Phase 7. |
| In-tree canonical run archival | Raw `.runs/` are local-only per Phase 7 D-09; revisit if case-reading needs it. |

## Resume Instruction

The 07-06 retry produced 2 real successful artifacts plus 1 partial-on-fail-fast capture. To advance the phase, the user picks ONE of:

```
# Option A — gate out the malformed-JSON request and rerun Stage 2 + Stage 3 only
# (e.g. by passing an explicit request_id list excluding -6834636343439087307)
python -m seers_harness.validation.runner --stage 2
python -m seers_harness.validation.runner --stage 3

# Option B — begin manual case-reading immediately on the 2 successful artifacts
# (this lives outside execute-phase per D-13 / D-14)
$EDITOR .planning/phases/07-real-llm-validation/case_analysis.md
```

Resume file: `workspace/.planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md` (full retry record + cause chain).
Plan summary: `workspace/.planning/phases/07-real-llm-validation/07-06-SUMMARY.md` (PARTIAL after retry).
