---
phase: 06-evolution-chain-production-hardening
verified: 2026-05-26T13:30:00Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
notes:
  - "REQUIREMENTS.md still labels EVO-01/02/03/05/06, PROD-01/02, TERM-01/02, PROMOTE-01 as Pending. Code evidence shows them complete; the label is stale documentation only and is the orchestrator's closeout edit."
---

# Phase 6: Evolution Chain + Production Hardening — Verification Report

**Phase Goal (ROADMAP.md):** "Accepted when evolution skills align with tool-use principles, reflow cadence is scenario-based, reference v2 is designed but not emitted, concurrency/progress UX are tested, and promotion-chain modules build against the current schema."

**Verified:** 2026-05-26
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Evolution skills align with tool-use principles | VERIFIED | `workflow-skills/evolution/distill-skill-deltas/SKILL.md` directs the model to call `record_delta_observation`, `record_delta_change`, `submit_delta_distillation_final`. Handlers in `seers_harness/tools/evolution_tools.py` enforce structure (Pydantic `extra=forbid`), evidence refs, privacy scan over 6 known private trace key names, and self-rated metric ban via `_FORBIDDEN_SELF_RATED_KEYS = ("confidence", "score", "probability", "uncertainty", "strength")` blocked at handler entry. SKILL.md prose is current vocabulary (delta/proposal/trial/trajectory/portfolio/belief). |
| 2 | Reflow cadence is scenario-based | VERIFIED | `seers_harness/evolution/delta_portfolio.py` exposes `select_trial_delta(...)` as a pure function gated at the SEERS request/scenario boundary (D-16); `TrajectoryRecord` and `DeltaPortfolioRow` carry `scenario_id`. Trial selection is portfolio-adaptive: `trial_prob = (1 - recent_failure_rate) * (1 - token_budget_pressure) * (1 - production_pressure)` with scarcity weight `1/(1+sample_count)`. No daemon/scheduler/cron — all per-request. Tests `tests/test_delta_portfolio.py` (17) cover scarcity, failure-rate, token-pressure, applicable-surface gating. |
| 3 | Reference v2 is designed but not emitted | VERIFIED | `docs/reference_v2_schema_design.md` exists; contains explicit "Not emitted in Phase 6" forbid section. `tests/test_evolution_schema_design.py` audits prove no `emit_v2_*` / `write_v2_*` / `materialize_v2_*` / `export_v2_*` function or `V2Emitter` / `V2Writer` / `ReferenceV2Writer` / `ReferenceV2Emitter` class exists in `seers_harness/`. Verified live. |
| 4 | Concurrency UX is tested | VERIFIED | `tests/smoke/test_concurrency_smoke.py::test_concurrent_fake_provider_requests_do_not_cross_contaminate` runs 20 `DelayedScriptedProvider` requests on `ThreadPoolExecutor`, asserts 60 unique artifact paths, schema-validity per node, six contamination scans (provider snapshots, runtime records, runtime trace, trajectory records, session_id uniqueness, owner-segment artifact paths). Test passes in 0.13s. |
| 5 | Progress UX is tested | VERIFIED | `seers_harness/workflow/progress.py` provides `ProgressState` + `render_progress_line` + `ProgressReporter`. Imports only `os`, `sys`, `dataclasses`, `typing.IO` — no `rich`/`tqdm`/`logging`. `tests/test_workflow_progress.py` covers normal output, disabled no-op, CI-plain prefix, env-driven CI default, audit reconstructing forbidden tokens to keep test file grep-clean. 9 tests pass. |
| 6 | Promotion-chain modules build against current schema | VERIFIED | `seers_harness/evolution/promotion_smoke.py::build_promotion_smoke_report` imports cleanly. Live dry run against `workflow-skills/current/`: `live_skill_writes_enabled=False`, `runtime_touched=False`, `decision="dry_run_only"`. `tests/test_promotion_smoke.py` (12) include byte-invariance tests against both a tmp mirror AND the real workspace live root, source-import audit, sentinel runtime-shape directory test. |

**Score: 6/6 truths verified.**

---

## Required Artifacts (Three-Level Verification)

| Artifact | Exists | Substantive | Wired | Status |
|---|---|---|---|---|
| `seers_harness/evolution/__init__.py` | yes | re-exports public surface | imported by tests + promotion_smoke | VERIFIED |
| `seers_harness/evolution/delta_portfolio.py` | yes | 5 BaseModels with `extra=forbid`, 6 pure functions: `load_portfolio_jsonl`, `write_portfolio_jsonl`, `belief_mean`, `update_after_trial`, `select_trial_delta`, `trajectory_signature`, `buffer_trajectory`, `sediment_trajectories` | imported by trial_runner, promotion_smoke, tests | VERIFIED |
| `seers_harness/evolution/trial_runner.py` | yes | `SkillDeltaPatch` (Pydantic, extra=forbid), `apply_delta_patch_temporarily` ctx mgr, `run_request_trial`, `TrialOutcome` | imported by tests; restores on success/failure | VERIFIED |
| `seers_harness/evolution/promotion_smoke.py` | yes | pure function returning self-describing JSON report; sets `live_skill_writes_enabled=False` / `runtime_touched=False` / `decision="dry_run_only"` literally | imported by tests; live dry-run executes successfully | VERIFIED |
| `seers_harness/tools/evolution_tools.py` | yes | 3 hand handlers, strict tool specs (additionalProperties=False), privacy scan over `_PRIVATE_TERMS` walking nested strings, self-rated key rejection | tool specs registered for the new evolution skill | VERIFIED |
| `seers_harness/workflow/progress.py` | yes | `ProgressState` dataclass, `render_progress_line`, `ProgressReporter` (enabled/disabled/ci_plain). Only stdlib imports. | tested directly; documented Phase-7 hook point in `docs/design.md` | VERIFIED |
| `seers_harness/provider_runtime/openai_compatible.py` | yes (modified) | `deepseek_runtime_facts()` pure read-only function returning 8-key dict; no SDK client construction | imported by `tests/test_deepseek_rate_limit_facts.py`; pinned 147 ≤ 150 line budget | VERIFIED |
| `workflow-skills/evolution/distill-skill-deltas/SKILL.md` | yes | Phase-4 eight-section style, current vocabulary (delta/proposal/trial/trajectory/portfolio/belief); cites all three handlers; no JSON-only / champion / candidate-bundle / self-rated language | the live skill prose surface read by the new tool-use skill | VERIFIED |
| `docs/reference_v2_schema_design.md` | yes | design-only sketch, contains literal "Not emitted in Phase 6" | audit tests pin its content; no live emitter ships | VERIFIED |
| `docs/deepseek_rate_limit_facts.md` | yes | records model `deepseek-v4-pro`, base URL `https://api.deepseek.com/beta`, SDK max retries 0, 429 → `rate_limit`, fact date 2026-05-26, optional probe policy, explicit Phase-6 non-goal | doc-content tests pin literal strings; sourced from `deepseek_runtime_facts()` | VERIFIED |
| `tests/smoke/test_concurrency_smoke.py` | yes | 20-request ThreadPoolExecutor smoke, six contamination assertion blocks, scope-boundary docstring (D-18/D-19/D-21) | passes in 0.13s | VERIFIED |
| `tests/test_promotion_smoke.py` | yes | 12 audits inc. dual byte-invariance (tmp mirror + real live root), retired-skill name absence, source-import audit, sentinel runtime-shape dir | passes in 0.10s | VERIFIED |

All artifacts: VERIFIED at all three levels (exist, substantive, wired).

---

## Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `distill-skill-deltas/SKILL.md` | `evolution_tools.py` handlers | named handler calls in skill prose; corresponding `def` in tools | WIRED |
| `evolution_tools.py` handlers | `DeltaDistillationArtifact` | `submit_delta_distillation_final` validates Pydantic model and writes `state["final_artifact"]` | WIRED |
| `delta_portfolio.py::select_trial_delta` | trial scheduling | callable from request boundary; `tests/test_trial_runner.py::test_integration_select_trial_buffer_and_update` exercises end-to-end | WIRED |
| `trial_runner.py::run_request_trial` | `WorkflowRuntime.run_request` | direct call inside `apply_delta_patch_temporarily(...)` ctx mgr; integration test asserts artifact paths returned for all three nodes | WIRED |
| `trial_runner.py::apply_delta_patch_temporarily` | restoration | `try/finally` writes original content back; tests prove restore on normal exit AND after exception | WIRED |
| `promotion_smoke.py` | live `workflow-skills/current/` | reads + hashes only; report sets writes_enabled=False; dual byte-invariance test (tmp mirror + real root) | WIRED |
| `progress.py::ProgressReporter` | future Phase-7 fan-out | hook point documented in `docs/design.md "Long-Run Progress (Phase 7 Hook Point)"`; tests cover composition shape | WIRED (deferred long-run wiring per plan task 06-04-04 fallback) |
| `deepseek_runtime_facts()` | `docs/deepseek_rate_limit_facts.md` | doc audits pin the same literal values as the function returns; 429 category computed via `classify_exception` | WIRED |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Real Data | Status |
|---|---|---|---|---|
| `select_trial_delta` | weighted portfolio | `DeltaPortfolioRow` rows from `load_portfolio_jsonl` JSONL | yes — JSONL persistence pure function | FLOWING |
| `run_request_trial` | artifact paths | `runtime.run_request(...)` real DAG with ScriptedProvider | yes — 3 artifact paths returned by integration test | FLOWING |
| `sediment_trajectories` | bounded JSONL | dedup + privacy + diversity round-robin filter | yes — round-robin diversity test asserts rare buckets survive | FLOWING |
| `build_promotion_smoke_report` | `skill_files` | walks `workflow-skills/current/`, reads + hashes | yes — live dry run returns 3 entries (factor/copy/judge) | FLOWING |
| `ProgressReporter` | `ProgressState` counters | caller-supplied via mutation | yes — long-run loop test asserts counters surface | FLOWING |
| `deepseek_runtime_facts()` | facts dict | static defaults from provider module + `classify_exception` for 429 category | yes — exploding `OpenAI` symbol stub still returns dict (no client construction) | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full pytest suite | `uv run --python 3.12 --extra dev python -m pytest -q` | **251 passed in 1.01s** | PASS |
| Concurrency smoke | `uv run --python 3.12 --extra dev python -m pytest tests/smoke/test_concurrency_smoke.py -v` | 1 passed in 0.13s | PASS |
| `promotion_smoke` import | `python -c "from seers_harness.evolution.promotion_smoke import build_promotion_smoke_report"` | imports ok | PASS |
| Live dry-run report | live invocation against `workflow-skills/current` | `live_skill_writes_enabled=False`, `runtime_touched=False`, `decision=dry_run_only`, output_exists=True | PASS |
| Self-rated metric ban | `grep -rEn 'confidence\|score\|probability\|uncertainty\|strength' seers_harness/evolution/ seers_harness/tools/evolution_tools.py` | only deliberate `_FORBIDDEN_SELF_RATED_KEYS` ban-list literals + comment prose; never a Pydantic field, tool-spec property, or skill prose claim | PASS |
| Champion vocabulary absence | `grep -rn 'champion\|candidate bundle' seers_harness/evolution/ workflow-skills/evolution/` | 0 hits | PASS |
| compare-champion-bundles / select-seed-probes absence | `grep -rn 'compare-champion-bundles\|select-seed-probes' workflow-skills/ seers_harness/` | 0 hits | PASS |
| harness-runtime non-import | `grep -rn 'harness-runtime\|harness_runtime' seers_harness/` | 5 hits, all in `promotion_smoke.py` docstring negative-boundary text; no `import`/`from` line | PASS |
| Forbidden machinery | `grep -rEn 'daemon\|scheduler\|Limiter\|RateLimiter\|circuit_breaker\|CircuitBreaker' seers_harness/` | 0 hits | PASS |
| progress.py forbidden imports | `grep -E 'rich\|tqdm\|logging' seers_harness/workflow/progress.py` | 0 hits (only `os`, `sys`, `dataclasses`, `typing.IO`) | PASS |

---

## Probe Execution

No formal probe scripts declared in this phase (probe tests live as conventional pytest under `tests/smoke/`). The plan's verification gates are the pytest commands documented above. All gates pass.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| EVO-01 | 06-01 | Delete evolution skills that ask an LLM to judge champion bundles or select probes | SATISFIED | `workflow-skills/evolution/` contains only `distill-skill-deltas`. 3 audit tests in `tests/test_evolution_schema_design.py` (`test_workspace_workflow_skills_evolution_does_not_have_compare_champion_bundles`, `test_workspace_workflow_skills_evolution_does_not_have_select_seed_probes`, `test_plan_verification_step_3_grep_gate`). |
| EVO-02 | 06-01 | Rewrite `distill-skill-deltas` as a tool-use skill with matching handlers | SATISFIED | SKILL.md uses tool-use style, names all three handlers; `evolution_tools.py` implements them; 32 tests in `tests/test_evolution_tools.py`. |
| EVO-03 | 06-05 | Audit `promote-skill-patch` and keep only deterministic action | SATISFIED | No live `promote-skill-patch` directory under `workflow-skills/`; promotion behavior is the deterministic dry-run `build_promotion_smoke_report` returning `decision="dry_run_only"`. 3 retired-skill audits in `tests/test_promotion_smoke.py`. |
| EVO-04 | 06-02 | Rename and implement scenario-based evolution cadence | SATISFIED | `select_trial_delta` portfolio-adaptive selector (scarcity / failure-rate / token-pressure / production-pressure / applicability), `TrajectoryRecord.scenario_id`, `DeltaPortfolioRow.scenario_id`. Trial scheduling at SEERS request/scenario boundary (D-16) — no daemon/cron. 17 portfolio tests + 9 trial-runner tests + 16 trajectory-evidence tests. |
| EVO-05 | 06-01 | Write reference v2 schema design only; do not emit v2 yet | SATISFIED | `docs/reference_v2_schema_design.md` exists with literal "Not emitted in Phase 6"; 4 audits prove no v2 emitter function/class in `seers_harness/`. |
| EVO-06 | 06-01 | Audit evolution field names against current schema | SATISFIED | `champion` / `candidate bundle` absent from workspace evolution Python files; `test_workspace_evolution_module_files_do_not_contain_champion` enforces. Field names use delta/proposal/trial/trajectory/portfolio/belief language. |
| PROD-01 | 06-03 | Stress concurrency 20 with realistic FakeProvider latency | SATISFIED | `tests/smoke/test_concurrency_smoke.py` runs 20 `DelayedScriptedProvider` (0.005s/call sleep) requests through `ThreadPoolExecutor`; 60 unique artifact paths; six contamination assertion blocks. Passes in 0.13s. |
| PROD-02 | 06-04 | Verify current DeepSeek rate-limit assumptions before tuning limits | SATISFIED | `deepseek_runtime_facts()` pure read-only function; `docs/deepseek_rate_limit_facts.md` records model/base URL/timeout/SDK retries=0/429-category; explicit "Phase 6 does not tune concurrency or add a limiter" non-goal pinned by audit test. 8 facts tests + 6 doc-content audits. |
| TERM-01 | 06-04 | Add terminal progress display for long runs | SATISFIED | `seers_harness/workflow/progress.py::ProgressReporter` writes a single `[N/M] current=… failures=… delta_trials=…` line per update — exactly the Phase-6 contract. |
| TERM-02 | 06-04 | Add CI-safe `--no-progress`/plain-output behavior | SATISFIED | `enabled=False` no-op, `ci_plain=True` adds `[progress]` prefix; `_detect_ci_default()` honors `CI` env var (`true`/`1`/`yes`). 9 tests cover all three modes + env-default. No ANSI / no `\r`. |
| PROMOTE-01 | 06-05 | Smoke promotion-chain public entry points against current fixtures | SATISFIED | `build_promotion_smoke_report` imports cleanly, reads `workflow-skills/current/` and optional portfolio JSONL, writes JSON dry-run report; live skill files byte-identical before and after (verified against real `workflow-skills/current` root). |
| PROC-02 | all 5 plans | Each phase plan names the skills or methods it relies on | SATISFIED | All five 06-NN-PLAN.md files declare a `## Skills/Methods` section. Verified by grep. |

**12/12 requirements SATISFIED. No orphans, no deferrals.**

Documentation note: `.planning/REQUIREMENTS.md` still labels EVO-01/02/03/05/06, PROD-01/02, TERM-01/02, PROMOTE-01 as "Pending" while the codebase shows them complete. This is a stale label, not a missing implementation — the orchestrator typically advances these labels at phase closeout. Code evidence is unambiguous.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|

No TBD / FIXME / XXX / unresolved debt markers in any phase-6 modified file. No empty implementations / stub returns / hardcoded empty data. No console-only handlers. No forbidden imports. No daemon/scheduler/limiter/circuit-breaker classes anywhere in `seers_harness/`. No `harness-runtime` imports.

---

## Human Verification Required

None. All must-haves are programmatically verifiable and have been verified by running pytest and inspecting code. The optional DeepSeek rate-limit live-header probe is intentionally off by default (requires `DEEPSEEK_API_KEY`) and is documented as fact-recording only — not a gate for Phase 6.

---

## Gaps Summary

None. Phase 6 goal is fully achieved against ROADMAP.md success criteria:

- evolution skills align with tool-use principles (D-03, EVO-02): `distill-skill-deltas` is a tool-use skill with privacy-scanning, self-rated-metric-banning, evidence-enforcing handlers — VERIFIED.
- reflow cadence is scenario-based (EVO-04, D-09, D-16): selection happens at the request/scenario boundary via a deterministic portfolio-adaptive function — VERIFIED.
- reference v2 is designed but not emitted (EVO-05): docs-only sketch, audit tests block any emitter — VERIFIED.
- concurrency UX tested (PROD-01): 20-request fake-provider smoke with realistic latency, six contamination scans, all pass — VERIFIED.
- progress UX tested (TERM-01, TERM-02): plain-stdout reporter with no third-party dependency, no-progress + CI-plain modes covered — VERIFIED.
- promotion-chain modules build against current schema (PROMOTE-01, EVO-03, D-22, D-24): `build_promotion_smoke_report` runs to a JSON dry-run report under workspace schema, no live-skill writes, no runtime edits — VERIFIED.

Full-suite regression: **251 passed in 1.01s**.
Boundary scans: zero `harness-runtime` imports, zero champion/select-probe live references, zero rich/tqdm/logging in `progress.py`, zero daemon/scheduler/limiter/circuit-breaker classes in `seers_harness/`.

Phase 6 is ready to merge into the verified baseline. Phase 7 (real-LLM validation) is the dependent next step.

---

_Verified: 2026-05-26_
_Verifier: Claude (gsd-verifier)_
