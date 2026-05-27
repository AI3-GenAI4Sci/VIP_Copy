---
phase: 8
slug: evolution-wiring-and-runner-debt
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-05-27
---

# Phase 8 — Validation Strategy

> Per-phase validation contract. Phase 8 has THREE validation layers:
> single-layer pytest verification is **insufficient** for acceptance —
> see 08-CONTEXT.md `D8-VAL-REAL` and 08-RESEARCH.md §5.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing repo standard) |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `pytest -q tests/test_validation_runner.py tests/test_trial_runner_smoke.py tests/test_provider_openai_compatible.py tests/test_exception_classifier.py tests/test_index_writer.py tests/test_batch_summary_writer.py` |
| **Full suite command** | `pytest -q` |
| **Real-LLM batch command** | `python -m seers_harness.validation.runner --env-file .env.local` |
| **Estimated runtime (full pytest)** | ~30-60 seconds |
| **Estimated runtime (real-LLM Stage 1+2+3)** | ~50-90 minutes (Stage 1 ~5min, Stage 2 ~20min, Stage 3 ~25-65min depending on rate-limit hits) |

---

## Sampling Rate

- **After every task commit:** Run quick-run command (subset above) — < 10 seconds
- **After every plan wave:** Run full pytest suite — < 60 seconds
- **Before phase 8 validation gate:** Full pytest green AND one complete real-LLM Stage 1+2+3 batch on the final phase-8 commit
- **Max pytest feedback latency:** 60 seconds
- **Max real-LLM feedback latency:** 90 minutes per batch

**Critical:** pytest passing alone does NOT close phase 8. Per `D8-VAL-REAL`,
every deliverable must have observable evidence in a real-LLM batch trace —
see Per-Task Verification Map below.

---

## Per-Task Verification Map

Phase 8 has no phase-specific REQ-IDs (it is an unblocker phase). The
verification map is keyed by deliverable (A-G items from 08-CHARTER.md).
"Real-LLM Evidence" column lists which trace artifact in
`tests/smoke/.runs/<phase-8-ts>/` proves the deliverable is firing.

| Item | Plan (TBD by planner) | Wave | Acceptance Bar | Test Type | Pytest Evidence | Real-LLM Evidence | Status |
|------|------|------|----------------|-----------|-----------------|-------------------|--------|
| **A** timeout 60→180s | 08-A | 1 | D8-A | unit | `test_provider_timeout_default_180s` | `usage.json` total ≥ 60s on at least one request, no `APITimeoutError` raised before 180s | ⬜ |
| **B** transient retry 5s/15s | 08-B | 5 | D8-B | unit + real | `test_runner_retries_transient_twice_then_succeeds`, `test_runner_does_not_retry_auth_error`, `test_runner_exhausts_transient_budget` | `.run-logs/runner-<ts>.log` contains `transient (attempt N/3); backoff=Ns`; if no natural transient, requires fault-injection request | ⬜ |
| **C** CR-05 audit | 08-C | post-batch | D8-C | manual | (audit reads logs, no test) | `parse_retry node=... attempt=N/M` log line + final request resolved (success OR `provider_error` fail-fast) | ⬜ |
| **D** `--env-file` | 08-D | 1 | D8-D | unit | `test_env_file_overrides_existing_env`, `test_env_file_does_not_log_values`, `test_env_file_handles_comments_and_blank`, `test_env_file_missing_raises`, `test_env_file_no_shell_expansion` | log lines `env-file: loaded N keys from .env.local` + `DEEPSEEK_API_KEY suffix=****<4chars>`; no value strings in any log | ⬜ |
| **E** `failure_class` column | 08-E | 1 | D8-E | unit + real | `test_failure_class_mapping`, `test_index_writer_includes_failure_class`, `test_batch_summary_by_failure_class` | every `index.json` row has `failure_class` ∈ {ok, auth, rate_limit, transient, malformed_tool_args, schema_violation, runner_bug}; `batch_summary.json.by_failure_class` value sum == `totals.requests` | ⬜ |
| **F** evolution wiring | 08-F | 4 | D8-F1, D8-F2, D8-F3, D8-ACC-2 | unit + real | `test_runner_fires_trial_when_portfolio_nonempty`, `test_runner_skips_trial_when_portfolio_empty`, `test_runner_trial_failure_does_not_abort_host`, `test_seed_patch_hash_validation_drift` | at least one `evolution_snapshot.json` has non-empty `trials[]`; `trial_succeeded` event present; `index.json` has `trial_selected_delta_id == "phase-8-seed-001"` on at least one row | ⬜ |
| **WR-01** Stage 3 drain | 08-WR-01 | 6 | D8-G-WR-01 | unit + (conditional real) | `test_stage3_fail_fast_drains_inflight` | IF Stage 3 fail-fast occurs naturally: `len(index.json.requests) == 20` AND disk `stage3/<rid>/` count == 20; ELSE pytest is sole evidence | ⬜ |
| **WR-02** finally best-effort | 08-WR-02 | 6 | D8-G-WR-02 | unit | `test_finally_writer_failure_does_not_mask_original` | pytest is sole evidence (rare in real batch) | ⬜ |
| **WR-03** delete dup `_detect_delimiter` | 08-WR-03 | 2 | D8-G-WR-03 | grep | `grep -c "_detect_delimiter" seers_harness/validation/runner.py == 0` | N/A (pure cleanup) | ⬜ |
| **WR-04** callsite | 08-WR-04 | 2 | D8-G-WR-04 | grep | `grep -c "_current_node_id as _cv" seers_harness/validation/runner.py == 0` | N/A (pure cleanup) | ⬜ |
| **WR-05** trial exception narrowing | 08-WR-05 | 6 | D8-G-WR-05 | unit + (conditional real) | `test_trial_runner_reraises_provider_errors` | IF a provider error occurs during trial in real batch: `provider_error -> fail-fast` log line + NO `trial_failed` event with provider exception class; ELSE pytest is sole evidence | ⬜ |
| **IN-01** token_cost_observed | 08-IN-01 | 4 (with F) | D8-G-IN-01 | unit + real | `test_trial_outcome_token_cost_from_trace_usage` | `evolution_snapshot.json.trials[*].token_cost_observed > 0` on at least one request | ⬜ |
| **IN-08** max_retries kwarg | 08-IN-08 | 2 | D8-G-IN-08 | grep | `grep -c "_PROVIDER_BUDGET_KEY" seers_harness/validation/runner.py == 0` AND `grep -c "deepseek_provider_from_env(max_retries=3)" seers_harness/validation/runner.py == 1` | N/A (pure cleanup) | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · 🔍 audit-pending (real-LLM batch)*

**Wave numbers** above are RESEARCH.md's recommendation (§7.2). Planner
adjusts as needed but must respect: F before IN-01; F before B; F before
WR-01/02/05.

---

## Wave 0 Requirements

Phase 8 has no Wave 0 stub-creation needs — the runner-touch sweep
modifies existing files. All target test files already exist:

- ✅ `tests/test_validation_runner.py` — phase-7 baseline
- ✅ `tests/test_trial_runner_smoke.py` — phase-6 baseline
- ✅ `tests/test_provider_openai_compatible.py` — phase-2 baseline
- ✅ `tests/test_exception_classifier.py` — phase-7 baseline
- ✅ `tests/test_index_writer.py` — phase-7 baseline
- ✅ `tests/test_batch_summary_writer.py` — phase-7 baseline

New tests are added to existing files (not new test modules) — Wave 0
trivially satisfied.

---

## Manual-Only Verifications

| Behavior | Acceptance Bar | Why Manual | Test Instructions |
|----------|----------------|------------|-------------------|
| Real-LLM Stage 1+2+3 batch end-to-end | D8-ACC-1 | Requires real DeepSeek calls (~50-90 minutes, costs tokens) | Run `python -m seers_harness.validation.runner --env-file .env.local` on the final phase-8 commit. Watch for: zero requests dropped to 60s timeout / shell-env / unhandled transient. |
| Evolution `trials[]` non-empty | D8-ACC-2 | Validates F wiring against real provider | After batch completes, run `find tests/smoke/.runs/<ts>/ -name evolution_snapshot.json -exec python -c "import sys,json; d=json.load(open(sys.argv[1])); print(sys.argv[1], 'trials:', len(d.get('trials',[])))" {} \;`. At least one request must have `trials: ≥ 1`. |
| `failure_class` per row + aggregation | D8-ACC-3 | Validates E against real failure mix | After batch, jq each `stage{N}/index.json` for `failure_class` field on every row. jq each `stage{N}/batch_summary.json` for `by_failure_class` dict. Sum == `totals.requests`. |
| CR-05 audit | D8-C | Audit, not implementation — reads log + classifies outcome | When a `tool_call.arguments` truncation appears in the batch, grep `parse_retry` log lines, confirm bounded retry behaved per `openai_compatible.py:73-103`. |
| `07-WRIN-TRIAGE.md` move 7 items to phase-8 commit refs | D8-ACC-5 | Doc hygiene — reflects what landed | After all phase-8 commits land, edit `07-WRIN-TRIAGE.md` table: replace "scheduled (phase 8)" with the phase-8 commit SHA per item. |

---

## Validation Sign-Off

- [ ] All deliverables have pytest `<automated>` verify (✅ all rows in map have a Pytest Evidence column entry)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (✅ no Wave 0 needs)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for pytest
- [ ] **Real-LLM batch evidence collected on the final phase-8 commit**
- [ ] **Real-LLM batch's `evolution_snapshot.json` has non-empty `trials[]` (D8-ACC-2)**
- [ ] **Real-LLM batch's `index.json` has `failure_class` per row (D8-ACC-3)**
- [ ] **Real-LLM batch ran via `--env-file .env.local` with no shell `export` (D8-D verification)**
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — set after the final phase-8 commit's real-LLM batch lands evidence under `tests/smoke/.runs/<phase-8-ts>/`.
