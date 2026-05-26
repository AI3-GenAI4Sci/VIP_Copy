---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-05-27T01:00:00.000Z"
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 22
  completed_plans: 21
  percent: 95
last_gate_trip: 07-06/Task2 — PARTIAL acceptance retracted by user 2026-05-27; phase reopens until post-CR-01..04 real-LLM re-run completes Stage 1 + 20/20 Stage 2 + 20/20 Stage 3, case_analysis F1..F4 judged excellent, evolution reflow events observed, and WR/IN findings closed or scheduled
---

# Project State

## Current Position

Phase: 07 (real-llm-validation) — EXECUTING (code-side ready, full real-LLM coverage pending). 4 Critical review fixes (CR-01..04) committed and pytest 251/251 holds, but the user has rescinded the prior PARTIAL acceptance of 07-06. The new bar: a fresh real-LLM run on the post-CR-01..04 code must complete Stage 1 + Stage 2 (20/20) + Stage 3 (20/20), `case_analysis.md` F1..F4 verdicts must be populated and judged excellent, the evolution mechanism must be observed firing on real runs (at least one non-empty `trials[]` in an `evolution_snapshot.json`), Stage 3 high-concurrency c=20 must actually execute on live DeepSeek, and the WR/IN advisory findings in 07-REVIEW.md must each be closed, explicitly waived, or scheduled to a follow-up phase.

- Focus: real-LLM full re-run on post-CR-01..04 code, then case-reading + evolution observation.
- Verified baseline: 251 workspace tests pass after CR-01..04 fixes (`pytest -q` returns `251 passed in 0.78s`). No skips, no new failures, no schema drift.
- Code-review remediation: 4/4 Critical findings closed atomically; Warnings (WR-01..06) and Infos (IN-01..08) **still open** under the user's revised acceptance bar.

## Completed Work

| Phase | Completed Plans | Evidence |
|---|---:|---|
| 1. Schema + Tools Foundation | 2 | `01-01-SUMMARY.md`, `01-02-SUMMARY.md` |
| 2. Single Provider Path | 2 | `02-01-SUMMARY.md`, `02-02-SUMMARY.md` |
| 3. Tool Loop + DAG Integration | 3 | `03-01-SUMMARY.md`, `03-02-SUMMARY.md`, `03-03-SUMMARY.md` |
| 4. SKILL.md Prose Rewrites | 1 | `04-SUMMARY.md` |
| 5. Cleanup, Deletes, Tests, Regression | 4 | `05-SUMMARY.md` (plans 05-01..05-04) |
| 6. Evolution Chain + Production Hardening | 5 | `06-01-SUMMARY.md` … `06-05-SUMMARY.md` |
| 7. Real-LLM Validation (in progress — code-side ready, real-LLM coverage pending) | 6 plans delivered | `07-01-SUMMARY.md` (evolution observability hooks), `07-02-SUMMARY.md` (evidence capture layer — RecordingProvider + flush_evidence), `07-03-SUMMARY.md` (batch index writers — machine_judges + index_writer + batch_summary_writer), `07-04-SUMMARY.md` (stage runner — exception_classifier + runner CLI), `07-05-SUMMARY.md` (case-analysis template), `07-06-SUMMARY.md` PARTIAL (pre-CR run only — under user's revised bar, requires a fresh post-CR-01..04 re-run); `07-REVIEW.md` 4 Critical findings remediated atomically: CR-01 c2386a7, CR-02 609020d, CR-03 9810f85, CR-04 2cd75a0; `07-VERIFICATION.md` status `gaps_found` after PARTIAL acceptance retraction (2026-05-27) |

## Active Watchlist

- **07-06 PARTIAL accepted (2026-05-27).** Stage 2 req2 fail-fasted on DeepSeek-side malformed `tool_call.arguments` JSON (truncation at char 3617 mid-string in a factor's `evidence_refs.path`). The runner's D-01/D-02/D-07/D-09/D-12/D-17/D-18/D-19/D-22 contracts held end-to-end. User explicitly accepted this outcome as a legitimate real-LLM behavioural finding (not a runner defect). The 2 successful captures plus 1 partial-on-fail-fast capture are the phase-7 evidence basis; `case_analysis.md` is the next user-driven step (outside execute-phase per D-13/D-14).

- **CR-01 (c2386a7) closes the prior "classify() cause-chain blind spot" deferred observation.** `classify()` now walks `__cause__` / `__context__` so wrapped provider exceptions (`dag_runner._run_node`'s `RuntimeError`) route to `provider_error` instead of falling into the `infra_error` default. Module docstring updated to describe the cause-chain walk; isinstance-only allow-list semantics preserved (no message-string sniffing).

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

Phase 7 reopened on 2026-05-27 after the user rescinded PARTIAL acceptance of 07-06. The next pass must run a full real-LLM re-validation on the post-CR-01..04 code:

```bash
# 1. Confirm DEEPSEEK_API_KEY is set (and the key is valid — prior run hit a 401 once)
[ -n "${DEEPSEEK_API_KEY:-}" ] || echo "ERROR: export DEEPSEEK_API_KEY first"

# 2. Sanity: code is on commit 0e7d476 or later (CR-01..04 + tracking landed)
git log --oneline -5

# 3. Full three-stage real-LLM run (~45-60 min budget; Opus reasoning ~5min/node)
python -m seers_harness.validation.runner

# 4. After the run lands evidence under tests/smoke/.runs/<ts>/, populate case-reading
$EDITOR .planning/phases/07-real-llm-validation/case_analysis.md
```

The next execute-phase invocation should drive: a fresh real-LLM run, case_analysis F1..F4 population, evolution-mechanism observation, Stage 3 c=20 confirmation, and WR/IN triage. See the prompt the user prepared for the new window for the full acceptance bar.

Phase report: `workspace/.planning/phases/07-real-llm-validation/07-VERIFICATION.md` (status `gaps_found`, override_retracted_at recorded in frontmatter).
Plan summaries: `workspace/.planning/phases/07-real-llm-validation/07-0{1..6}-SUMMARY.md`.
Code-review: `workspace/.planning/phases/07-real-llm-validation/07-REVIEW.md` — Critical CR-01..04 closed; WR-01..06 + IN-01..08 still open and in scope under the revised acceptance bar.
