# Phase 08: Runner ↔ Evolution Wiring + Runner-Debt Cleanup + Phase-7 Real-LLM Hardening — Context

**Gathered:** 2026-05-27
**Status:** Ready for planning
**Source:** Transcribed from `08-CHARTER.md` + user kick-off constraints (2026-05-27 "1 我需要的是把整个流程每个模块全跑通且确定分别都work, 这部分几乎不能依赖冒烟测试, 必须跑ds实测. 同时注意在定位错误时我需要真正的根因定位而不是表层错误")

<domain>
## Phase Boundary

This phase makes a single runner-touch sweep over `seers_harness/validation/runner.py` (plus the provider runtime and one trial-runner narrowing) so that:

1. Phase 7's reopened acceptance gate can re-launch real DeepSeek Stage 1+2+3 cleanly without the three 2026-05-26 operational failures (60s timeout / shell-env staleness / unhandled transient errors).
2. The runner ↔ phase-6 evolution wiring closes the "evolution observed firing on real runs" condition (≥1 non-empty `trials[]` in `evolution_snapshot.json`).
3. The 7 deferred phase-7 WR/IN runner-debt items land in the same sweep, since they touch the same file.

**Three deliverable groups, single runner-touch sweep:**

- **Group 1 (A-E)** — Phase-7 real-LLM operational hardening.
- **Group 2 (F)** — Primary deliverable: runner ↔ evolution wiring with a seeded test delta.
- **Group 3 (G)** — Seven WR/IN items deferred from phase 7 (`07-WRIN-TRIAGE.md`).

**Out of scope:**
- No new evolution-design changes. Phase 6 designed evolution; phase 8 only *connects* phase 6 evolution to phase 7 runner.
- No changes to phase-7 capture layer (`recording_provider.py`, `evidence_writer.py`, `index_writer.py`, `batch_summary_writer.py`, `machine_judges.py`) except the additive `failure_class` column (Group 1 E) — D-22d isolation must hold.
- No new phase-7 plan documents. Phase 7's acceptance gate stays open and is unblocked by phase-8 commits, not replanned.
- No real-LLM tuning / circuit-breaker / rate-limit absorber (already deferred — phase 7 stage 3 only observes).

</domain>

<decisions>
## Implementation Decisions

### Group 1 — Phase-7 real-LLM hardening (A-E)

- **D8-A** Bump `DEEPSEEK_TIMEOUT_SECONDS` default in `seers_harness/provider_runtime/openai_compatible.py:141` from `"60"` to `"180"`. Operators may still override via env. **Why 180s:** observed worst-case TTFB ≈110s on `deepseek-v4-pro` + `reasoning_effort=max` + `thinking.type=enabled`; 180s gives ~60% headroom (charter Group 1 A; not raising further until evidence shows >110s in a real run).
- **D8-B** Wrap `_run_one_request`'s `generate_with_tools` invocation with up to 2 additional attempts (3 total) on `ProviderTransientError` ONLY. Backoff sequence: 5s, 15s. This is a *request*-level retry, not an HTTP/SDK-level retry — it does NOT change D-03 (SDK `max_retries=0` stays). `ProviderAuthError`, `ProviderRateLimitError`, `ProviderResponseError`, `TrialFailure`, `AssertionError`, `SchemaError` continue to fail-fast per D-02 / D-19.
- **D8-C** CR-05 audit is **verify-only, do not modify**. After the next real-LLM batch lands ≥1 `tool_call.arguments` truncation event, read the runner log for `parse_retry_*` markers and confirm the bounded parse-layer retry absorbed the truncation without raising. If the audit fails (retry exhausted but D-19 routing wrong), file a new WR item in a follow-up — no code change in this phase unless the audit fails.
- **D8-D** Add an optional `--env-file <path>` CLI argument to `runner.py`. Parser handles `KEY=VALUE` lines + `#` comments + no shell expansion. Merges into `os.environ` BEFORE the provider is constructed. **Security:** never log resolved key values; only log `loaded N keys from <path>` and `DEEPSEEK_API_KEY` suffix (last 4 chars).
- **D8-E** Add `failure_class` column to each row in `index.json` and aggregate by class in `batch_summary.json`. Allowed values: `{auth, rate_limit, transient, malformed_tool_args, schema_violation, runner_bug, ok}`. Materialised from existing exception types: `ProviderAuthError → auth`; `ProviderRateLimitError → rate_limit`; `ProviderTransientError → transient`; `ProviderResponseError → malformed_tool_args`; `SchemaError → schema_violation`; any other exception → `runner_bug`; success → `ok`.

### Group 2 — Runner ↔ evolution wiring (F)

- **D8-F1** `_run_one_request` calls `assemble_portfolio` + `run_request_trial(events=events)` when `delta_portfolio` is non-empty. When empty, the runner skips both calls — never raises.
- **D8-F2** Seed at least one test delta into the `delta_portfolio` at process start so `trials[]` is observably non-empty on real-LLM runs. **The seeded delta IS the trial source for phase 8 acceptance** — it must produce a recorded `TrialOutcome`, not a no-op.
- **D8-F3** The `events` list passed to `run_request_trial` flows to the per-request `evolution_snapshot.json` reducer (`seers_harness/validation/evolution_snapshot.py`) — no new reducer code; reuse the phase-7 seam landed in 07-01.

### Group 3 — Runner-debt (G)

- **D8-G-WR-01** Stage 3 fail-fast drains in-flight futures (cancel + wait-for-cancellation) BEFORE stopping, so disk artifacts and `index.json` agree on which requests ran.
- **D8-G-WR-02** Wrap `flush_evidence` and `write_evolution_snapshot` in the runner's `finally` clause with best-effort logging (catch + log + continue) so a cleanup failure cannot mask the original exception.
- **D8-G-WR-03** Delete the duplicate `_detect_delimiter` in `runner.py:350` and import the canonical one from `seers_harness.intake.request_preprocessor`.
- **D8-G-WR-04** Migrate runner's `_cv.reset(token)` call to the public `reset_current_node_id(token)` helper landed in `aa49f06`. The private `_cv` import is removed.
- **D8-G-WR-05** Narrow `trial_runner`'s `except Exception` to `(TrialFailure, AssertionError, SchemaError)` and re-raise `(ProviderAuthError, ProviderRateLimitError, ProviderTransientError)` so D-19 fail-fast holds once trials actually run.
- **D8-G-IN-01** Plumb `runtime.trace[*].usage` into `TrialOutcome.token_cost_observed`. Field must reflect real recorded usage from the captured trace, not be dead.
- **D8-G-IN-08** Extract the `max_retries=3` provider-side budget into a keyword parameter on `deepseek_provider_from_env(..., max_retries=3)` and remove the `"max_" + "retries"` scan-evasion string concatenation in the runner.

### Acceptance gates (BLOCKING, all must hold)

- **D8-ACC-1** A real-LLM Stage 1 + Stage 2 + Stage 3 batch completes end-to-end on a single phase-8 commit. Zero requests dropped to 60s timeout, shell-env staleness, or unhandled transient errors. **No smoke-test or FakeProvider substitution counts** (user constraint 2026-05-27).
- **D8-ACC-2** `evolution_snapshot.json` carries ≥1 non-empty `trials[]` entry — the seeded test delta fired and was recorded. Closes phase-7 condition "evolution mechanism observed firing on real runs."
- **D8-ACC-3** `index.json` carries `failure_class` per row; `batch_summary.json` aggregates by class.
- **D8-ACC-4** `pytest -q` passes on the runner-touch sweep covering WR-01..05, IN-01, IN-08, plus new tests for A, B, D, E.
- **D8-ACC-5** `07-WRIN-TRIAGE.md` updated: all 7 scheduled items move from `scheduled (phase 8)` to a phase-8 commit reference.
- **D8-ACC-6** Phase 8's own `08-VERIFICATION.md` is `passed`.

### Sequencing (locked)

Per charter Sequencing recommendation (user-endorsed 2026-05-27 "开干"):

1. **A** (timeout 60→180), **D** (`--env-file`), **E** (`failure_class`) — make the runner re-runnable on real LLM at all.
2. **C** (CR-05 audit) — gated on a real-LLM batch landing first; audit-only, no code change unless audit fails.
3. **WR-03**, **WR-04 callsite**, **IN-08** — pure cleanup.
4. **F** — evolution wiring (primary deliverable).
5. **B** — request-level transient retry; wraps the new wiring naturally.
6. **WR-01**, **WR-02**, **WR-05**, **IN-01** — touch the new wiring directly.

### User-imposed validation constraints (LOCKED, 2026-05-27)

- **D8-VAL-REAL** Every module (A-E, F, G) must be **verified to work end-to-end against real DeepSeek**, not just against pytest/FakeProvider. Smoke tests prove the code path compiles and contracts hold; they do NOT prove the module "works" for phase-8 acceptance. The runner-touch sweep is gated on a real-LLM Stage 1+2+3 batch completing on the final phase-8 commit. No module is "done" until at least one real-LLM trace demonstrates it firing — including:
  - A: a real-LLM request with TTFB >60s succeeds (timeout did not fire prematurely).
  - B: a real-LLM transient error is observed AND retried AND succeeded on a later attempt. (If no transient appears organically during Stage 1+2+3, a deliberate fault-injection request goes into the sweep so the path is exercised — fault-injection traces are tagged in `index.json` so they're not counted as honest failures.)
  - C: at least one real-LLM `tool_call.arguments` truncation occurs in the batch; the parse-retry markers are read; verdict logged.
  - D: the batch is launched via `--env-file .env.local` with no shell `export`; the runner's log shows the key suffix and `loaded N keys` line.
  - E: `index.json` carries every allowed `failure_class` value that the batch's outcomes warrant.
  - F: `evolution_snapshot.json` from the batch contains ≥1 non-empty `trials[]` entry from the seeded delta.
  - G: each WR/IN item has a real-LLM trace or runner log line that demonstrates the fix is active (not just that the code path now compiles).
- **D8-VAL-ROOTCAUSE** Failure diagnosis MUST go to **root cause**, not surface symptom. If a real-LLM run fails:
  - Do NOT patch the line that raised. Read the trace, locate the upstream condition that produced the bad state, and fix THAT.
  - Do NOT classify a real-LLM failure as `runner_bug` (Group 1 E) until the root cause is shown to be inside the runner. Default suspect chain: shell env → `.env.local` → provider response → runner state → test/seed setup.
  - Plan tasks that diagnose failures must include a `<read_first>` list spanning the trace location, the upstream function, and any state file the upstream reads — not just the function that raised.
  - Any "I think we fixed it" claim is not acceptance evidence; only a real-LLM re-run on the supposedly-fixed code is.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-8 inputs (must read)

- `.planning/phases/08-evolution-wiring-and-runner-debt/08-CHARTER.md` — Source of truth for Groups A-G, sequencing, and acceptance bar. Charter wins on conflict with summarised text.
- `.planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md` — The 7 scheduled WR/IN items (Group 3). Each item has a triage decision + scope that the planner must preserve.
- `.planning/phases/07-real-llm-validation/07-REVIEW.md` — Critical CR-01..05 fixes already landed; CR-05 audit (Group 1 C) targets the parse-retry it added.
- `.planning/phases/07-real-llm-validation/07-VERIFICATION.md` — Phase-7 reopen rationale; status `gaps_found` after 2026-05-26 real-LLM batch.

### Runner & validation code (must read before modifying)

- `seers_harness/validation/runner.py` — The phase-8 single-file sweep target. Carries `_run_one_request`, `_detect_delimiter` (duplicate, WR-03), `_cv.reset` callsite (WR-04), empty `_delta_portfolio_empty` anchor (F seed), Stage 1/2/3 driver, and `finally` clause for WR-02.
- `seers_harness/provider_runtime/openai_compatible.py` — `DEEPSEEK_TIMEOUT_SECONDS` default (Group 1 A, line 141), `deepseek_provider_from_env` signature (IN-08), exception types referenced by Group 1 B + E.
- `seers_harness/validation/exception_classifier.py` — `classify()` and `TrialFailure`; the source of truth for the `failure_class` mapping in Group 1 E.
- `seers_harness/validation/index_writer.py` — Receives `failure_class` per row (E).
- `seers_harness/validation/batch_summary_writer.py` — Aggregates by `failure_class` (E).
- `seers_harness/validation/evolution_snapshot.py` — Per-request reducer for `events` from `run_request_trial` (F).
- `seers_harness/evolution/delta_portfolio.py` — `assemble_portfolio` (F).
- `seers_harness/evolution/trial_runner.py` — `run_request_trial`, `TrialOutcome`, the `except Exception` to narrow (WR-05), and the `token_cost_observed` field (IN-01).
- `seers_harness/intake/request_preprocessor.py` — The canonical `_detect_delimiter` (WR-03 imports it).

### Phase-6/7 contract docs (must respect)

- `.planning/intel/decisions.md` — Architectural decisions log (D-XX). Group 1 B must not break D-02, D-03, D-19; F must not break D-18 (empty portfolio default); E must not break D-22d capture-vs-judge isolation.
- `.planning/REQUIREMENTS.md` — Phase 7's VAL-01..06 IDs. Phase 8 does NOT carry phase-8-specific REQ-IDs (it's an unblocker phase) — see `<scope_fence>` below.

### Trace evidence (must read for root-cause work)

- `tests/smoke/.runs/20260526T183142Z/` — The 2026-05-26 batch that surfaced timeout / truncation / stale-env. Use as the root-cause anchor for A, B, C, D.
- `.planning/handoffs/` — Phase-7 → phase-8 handoff notes (`899a346`); root-cause RC-01..03 documented.

</canonical_refs>

<specifics>
## Specific Ideas

### Open questions from CHARTER (resolved or carried)

The charter listed four open questions for kick-off. Resolved/carried:

1. **Test delta seed (Q1).** Use a **real prompt-level delta from `.planning/intel/`**, not a no-op patch. Rationale: charter Q1 explicitly weighed the trade-off and the user's "I need the modules to actually work, no smoke" constraint (D8-VAL-REAL) rules out a no-op. The exact delta is researcher's call — the constraint is "must produce a measurable `TrialOutcome.token_cost_observed`, not zero." Researcher locks the choice in `08-RESEARCH.md`.
2. **Trial cadence (Q2).** Carry phase-6 default: one trial per `assemble_portfolio` policy decision. Phase 8 does NOT redesign cadence (out-of-scope per `<scope_fence>`).
3. **Timeout default (Q3).** Locked at 180s per D8-A.
4. **Transient retry budget (Q4).** Locked at 2 attempts / 3 total per D8-B.

### Concrete touchpoints (grepped 2026-05-27)

- `seers_harness/provider_runtime/openai_compatible.py:141` — timeout default literal.
- `seers_harness/validation/runner.py:350` — duplicate `_detect_delimiter`.
- `seers_harness/validation/runner.py:425` — `_run_one_request` (B wrap, F call).
- `seers_harness/validation/runner.py:782-786` — empty `_delta_portfolio_empty` D-18 anchor; F seed lands here.
- `seers_harness/validation/runner.py:238` — D-03 `"max_" + "retries"` scan-evasion (IN-08 removes this).
- `seers_harness/validation/runner.py:223` — CLI args block; D `--env-file` lands here.

### Test-pattern conventions to respect

- All new tests live under `tests/` mirroring the source tree (see existing phase-7 tests for `runner.py`).
- Fault-injection tests for B use a custom transient exception, not real-network flakiness. The **real-LLM acceptance trace** for B is separate and lives in the Stage 1+2+3 batch evidence.
- `ensure_ascii=False` is mandatory wherever Chinese tokens appear in artifacts (carry phase-7 D-22 convention).
- Tests must not bake any DEEPSEEK_API_KEY into source (carry phase-7 DI convention).

</specifics>

<deferred>
## Deferred Ideas

- Real-DeepSeek concurrency tuning / circuit-breaker / rate-limit absorber — phase 7 stage 3 only observes; tuning is a follow-up phase. Confirmed deferred in STATE.md.
- Trial isolation upgrade to git worktree — pre-deployment ADR review; current `shutil.copytree` mechanism is sufficient for phase 8.
- Reference v2 emitter implementation — phase 6 designed v2; emitter work is post-phase 7.
- In-tree canonical run archival — raw `.runs/` stays local-only per D-09; revisit only if case-reading needs it.
- New evolution-design changes (cadence, reflow policy, delta-generation strategy) — phase 6 owned these. Phase 8 connects but does not redesign.
- Reduce transient-retry attempts below 2 to "keep cycle time tight on Stage 3 c=20" (charter Q4) — rejected for phase 8; reconsider only if Stage 3 cycle-time evidence shows 2 attempts is too expensive.
- Failure-classification taxonomy beyond the 7 values in D8-E — extend only when a real failure surfaces that none of the 7 cleanly classifies.

</deferred>

<scope_fence>
## Scope Fence

**Phase 8 deliberately does NOT cover:**
- Phase-7 case_analysis F1..F4 verdicts (user-driven, runs AFTER the phase-8 real-LLM re-run lands).
- Phase-7 VAL-03 / VAL-06 case-reading verdicts (same; user-driven, post phase 8).
- Any modification to phase-6 evolution logic, delta-generation, or reflow policy — phase 8 only *wires* phase 6 into phase 7's runner.
- Any change to the phase-7 capture layer (`recording_provider`, `evidence_writer`) except the additive `failure_class` column in `index_writer` + `batch_summary_writer`.
- Phase-7 acceptance closure itself. Phase 8 unblocks the gate; closing it is a phase-7 follow-up step after the phase-8 batch lands.

**Phase 8 IS NOT a phase-7 retry.** It is a runner-debt + wiring sweep that PRODUCES the conditions under which phase 7 can be retried.

</scope_fence>

---

*Phase: 08-evolution-wiring-and-runner-debt*
*Context transcribed: 2026-05-27 from 08-CHARTER.md + user constraints*
