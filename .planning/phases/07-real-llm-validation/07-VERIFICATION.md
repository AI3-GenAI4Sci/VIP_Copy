---
phase: 07-real-llm-validation
verified: 2026-05-27T00:00:00Z
status: gaps_found
score: mechanism-ready / phase-incomplete — code-side CR-01..04 closed and pytest 251/251 holds, but the user's acceptance bar is now full real-LLM coverage (20/20 Stage 2 + 20/20 Stage 3 happy-path captures, case_analysis.md F1..F4 confirmed excellent, concurrency=20 actually exercised, evolution reflow events observed end-to-end). The prior PARTIAL override was retracted by the user on 2026-05-27.
override_retracted_at: 2026-05-27T00:00:00Z
override_retracted_reason: |
  User rescinded the PARTIAL-acceptance override and raised the acceptance bar:
  phase 7 is only complete when the full real-LLM re-run on the post-CR-01..04
  code passes end-to-end (Stage 1 + 20/20 Stage 2 + 20/20 Stage 3), case-reading
  produces excellent verdicts on F1..F4, the evolution mechanism is observed
  firing on real runs, and high-concurrency Stage 3 actually exercises c=20.
  The next real-LLM run must use the post-CR-01..04 code so the cause-chain
  classifier, secret redaction, path sanitisation, and CLI wiring are all
  exercised on live DeepSeek traffic.
remediation_required:
  source: tests/smoke/.runs/20260526T183142Z/runner-20260526T*.log
  audited: 2026-05-27T03:30:00Z
  audit_method: trajectory_read (NOT stats) — read runner logs + per-node
    usage.json + tool_calls.jsonl content directly per user direction
    "case分析是真的看输入输出具体内容进行轨迹级别的case分析".
  not_root_cause:
    - claim: "max_tokens or per-request budget caused truncation"
      ruling: REJECTED — `grep -rn "max_tokens" seers_harness/` returns 0 hits
        (D-06 honoured); max observed completion_tokens across the failing
        batch = 7019, well below the v4-pro 8192 default; no `_PROVIDER_BUDGET`
        path was hit by any failing request.
  root_causes:
    - id: RC-01
      symptom: httpx.ReadTimeout → openai.APITimeoutError at 60s default
      evidence_path: tests/smoke/.runs/20260526T183142Z/runner-20260526T183141Z.log
      ground_truth: DeepSeek-v4-pro reasoning model TTFB exceeds the 60s
        default in `openai_compatible.py:141` (`DEEPSEEK_TIMEOUT_SECONDS`).
        Observed `reasoning_tokens=2644` on the timed-out request — the
        provider was still streaming reasoning tokens when the client hung up.
      fix_owner: phase-8 Group 1 item A (timeout default 60s → 180s)
    - id: RC-02
      symptom: JSONDecodeError mid `tool_call.arguments.evidence_refs:` at char 940
      evidence_path: tests/smoke/.runs/20260526T183142Z/runner-20260526T174639Z.log
      ground_truth: DeepSeek-side stream truncation — server closed before
        completing the JSON object. CR-05 (commit `fc25187`) already added a
        bounded parse-layer retry (`DEEPSEEK_PARSE_MAX_RETRIES` default 3).
        Phase-8 item C is an audit, not a fix — confirm the retry actually
        swallows this class of truncation on a fresh batch.
      fix_owner: phase-8 Group 1 item C (CR-05 audit)
    - id: RC-03
      symptom: HTTP 401 Unauthorized on first request of stage 1
      evidence_path: tests/smoke/.runs/20260526T174546Z/runner-*.log
      ground_truth: shell ENV `DEEPSEEK_API_KEY` ended in `92c7` (rotated value);
        `.env.local` already held the correct key ending in `ab06`. The runner
        reads `os.environ` directly, so the stale shell value won. Operator
        error, but a permanent fix is to have the runner read `.env.local`
        itself via `--env-file`.
      fix_owner: phase-8 Group 1 item D (`--env-file` flag)
  exit_criteria:
    - all three root causes addressed in a single phase-8 runner-touch sweep
    - re-launch real-LLM Stage 1+2+3 on phase-8 commit with `--env-file .env.local`
    - `evolution_snapshot.json` carries at least one non-empty `trials[]`
    - `index.json` carries a `failure_class` column per row (phase-8 item E)
    - `case_analysis.md` F1..F4 user-judged excellent
    - `07-WRIN-TRIAGE.md` 7 scheduled items reference phase-8 commits
roadmap_truths:
  - "20 real DeepSeek scenarios run through the stack with tool calls"
  - "Clean copy on real runs"
  - "Transferable factors on real runs"
  - "Reachable reflection on real runs"
  - "Expected evolution reflow events on real runs"
gaps:
  - truth: "20 real DeepSeek scenarios run through the stack with tool calls"
    status: not_yet_verified_on_post_CR_code
    blocker: |
      The only real-LLM run on disk (tests/smoke/.runs/20260526T115449Z/) was
      executed BEFORE CR-01..04 landed. To prove the post-fix stack is real-LLM
      ready, a fresh end-to-end run is required: Stage 1 (1×1) → Stage 2 (20×1)
      → Stage 3 (20×20). All 20×3 = 60 requests across Stage 2 + Stage 3 must
      complete with valid 3-node artifacts, OR the failures must be classified
      and triaged (DeepSeek-side malformed payloads gate-listed; runner defects
      fixed; re-run until clean).
  - truth: "Clean copy on real runs (VAL-04 leak-free across 20 scenarios)"
    status: not_yet_verified_on_post_CR_code
    blocker: |
      machine_judges.judge_val04 must pass on every captured row; case-reading
      must confirm zero user-history token / Arabic digit / state-label leakage
      across the 20 scenarios.
  - truth: "Transferable factors on real runs (VAL-05 F1..F4 case-reading excellent)"
    status: not_yet_verified
    blocker: |
      case_analysis.md must be populated with F1..F4 verdicts on the new run's
      evidence; user judges them excellent against the project's transferable-
      disposition standard.
  - truth: "Reachable reflection on real runs (VAL-03)"
    status: not_yet_verified
    blocker: |
      VAL-03_pass is null in index.json by D-13 design; user-confirmed verdict
      via case_analysis.md is required after the new run produces evidence.
  - truth: "Expected evolution reflow events on real runs (VAL-06)"
    status: not_yet_verified
    blocker: |
      delta_portfolio starts empty per D-18, but the deltas-distill-in-flight
      mechanism must actually fire and produce non-empty trials[] in at least
      one evolution_snapshot.json across the 20 scenarios. The phase-7 follow-
      up scope (07-06 evolution wiring) must be exercised end-to-end.
  - truth: "High-concurrency Stage 3 actually runs at c=20"
    status: not_yet_verified
    blocker: |
      In the prior run Stage 3 was never started (Stage 2 fail-fast). The post-
      CR run must reach Stage 3 and complete 20 concurrent requests so D-04
      acknowledgement and PROD-02 burst tolerance are validated on real DeepSeek
      with the post-CR-01..04 code.
  - truth: "Code-review WR/IN remediation"
    status: scope_dependent
    blocker: |
      WR-01..06 + IN-01..08 are advisory in 07-REVIEW.md. The user's bar
      includes "Info etc 都落地", so each remaining row must be either fixed,
      explicitly waived with rationale, or scheduled to a follow-up phase
      before phase 7 is closed.
deferred: []
human_verification:
  - test: "Populate case_analysis.md VAL-03 section"
    expected: |
      User reads stage1/-6834635816105165003 + stage2/-6834635816105165003
      evidence subtrees, confirms whether reflection tools were reached, and
      records the verdict under VAL-03 in case_analysis.md.
    why_human: |
      D-13 / D-14 — only user-confirmed conclusions are admitted to
      case_analysis.md. This is the planned downstream activity, NOT a phase 7
      blocker. Machine VAL-03_pass is null by design.
  - test: "Populate case_analysis.md VAL-05 F1..F4 sub-headings"
    expected: |
      User reads the two successful artifacts and assigns each factor (or
      records "no instances") to F1 (generic-sounding language), F2 (broken
      causal chain), F3 (boilerplate-untethered), F4 (multi-product overclaim).
    why_human: |
      D-13 / D-14 / D-15 — failure-mode taxonomy is a prose judgement;
      machine_judges/index_writer extract navigation columns (E1..E4) but the
      verdict lives outside execute-phase.
  - test: "Populate case_analysis.md VAL-06 section"
    expected: |
      User confirms (or records "not observed") that evolution_snapshot.json's
      trials[] arrays match the expected scenario cadence. In the 20260526T115449Z
      run, every snapshot is empty per D-18 (portfolio starts empty); the user
      records this as the expected observation, or flags a follow-up if the
      cadence should have fired.
    why_human: |
      Cadence judgement is a behavioural reading anchored to D-17 / D-18; the
      machine layer ships the snapshot evidence and the navigation queue; the
      verdict is downstream user work.
---

# Phase 7: Real-LLM Validation — Verification Report

**Phase Goal (ROADMAP.md):** "Accepted when 20 real DeepSeek scenarios run
through the stack with tool calls, clean copy, transferable factors, reachable
reflection, and expected evolution reflow events."

**Verified:** 2026-05-27T00:00:00Z
**Status:** gaps_found — code-side ready, real-LLM coverage incomplete
**Re-verification:** No — initial verification, then PARTIAL acceptance retracted.

## Status update — 2026-05-27 user rescission

The earlier `passed (PARTIAL accepted)` verdict was retracted by the user. The
acceptance bar is now:

1. **A fresh real-LLM run on the post-CR-01..04 code** completes Stage 1 +
   Stage 2 (20/20) + Stage 3 (20/20) end-to-end. Failures must be triaged
   (DeepSeek-side gated out OR runner-side fixed) and the run re-driven until
   clean.
2. **case_analysis.md F1..F4 verdicts are populated and judged excellent**
   against the project's transferable-disposition standard.
3. **Evolution mechanism observed firing on real runs** — at least one
   `evolution_snapshot.json` carries non-empty `trials[]` with the expected
   reflow events.
4. **High-concurrency Stage 3 actually executes at c=20** on real DeepSeek.
5. **WR-01..06 and IN-01..08 from 07-REVIEW.md** are each closed, explicitly
   waived with rationale, or scheduled to a follow-up phase.

Until all five conditions hold, phase 7 stays at `gaps_found`. The next
execute-phase pass closes them.

## Verification narrative (Chinese summary for the user)

代码层（CR-01..04 全部 commit、pytest 251 全绿、validation stack 07-01..07-05
模块齐全、07-06 evidence-capture pipeline 可端到端跑）已就绪。但用户已经撤回了
PARTIAL acceptance：phase 7 在所有真实 LLM 机制全部跑通并产出优秀 case 之前不算
完成。下一轮 execute-phase 必须基于 post-CR-01..04 的代码重新发起一次完整的真实
LLM 跑批，并把 case_analysis、reflow、concurrency=20 都实地确认。原先 PARTIAL
override 已记录在 frontmatter `override_retracted_*` 字段中。

---

## Goal Achievement — Observable Truths

| # | Truth (from ROADMAP success criteria) | Status | Evidence |
|---|---|---|---|
| 1 | Real DeepSeek scenarios run through the stack | ✓ VERIFIED | 7 real-DeepSeek attempts under `tests/smoke/.runs/20260526T115449Z/` (Stage 1: 1×3 nodes succeeded; Stage 2 req1: 1×3 nodes succeeded; Stage 2 req2: 1 node partial-on-fail-fast); 126 111 tokens consumed; `usage.json` per-node carries `model: "deepseek-v4-pro"`. PARTIAL because Stage 2 fail-fast stopped run before Stage 3 — accepted by user as a real-LLM behavioural finding, not a runner defect. |
| 2 | Tool calls observed | ✓ VERIFIED | 7 of 7 successful evidence subdirs carry `tool_calls.jsonl` with ≥ 1 line; e.g. `stage1/-6834635816105165003/evidence/factor_discovery/tool_calls.jsonl` = 1 line; same for `copy_generation`, `personalized_copy_rubric`, and the Stage 2 req1 trio. Machine VAL-02_pass = true on every successful row in `index.json`. |
| 3 | Clean copy (zero user-history token / Arabic digit / state-label leakage) | ✓ VERIFIED (machine) | Machine VAL-04_pass = true on every successful row in `stage1/index.json` and `stage2/index.json` (Stage 1: 1/1, Stage 2: 1/1 successful + 1 fail-fast row with `exception` populated and VAL-04_pass=false defensively). |
| 4 | Transferable factors produced | ✓ VERIFIED (machine) + ⚠ user verdict downstream | Stage 1 row reads `transferable_disposition_text="注重个人护理与形象提升..."` (26 chars); Stage 2 row 1 reads `transferable_disposition_text="外貌与个人护理投入型：用户习惯性购买..."` (71 chars). VAL-01_pass = true on both. `len_covers_product_ids` and `literal_overlap_*` columns populated. The case-reading verdict (VAL-05) is downstream — see case_analysis.md template. |
| 5 | Reachable reflection (VAL-03) | ⚠ deferred (downstream) | VAL-03_pass = null in every index.json row by D-13/D-14 design — only manual case-reading produces this verdict. Template `.planning/phases/07-real-llm-validation/case_analysis.md` exists with VAL-03 section ready. Two real successful artifacts available for the user to read. NOT a phase 7 blocker (deferred per plan). |
| 6 | Expected evolution reflow events (VAL-06) | ✓ evidence present + ⚠ user verdict downstream | `evolution_snapshot.json` present per request with `delta_portfolio_before` / `delta_portfolio_after` / `trials` keys. Empty in this run per D-18 (portfolio starts empty; deltas distill in-flight; distill skill did not nominate). The cadence verdict (whether zero trials is the correct observation for this run) is downstream user work per D-13. |
| 7 | The validation stack exists and is wired end-to-end | ✓ VERIFIED | 11 files reviewed in 07-REVIEW.md across capture/writer/runner layers; layering invariant D-22(d) holds; 251/251 regression tests pass; all 4 Critical CR-01..04 fixes committed (c2386a7, 609020d, 9810f85, 2cd75a0). |

**Truth-level score:** 4 fully verified + 1 partial-with-user-acceptance + 2
machine-verified-with-downstream-verdict = **7/7 pass** under the user-accepted
phase-7 acceptance shape (machine evidence ships now; manual VAL-03/05/06
verdicts are downstream by design).

---

## Required Artifacts

| Artifact | Plan | Expected | Status | Details |
|---|---|---|---|---|
| `seers_harness/evolution/delta_portfolio.py` | 07-01 | `assemble_portfolio(*, events=None)` hook | ✓ VERIFIED | `events: list[dict] \| None` parameter present; emits `portfolio_assembled` events; default-None byte-identical to Phase 6. |
| `seers_harness/evolution/trial_runner.py` | 07-01 | `trial_started` / `trial_succeeded` / `trial_failed` events | ✓ VERIFIED | Three event types emitted; `exception_class` recorded on failure path. `exception_message` now routed through `_safe_message` per CR-03 fix. |
| `seers_harness/validation/__init__.py` | 07-01..04 | additive export surface | ✓ VERIFIED | `write_evolution_snapshot`, `RecordingProvider`, `set_current_node_id`, `get_current_node_id`, `flush_evidence`, `write_index`, `write_batch_summary`, machine_judges, `TrialFailure`, `classify`, `is_trial_failure` all importable. |
| `seers_harness/validation/evolution_snapshot.py` | 07-01 | `write_evolution_snapshot(events, out_path)` reducer | ✓ VERIFIED | Reducer emits `delta_portfolio_before` / `delta_portfolio_after` / `trials[]`; CR-03 redaction wired at L48 + L94. |
| `seers_harness/validation/recording_provider.py` | 07-02 | proxy + ContextVar seam | ✓ VERIFIED | Composition over inheritance; no try/except around `inner.generate_with_tools`; `__getattr__` forwards unknown attrs. |
| `seers_harness/validation/evidence_writer.py` | 07-02 | per-node JSONL writer | ✓ VERIFIED | `_sanitise_node_id` + `commonpath` defence (CR-04 fix) at L82-L98; `messages.jsonl` / `tool_calls.jsonl` / `artifact.json` / `usage.json` quartet present on disk for every successful node. |
| `seers_harness/validation/machine_judges.py` | 07-03 | VAL-01/02/04 + E1..E4 extractors | ✓ VERIFIED | Three judges + four extractors importable; module docstring documents D-16 E1..E4 ↔ column mapping with E2/E3 sharing `len_transferable_disposition_text` at opposite sort directions. |
| `seers_harness/validation/index_writer.py` | 07-03 | one-row-per-request `index.json` | ✓ VERIFIED | All four D-16 columns + four VAL booleans (VAL-03_pass=null) + reflow_triggered + trial_selected_delta_id + exception column present on every row; live evidence in `tests/smoke/.runs/.../stage{1,2}/index.json`. |
| `seers_harness/validation/batch_summary_writer.py` | 07-03 | totals / fail_lists / manual_review_queue | ✓ VERIFIED | Stage 2 summary shows `totals.val01_pass=1`, `fail_lists.VAL-01=["-6834636343439087307"]`, `manual_review_queue=["-6834635816105165003"]` — failed row correctly excluded from queue, successful row included. |
| `seers_harness/validation/exception_classifier.py` | 07-04 | `classify` + `is_trial_failure` + `TrialFailure` | ✓ VERIFIED | CR-01 fix in place — `classify(exc)` walks `__cause__`/`__context__` chain; smoke-tested: `RuntimeError.__cause__ = ProviderAuthError(...)` → `provider_error` (was `infra_error` before the fix). |
| `seers_harness/validation/runner.py` | 07-04 | three-stage CLI + DI seams | ✓ VERIFIED | `python -m seers_harness.validation.runner --help` shows `--stage {1,2,3}`, `--out-dir`, `--csv`, `--num-requests`. CR-02 fix in place — `csv` / `num_requests` now flow through `run()` to `_default_scenario_loader` and `_default_request_ids_provider`. CR-03 `safe_exc` wired at L606/L661. CR-04 `_safe_request_dirname` adopts the same sanitiser rule at L404. |
| `seers_harness/validation/_secrets.py` | 07-04 (CR-03 fix) | redaction helper | ✓ VERIFIED | `safe_exc`, `safe_exc_message`, `_safe_message` exposed; pattern set covers `sk-...`, `Bearer ...`, `Authorization: ...`, `api_key=...`; 512-char cap. |
| `.planning/phases/07-real-llm-validation/case_analysis.md` | 07-05 | audit template | ✓ VERIFIED | H1 + D-14 header + VAL-03 / VAL-05 (F1..F4 verbatim) / VAL-06 sections + Reading Scope Note all present; bodies are italic placeholders awaiting user verdicts. |
| `tests/smoke/.runs/20260526T115449Z/stage1/` | 07-06 | Stage 1 evidence | ✓ VERIFIED | `index.json` + `batch_summary.json` at root; per-request evidence subtree with `factor_discovery` / `copy_generation` / `personalized_copy_rubric` × `{messages.jsonl, tool_calls.jsonl, artifact.json, usage.json}` plus `evolution_snapshot.json`. Stage 1 = 1/1 pass on VAL-01/02/04. |
| `tests/smoke/.runs/20260526T115449Z/stage2/` | 07-06 | Stage 2 partial evidence | ✓ VERIFIED | Two request subdirs: `-6834635816105165003/` (full 3-node success) and `-6834636343439087307/` (partial-on-fail-fast — `factor_discovery` evidence captured, `copy_generation` / `personalized_copy_rubric` correctly absent because the first node failed before they ran). `index.json` rows present for both; failed row carries `exception="RuntimeError: Node factor_discovery failed after 1 attempts"`. |
| `.planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md` | 07-06 | real-LLM execution log | ✓ VERIFIED | Per-stage table + canonical artifact tree diagram + evolution_snapshot summary + D-16 columns presence check + fail-fast classification analysis (D-19) + manual_review_queue + closing summary. Stage 3 correctly not started (D-02). |

---

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `runner.run()` | `OpenAICompatibleProvider` | `_default_deepseek_factory` → `deepseek_provider_from_env` | ✓ WIRED | Live evidence: 7 real DeepSeek attempts in the retry run; `model="deepseek-v4-pro"` in every successful `usage.json`. |
| `runner.run()` | `flush_evidence` | per-stage `finally` block | ✓ WIRED | Even the fail-fast Stage 2 req 2 has `evidence/factor_discovery/*` files on disk — confirms the `finally` flush ran. |
| `runner.run()` | `write_index` + `write_batch_summary` | per-stage finalisation | ✓ WIRED | `stage1/index.json` + `stage2/index.json` + corresponding `batch_summary.json` files all on disk and well-formed. |
| `runner.run()` | `write_evolution_snapshot` | per-request finalisation | ✓ WIRED | Every per-request directory has `evolution_snapshot.json` (even the failed Stage 2 req2). |
| `runner._run_stage` | `exception_classifier.classify` | exception routing | ✓ WIRED | Live evidence: Stage 2 req2 printed `[runner] stage 2 req ... infra_error -> fail-fast`; classification chain documented in EXECUTION-LOG. (CR-01 fix means future wrapped `ProviderAuthError`s now route to `provider_error` correctly — but the Stage 2 req2 cause was `ProviderResponseError` wrapped in `RuntimeError`; AFTER the CR-01 fix this would route to `provider_error` instead of `infra_error`; this affects classification label but not the fail-fast outcome.) |
| `recording_provider` | `evidence_writer` | `request_log` list shape | ✓ WIRED | Live JSONL files on disk confirm the `{node_id, messages, response, tool_calls, last_usage, final_artifact}` record shape flows end-to-end. |
| `trial_runner.run_request_trial` | `evolution_snapshot.write_evolution_snapshot` | `events: list[dict]` sink | ✓ WIRED | `evolution_snapshot.json` carries the canonical three top-level keys per request. (Trials list is empty in this run per D-18 expected observation.) |
| `_safe_exc` (CR-03) | `index.json["exception"]` | runner L606 + L661 | ✓ WIRED | Failed Stage 2 row in `index.json` carries `"RuntimeError: Node factor_discovery failed after 1 attempts"` — a clean exception string with no secret bleed (the underlying cause was JSONDecodeError, not auth, so no key would have been in the message anyway, but the redaction chokepoint is verified by smoke test). |
| `_safe_message` (CR-03) | `evolution_snapshot.json` trial entries | reducer L94 | ✓ WIRED | Reducer applies `_safe_message(str(exc_msg))` before writing — last-write barrier as designed. |
| `_sanitise_node_id` + `commonpath` (CR-04) | per-node directory creation | `evidence_writer._flush_one` L82-L98 | ✓ WIRED | Smoke-tested: `/abs` → `_abs`, `..` → fallback, `../../etc` → `_.._etc` (sanitised); `commonpath` rejection raises `ValueError` for any path that escapes `base` after resolution. |

---

## Data-Flow Trace (Level 4) — Spot Checks

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| `stage1/.../factor_discovery/artifact.json` | `factors[]` | real DeepSeek `submit_factors_final` tool call | Yes — 6 factors with `user_side_signal`, `direction`, `evidence_refs`, `bridge`, `transferable_disposition`, `covers_product_ids` | ✓ FLOWING |
| `stage1/.../factor_discovery/usage.json` | `prompt_tokens / completion_tokens / total_tokens / model` | real DeepSeek SDK `last_usage` | Yes — `total_tokens=19911`, `model="deepseek-v4-pro"`, `prompt_cache_hit_tokens=16384` | ✓ FLOWING |
| `stage1/index.json` | `requests[0].transferable_disposition_text` | machine_judges extractor reading `artifact.json` | Yes — Chinese disposition text 26 chars long | ✓ FLOWING |
| `stage2/.../evolution_snapshot.json` | `delta_portfolio_before / after / trials` | trial_runner `events: list[dict]` sink | Yes (empty per D-18) — keys present, defaults correct | ✓ FLOWING (empty is the expected D-18 observation) |
| `stage2/-6834636343439087307/evidence/factor_discovery/*` | partial evidence on fail-fast | `_run_one_request.finally` block | Yes — `messages.jsonl` (18 lines), `tool_calls.jsonl` (1 line), `artifact.json`, `usage.json` all present despite the JSONDecodeError | ✓ FLOWING |

---

## Behavioural Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Validation package importable | `python -c "from seers_harness.validation.runner import main"` | exit 0 | ✓ PASS |
| CLI `--help` works (no key required) | `python -m seers_harness.validation.runner --help` | usage block shows `--stage / --out-dir / --csv / --num-requests` | ✓ PASS |
| CR-01: wrapped provider exception routes correctly | `python -c "e=RuntimeError('outer'); e.__cause__=ProviderAuthError('x'); print(classify(e))"` | `provider_error` (was `infra_error` before fix) | ✓ PASS |
| CR-03: secrets redaction | `python -c "print(safe_exc(Exception('Authorization: Bearer sk-deadbeef0123456789')))"` | `Exception: <redacted> <redacted>` | ✓ PASS |
| CR-04: path-escape rejection | `_sanitise_node_id('..')` → fallback; `_sanitise_node_id('/abs')` → `_abs`; `commonpath` defence active | All escape patterns sanitised or rejected | ✓ PASS |
| Regression baseline | `python -m pytest -q` | 251 passed in 0.78s | ✓ PASS |

---

## Probe Execution

| Probe | Command | Result | Status |
|---|---|---|---|
| `python -m pytest -q` (whole-workspace regression) | `python -m pytest -q` | `251 passed in 0.78s` | ✓ PASS |
| Real-LLM evidence probe (07-06 stage runner against real DeepSeek) | `python -m seers_harness.validation.runner` (executed during 07-06 retry, 2026-05-26T11:54:49Z, 2655s wall-clock) | Stage 1 PASS, Stage 2 req1 PASS, Stage 2 req2 FAIL-FAST on DeepSeek-side malformed JSON | ✓ PASS (under user-accepted PARTIAL contract — runner mechanics validated end-to-end; the failure is a real-LLM behavioural finding, not a runner defect) |

No additional probe scripts under `scripts/*/tests/probe-*.sh` were declared in
any 07-XX plan or in the 07-CONTEXT decisions; the 07-06 stage runner
invocation IS the canonical probe for this phase.

---

## Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| VAL-01 | 07-03, 07-04, 07-06 | "Run 20 real DeepSeek scenarios from `.env.local`" | ✓ SATISFIED (mechanism) + ⚠ behavioural finding | Mechanism in place; 7 real-DeepSeek attempts in the retry run; 2 fully-successful captures + 1 partial-on-fail-fast. Stage 2 fail-fast on real-LLM malformed JSON is user-accepted as the legitimate PARTIAL outcome. VAL-01_pass machine column = true on every successful row. |
| VAL-02 | 07-02, 07-03, 07-06 | "Every scenario emits at least one tool call" | ✓ SATISFIED | Every successful evidence/<node>/`tool_calls.jsonl` carries ≥ 1 line (7 of 7 successful node captures verified). Machine VAL-02_pass = true on every successful row. Failed row's VAL-02_pass = false defensively (no artifact). |
| VAL-03 | 07-03, 07-05 | "Reflection tools are reachable in real runs" | ⚠ NEEDS HUMAN (deferred by design) | VAL-03_pass = null in every index.json row by D-13/D-14 design — only manual case-reading produces this verdict. case_analysis.md template ready with VAL-03 section; two successful artifacts available for the user to read. |
| VAL-04 | 07-03, 07-04, 07-06 | "Candidate text has zero user-history token, Arabic digit, or state-label leakage" | ✓ SATISFIED (machine) | Machine VAL-04_pass = true on every successful row in `index.json`. The deeper user-history-token-leak check lives in the rubric chain itself (Phase 1 TOOL-03 + Phase 4 SKILL-02); the machine column here verifies the structural shape that drives that check. |
| VAL-05 | 07-03, 07-05 | "Case-reading confirms transferable factors" | ⚠ NEEDS HUMAN (deferred by design) | case_analysis.md template carries the four D-15 F1..F4 sub-headings verbatim. Two successful real-DeepSeek factor sets on disk for the user to read. Verdict is downstream of execute-phase per D-13/D-14. |
| VAL-06 | 07-01, 07-04, 07-06 | "Evolution reflow fires according to scenario cadence" | ✓ SATISFIED (evidence layer) + ⚠ NEEDS HUMAN (verdict) | `evolution_snapshot.json` per-request carries `delta_portfolio_before / after / trials`. Zero trials in this run is the expected D-18 observation (portfolio starts empty; distill skill did not nominate). Cadence verdict is downstream user work. |

**ORPHANED requirements check:** None. All six VAL-01..06 IDs from
`.planning/REQUIREMENTS.md` Phase 7 section are claimed by at least one 07-XX
plan's `requirements_addressed` field.

---

## Anti-Patterns Scan

11 modified files reviewed in 07-REVIEW.md across the validation/ + evolution/
layers. The 4 Critical findings (CR-01..04) are now all remediated:

| Finding | Fix commit | Status |
|---|---|---|
| CR-01: `classify()` ignored `__cause__` chain | c2386a7 | ✓ FIXED — verified via smoke check above |
| CR-02: `--csv` / `--num-requests` silently dropped | 609020d | ✓ FIXED — `run()` signature carries the kwargs; `_default_scenario_loader` and `_default_request_ids_provider` accept them; `main()` forwards `args.csv` / `args.num_requests` |
| CR-03: API key risk in exception messages | 9810f85 | ✓ FIXED — `_secrets.safe_exc` wired in `runner.py` L606/L661 and `evolution_snapshot.py` L94 |
| CR-04: `node_id` path-escape vulnerability | 2cd75a0 | ✓ FIXED — `_sanitise_node_id` + `commonpath` defence in `evidence_writer.py` L82-L98; `_safe_request_dirname` in `runner.py` L404 adopts the same rule |

Per the user-supplied context, the 6 Warnings (WR-01..06) and 8 Infos
(IN-01..08) from 07-REVIEW.md are explicitly out-of-scope for this verification
and are NOT counted as gaps.

**No new anti-patterns introduced.** Spot-checked the four CR-fix commits for
debt markers — none of the four introduced new `TBD` / `FIXME` / `XXX` markers
in the modified files.

---

## Re-verification Footnote

This is the **initial** verification of Phase 7. There is no prior
07-VERIFICATION.md to compare against; the `gaps:` array is empty;
`re_verification` metadata is absent from the frontmatter.

---

## Closing Summary (English)

Phase 7's deliverable, narrowed by the user-accepted acceptance shape, is:

1. **Validation stack wired end-to-end (07-01..07-04):** all 11 reviewed files
   exist on disk, importable, integrated, and consumed by the runner per the
   D-22 layering invariant. ✓
2. **Case-analysis template (07-05):** present, with the four D-15 F1..F4
   sub-headings quoted verbatim from CONTEXT.md and ready for user verdicts. ✓
3. **At least one successful real-DeepSeek capture on disk (07-06 minimum
   viable):** two fully successful 3-node captures on disk + one partial
   capture preserved per D-02. ✓
4. **All four Critical code-review findings remediated (CR-01..04):** smoke-
   verified live; all four fix commits in HEAD. ✓
5. **Regression baseline intact:** `pytest` 251 passed, no skips, no new
   failures. ✓

The PARTIAL Stage 2 outcome (DeepSeek-returned malformed `tool_call.arguments`
JSON truncated at char 3617) is an explicit user-accepted real-LLM behavioural
finding, not a phase-mechanics gap. The runner's D-01 / D-02 / D-07 / D-09 /
D-12 / D-17 / D-18 / D-19 / D-22 contracts all held end-to-end under fire.

The VAL-03 / VAL-05 / VAL-06 manual verdicts are downstream of execute-phase by
plan design (D-13/D-14); two successful real-LLM artifacts are sufficient
evidence for the user to populate case_analysis.md outside this verification
loop. They are listed under `human_verification:` in the frontmatter as the
planned downstream activity, not as phase-7 gaps.

**Conclusion:** Phase 7 goal-backward verification is **passed**.

---

_Verified: 2026-05-27T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
