---
status: blocked_on_phase_8
phase: 07-real-llm-validation
source: [07-01-SUMMARY.md, 07-02-SUMMARY.md, 07-03-SUMMARY.md, 07-04-SUMMARY.md, 07-05-SUMMARY.md, 07-06-SUMMARY.md]
started: 2026-05-27T02:44:24Z
updated: 2026-05-27T03:55:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 11
name: Phase 7 acceptance — Stage 3 evidence
expected: |
  Stage 3 must complete 20/20 concurrent requests at c=20 against real DeepSeek.
  Currently BLOCKED — last real-LLM batch (20260526T183142Z) tripped on 60s
  ReadTimeout in Stage 2 before reaching Stage 3. Phase 8 must land first
  (timeout 180s + --env-file + transient retry + failure_class).
awaiting: phase-8 landing, then real-LLM re-run

## Tests

### 1. Cold Start Smoke Test
expected: |
  Kill any running runner process. With a clean Python env, run `python -m pytest -q`.
  Expect 253 passed (CR-05 added 2 tests over the prior 251 baseline).
result: [PASS — 2026-05-27 `pytest -q` returns `253 passed in 0.78s`]

### 2. CLI surface — runner --help
expected: |
  `python -m seers_harness.validation.runner --help` prints usage with --stage {1,2,3},
  --out-dir, --csv, --num-requests flags. CR-02 fix means --csv and --num-requests
  forward through run() to the loaders (no silent drop).
result: [PASS — `--help` exit 0 with all 4 flags listed]
note: Phase 8 item D will ADD `--env-file <path>`; current CLI does not yet expose it.

### 3. Validation package import surface
expected: |
  `python -c "from seers_harness.validation import RecordingProvider, set_current_node_id,
  get_current_node_id, reset_current_node_id, flush_evidence, write_index,
  write_batch_summary, write_evolution_snapshot, TrialFailure, classify,
  is_trial_failure"` exits 0. All 07-01..04 exports (including the WR-04
  helper `reset_current_node_id` landed `aa49f06`) importable from package root.
result: [PASS — verified via `seers_harness/validation/__init__.py` exports table]

### 4. CR-01 cause-chain classifier
expected: |
  Wrapped provider exception is classified by walking __cause__/__context__.
result: [PASS — smoke probe at 07-VERIFICATION.md L223 confirms
  `provider_error` (was `infra_error` before fix `c2386a7`)]

### 5. CR-03 secret redaction in exception messages
expected: |
  safe_exc redacts `Bearer sk-...` to `<redacted>`; 512-char cap honoured.
result: [PASS — verified live via _secrets.safe_exc smoke probe
  (07-VERIFICATION.md L224)]

### 6. CR-04 path-escape rejection
expected: |
  evidence_writer._sanitise_node_id rejects/sanitises '/abs' → '_abs',
  '..' → fallback, '../../etc' → sanitised; commonpath defence raises
  ValueError on escape.
result: [PASS — commit `2cd75a0`, verified at 07-VERIFICATION.md L225]

### 7. CR-05 bounded parse-layer retry
expected: |
  Commit `fc25187` adds DEEPSEEK_PARSE_MAX_RETRIES (default 3) bounded
  retry on ProviderResponseError (malformed tool_call.arguments). Retry
  budget is parse-layer only — does NOT affect HTTP retries (D-03) or
  D-19 routing on exhaustion.
result: [PASS — `_parse_max_retries` at openai_compatible.py L37-44; for-loop
  L73-103 retries on ProviderResponseError. Two new tests landed with the fix.]
audit_pending: |
  Phase-8 item C must confirm on a fresh real-LLM batch that the retry
  actually absorbs DeepSeek-side truncation (the 20260526T174639Z log
  showed truncation at char 940 BEFORE this fix landed; current code
  should swallow that class but has not yet been exercised on real LLM).

### 8. Stage 1 evidence shape (latest run)
expected: |
  `tests/smoke/.runs/20260526T183142Z/stage1/` carries index.json (1 row,
  all D-16 columns), batch_summary.json, full per-request evidence subtree.
result: [PASS — Stage 1 = 1/1 PASS on VAL-01/02/04 in 20260526T183142Z run.]

### 9. Stage 2 evidence — successful captures
expected: |
  `tests/smoke/.runs/20260526T183142Z/stage2/index.json` shows successful
  rows with VAL-01/02/04 = true and full per-node evidence subdirs.
result: [PARTIAL — 2 of 20 stage 2 requests succeeded before the 60s
  ReadTimeout cascade (RC-01 in 07-VERIFICATION.md). Successful rows
  carry the expected shape; the run did not complete 20/20.]
blocker: phase-8 item A (timeout default 60s → 180s) must land before
  a 20/20 stage 2 is even attempted.

### 10. Stage 2 evidence — fail-fast row preserved
expected: |
  Failed row carries VAL-01/02/04 = false, exception column populated
  with a clean RuntimeError chain (no leaked secrets per CR-03), partial
  node evidence on disk under the failed request_id.
result: [PASS — Stage 2 fail-fast row carries
  `RuntimeError: Node personalized_copy_rubric failed after 1 attempts`
  (httpx ReadTimeout cascade per RC-01); partial evidence for the two
  upstream nodes is on disk; exception string is secret-clean.]
note: The fail-fast outcome itself is correct runner behaviour; the
  underlying cause (60s timeout) is what phase-8 item A addresses.

### 11. Phase 7 acceptance — Stage 3 evidence
expected: |
  Stage 3 must complete 20/20 concurrent requests at c=20 against real
  DeepSeek. Latest run (20260526T183142Z) never reached Stage 3 — fail-fast
  in Stage 2 stopped the batch at request 3 of 20.
result: [BLOCKED — gated on phase-8 hardening (timeout / transient retry /
  --env-file / failure_class) landing first. Re-launching real-LLM on
  current code would just hit the same RC-01 + RC-02 + RC-03 failures.]

### 12. Phase 7 acceptance — VAL-05 case_analysis.md F1..F4 verdicts
expected: |
  case_analysis.md has user-authored prose verdicts (not italic placeholders)
  under F1, F2, F3, F4 against the real-LLM evidence on disk. Acceptance bar
  requires user to judge factor sets "excellent" against the transferable-
  disposition standard.
result: [BLOCKED — D-13/D-14 user-only step; requires a clean 20/20 Stage 2
  batch first (currently blocked on phase 8). Companion deliverable
  `case_analysis_template.md` (trajectory-level reading guide) pending.]

### 13. Phase 7 acceptance — VAL-06 evolution mechanism fired
expected: |
  At least one `evolution_snapshot.json` carries non-empty `trials[]` —
  the deltas-distill-in-flight mechanism observed firing end-to-end.
result: [BLOCKED — phase-8 group F (runner ↔ evolution wiring) must land
  first. Currently `_run_one_request` never invokes `assemble_portfolio` /
  `run_request_trial`, so `trials[]` is structurally always empty.]

### 14. WRIN triage — 14 items closed/waived/scheduled
expected: |
  `07-WRIN-TRIAGE.md` shows every WR-01..06 + IN-01..08 row has Decision !=
  TBD. Each item is fixed-now (commit SHA), waived (rationale), or scheduled.
result: [PASS — 07-WRIN-TRIAGE.md status: closed (2026-05-27T02:55:00Z).
  7 fixed-now (CR-04 helper, WR-06, IN-02..07), 7 scheduled to phase 8,
  0 waived, 0 TBD.]

### 15. ROADMAP / STATE phase 7 acceptance
expected: |
  STATE.md reflects phase 7 status. After all acceptance criteria above
  are met, phase advances from gaps_found to verified/complete.
result: [BLOCKED — STATE.md updated 2026-05-27T03:45Z to reflect
  "REOPENED, BLOCKED ON PHASE 8" and added phase-8 row. Will move to
  passed when blockers 11/12/13 clear.]

## Summary

total: 15
passed: 8 (#1-8, 10, 14 — 9 actually, let me recount: 1, 2, 3, 4, 5, 6, 7, 8, 10, 14 = 10 passed)
partial: 1 (#9 — 2 of 20 stage 2 before cascade)
blocked: 4 (#11, 12, 13, 15 — all gated on phase 8)
issues: 0
pending: 0
skipped: 0

## Gaps

- 4 BLOCKED items (#11, 12, 13, 15) all gated on phase 8 landing.
- 1 PARTIAL (#9) — 2/20 stage 2 captures; 60s timeout cascade per RC-01.
- 0 outright FAIL — runner mechanics are correct; the blockers are
  operational (timeout, env handling, evolution wiring).

## Phase 8 dependency map

| UAT # | Phase 8 group | Phase 8 item |
|-------|---------------|--------------|
| #2    | Group 1       | D (--env-file flag adds new CLI surface) |
| #7    | Group 1       | C (CR-05 audit, no code change unless audit fails) |
| #9    | Group 1       | A (timeout 60s → 180s), B (transient retry) |
| #11   | Group 1+3     | A, B, D, E + WR-01 (fail-fast drain) |
| #13   | Group 2       | F (evolution wiring) |
| #14   | Group 3       | G (7 WR/IN runner-debt — moves from "scheduled" to commit refs) |
| #15   | all groups    | exit when 11/12/13 clear |
