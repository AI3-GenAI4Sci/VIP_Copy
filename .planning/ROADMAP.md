# Roadmap: SEERS Harness Workspace

## Overview

The workspace follows an eight-phase GSD plan. Phases 1-6 have landed and are
covered by phase summaries plus tests. Phase 7 is reopened blocked on Phase 8.

| Phase | Scope | Status | Evidence |
|---|---|---|---|
| 1 | Schema + tool-handler foundation | Complete | covered by current 122/122 suite; summaries `01-01`, `01-02` |
| 2 | Single `generate_with_tools` provider path | Complete | covered by current 122/122 suite; summaries `02-01`, `02-02` |
| 3 | Tool loop + DAG integration + payload cleanup | Complete | covered by current 122/122 suite; summaries `03-01`, `03-02`, `03-03` |
| 4 | Rewrite the three development SKILL.md files | Complete | summary `04-SUMMARY.md`; three SKILLs under `workspace/workflow-skills/current/`; 122/122 baseline holds |
| 5 | Cleanup, deletes, tests, bypass-module regression | Complete | summary `05-SUMMARY.md`; 125/125 suite incl. 20-request E2E smoke |
| 6 | 5/5 | Complete    | 2026-05-26 |
| 7 | 6/6 code-side; full real-LLM coverage pending | In progress (blocked on 8) | 2026-05-27 — code-side ready: 4 Critical review fixes (CR-01..04) committed, pytest 251/251 holds, validation stack 07-01..07-06 modules in place. PARTIAL 07-06 acceptance retracted by user; phase reopens until a full post-CR-01..04 real-LLM re-run completes Stage 1 + Stage 2 (20/20) + Stage 3 (20/20), case_analysis F1..F4 judged excellent, evolution reflow events observed, and WR/IN findings closed or scheduled. |
| 8 | 8/13 | In Progress|  |

## Phase Criteria

### Phase 1: Schema + Tools Foundation

Accepted when the C17 schema accepts the new fields, rejects deleted/self-rated
fields, exposes all pure-function handlers, and keeps handler logic structural.

### Phase 2: Single Provider Path

Accepted when `openai_compatible.py` exposes one tool path, deletes
`generate_json`/`response_format`, carries parsed raw tool calls, and keeps the
provider file within its line budget.

### Phase 3: Tool Loop + DAG Integration

Accepted when `run_skill_via_tools` drives scripted tool calls, handles error and
retry routing, and `dag_runner._run_node` validates final artifacts through typed
models without polling residue.

### Phase 4: SKILL.md Prose Rewrites

Accepted when the three SKILL files are ≤60 visible markdown lines each, use the
8-section skill template, frame work as tool-call sequences, retain only
transferable methodology, and avoid numeric thresholds, internal examples,
enumerations, and JSON-output framing.

### Phase 5: Cleanup, Deletes, Tests, Regression

Accepted when retired polling/check modules are gone, invariants match the new
schema, FakeProvider uses tool-call scripts, and storage/assets/evaluation/gates
/CLI regression surfaces either pass or have documented delete/keep decisions.

### Phase 6: Evolution Chain + Production Hardening

Accepted when evolution skills align with tool-use principles, reflow cadence is
scenario-based, reference v2 is designed but not emitted, concurrency/progress UX
are tested, and promotion-chain modules build against the current schema.

### Phase 7: Real-LLM Validation

Accepted when 20 real DeepSeek scenarios run through the stack with tool calls,
clean copy, transferable factors, reachable reflection, and expected evolution
reflow events.

### Phase 8: Runner ↔ Evolution Wiring + Runner-Debt Cleanup + Phase-7 Real-LLM Hardening

Depends on: Phase 6, Phase 7

Accepted when ALL of the following hold (full text in `08-CHARTER.md`):

1. A real-LLM Stage 1 + Stage 2 + Stage 3 batch completes end-to-end on a
   single phase-8 commit with no requests dropped due to 60s timeout, shell-env
   staleness, or unhandled transient errors.
2. `evolution_snapshot.json` carries at least one non-empty `trials[]` entry —
   the seeded test delta fired and was recorded (closes phase-7 acceptance
   condition "evolution mechanism observed firing on real runs").
3. `index.json` carries `failure_class` per row drawn from `{auth, rate_limit,
   transient, malformed_tool_args, schema_violation, runner_bug, ok}`;
   `batch_summary.json` aggregates by class.
4. `pytest -q` passes on the runner-touch sweep covering WR-01..05, IN-01,
   IN-08, plus new tests for Group 1 items A, B, D, E.
5. `07-WRIN-TRIAGE.md` updated: all 7 scheduled items move from
   `scheduled (phase 8)` to a phase-8 commit reference.
6. Phase 8's own `08-VERIFICATION.md` is `passed`.

Three deliverable groups, single runner-touch sweep:

- **Group 1 (A-E) — Phase-7 real-LLM hardening:** A timeout 60→180s,
  B request-level transient retry (`ProviderTransientError` only, 2 attempts,
  backoff 5s/15s — does NOT change D-03 SDK `max_retries=0`), C CR-05 audit
  (verify, do not modify), D runner `--env-file` flag (no shell ENV
  indirection; never log resolved key), E `failure_class` column in
  `index.json`.
- **Group 2 (F) — primary deliverable:** Wire `_run_one_request` to call
  `assemble_portfolio` + `run_request_trial` with `events=events` when
  `delta_portfolio` is non-empty; seed at least one test delta at process
  start so `trials[]` is observably non-empty.
- **Group 3 (G) — runner-debt deferred from phase 7:** WR-01 Stage 3 fail-fast
  drains in-flight futures; WR-02 wrap evidence/snapshot writers in `finally`;
  WR-03 delete duplicate `_detect_delimiter`; WR-04 callsite migrate to public
  `reset_current_node_id` helper; WR-05 narrow `trial_runner` exception
  net to `(TrialFailure, AssertionError, SchemaError)` and re-raise provider
  errors so D-19 fail-fast holds; IN-01 plumb `runtime.trace[*].usage` into
  `TrialOutcome.token_cost_observed`; IN-08 extract `max_retries=3`
  provider-side budget into `deepseek_provider_from_env(..., max_retries=3)`.

Sequencing recommendation (from charter): A/D/E (re-runnable) → C (audit
gated on a real-LLM batch) → WR-03/WR-04 callsite/IN-08 (pure cleanup) → F
(evolution wiring) → B (transient retry wraps the new wiring) → WR-01/WR-02/
WR-05/IN-01 (touch the new wiring directly).

Scope guardrails: no new evolution-design changes — phase 6 designed
evolution; phase 8 only *connects* phase 6 evolution to phase 7 runner. Group 1
is required for phase-7 acceptance to actually re-run cleanly, not stretch
goals.

## Execution Rule

Proceed in numeric order. Phase 4 may be completed before broader cleanup. Phase
6 depends on Phase 5; Phase 7 depends on Phase 6; Phase 8 unblocks the Phase 7
real-LLM acceptance gate.
