---
phase: 06-evolution-chain-production-hardening
plan: 06-03
subsystem: smoke
tags: [smoke, concurrency, fake-provider, isolation, trajectory]
requirements_completed: [PROD-01, PROC-02]
dependency_graph:
  requires:
    - "tests/fakes/scripted_provider.py — ScriptedProvider base shape and message-capture behavior"
    - "tests/smoke/scripted_full_chain.py — build_full_chain_script, make_nodes for 3-node DAG"
    - "seers_harness/workflow/dag_runner.py — WorkflowRuntime.run_request and per-node session_id stamping"
    - "seers_harness/evolution/delta_portfolio.py — TrajectoryRecord and buffer_trajectory from 06-02"
  provides:
    - "tests/fakes/scripted_provider.py — DelayedScriptedProvider variant with synthetic per-call latency"
    - "tests/smoke/test_concurrency_smoke.py — 20-request concurrent harness-safety smoke"
  affects:
    - "future Phase 6 plans 06-04 (progress UX) and 06-05 (promotion smoke) — they may reuse the per-thread runtime/provider pattern when they need concurrent fake-provider drivers"
tech-stack:
  added: []
  patterns:
    - "per-request isolation via fresh DelayedScriptedProvider + WorkflowRuntime instances on each thread"
    - "synthetic-latency subclass (time.sleep before delegate) preserves base provider's message capture and protocol exactly"
    - "owner-segment artifact paths ('req-{request_id}/...') so file-system contamination is a structural assertion, not a string heuristic"
    - "explicit scope-boundary docstring (D-18 / D-19 / D-21) keeps fake-provider safety results from being misread as real DeepSeek concurrency tuning"
key-files:
  created:
    - tests/smoke/test_concurrency_smoke.py
  modified:
    - tests/fakes/scripted_provider.py
decisions:
  - "DelayedScriptedProvider subclasses ScriptedProvider rather than wrapping; same constructor field order, same received_messages capture, same scripted-turn indexing — existing tests stay green without edits."
  - "Scenarios are constructed in-process per request (no data_100k.csv dependency) so the smoke runs in any tree."
  - "Each request gets its own DelayedScriptedProvider instance — sharing one provider across threads is explicitly forbidden by the plan."
  - "Cross-request contamination is asserted via JSON-serialized provider snapshots, runtime records, runtime trace, and the trajectory record; foreign request id substrings produce a named failure message identifying the contaminator."
  - "session_id uniqueness is asserted across all 20 requests (not just within one) so the uuid hex inside WorkflowRuntime's session_id format catches any cross-request reuse."
  - "Trajectory records use 06-02's TrajectoryRecord + buffer_trajectory directly so the trajectory leg of the smoke uses production helpers, not test-private stubs."
  - "Per-call delay is 0.005s — small enough to keep the smoke under one second on CI, large enough to interleave 20 threads."
metrics:
  duration: "~10 minutes"
  completed_date: "2026-05-26"
  tests_added: 1
  tests_passing: 213
  baseline_before: 213
---

# Phase 6 Plan 06-03: Realistic-Latency Fake-Provider Concurrency Safety Summary

Plan 06-03 verifies harness concurrency safety — and only harness
concurrency safety — by running 20 fake-provider request runs
through the 3-node DAG simultaneously and asserting that artifact
paths, tool-loop state, provider message snapshots, runtime records,
runtime trace events, session ids, and trajectory records do not
cross-contaminate across simultaneously running requests.

## Goal

Prove that the runtime, provider base, payload builders, tool-loop,
and trajectory helpers hold no concealed cross-request mutable state
when callers run multiple requests concurrently with fresh per-request
runtime and provider instances. The scope is deliberately tight: this
is harness safety, not real DeepSeek concurrency capacity (D-18, D-19,
D-21).

## Outputs

| Task | Scope | Commit |
|---|---|---|
| 06-03-01 | `DelayedScriptedProvider` subclass in `tests/fakes/scripted_provider.py` — preserves base protocol, adds configurable per-call sleep | `8b07845` |
| 06-03-02 | `tests/smoke/test_concurrency_smoke.py` — 20-request ThreadPoolExecutor smoke, artifact count + uniqueness + per-node forbid-schema validation | `bbd197f` |
| 06-03-03 | Cross-request contamination assertions — provider snapshots, runtime records/trace, trajectory records, session_id uniqueness, artifact owner-segment containment | `dba7897` |
| 06-03-04 | Scope-boundary docstring expansion — explicit D-18 / D-19 / D-21 framing; negative-scope phrasing keeps the only `limiter|circuit` mention inside an explicit forbid statement | `feabfdd` |

## Requirement Coverage

- **PROD-01** — Stress concurrency 20 with realistic FakeProvider
  latency. The smoke spawns 20 ``DelayedScriptedProvider`` request
  runs on a ``ThreadPoolExecutor`` and asserts the harness produces 60
  unique artifact paths, 60 schema-valid artifact files, and zero
  cross-request leakage in provider/runtime/trajectory state. The
  per-call delay is synthetic by design — real DeepSeek concurrency
  capacity is out of scope (D-21).
- **PROC-02** — PLAN.md names `systematic-debugging` and
  `verification-before-completion`. Per-task acceptance gates ran
  green before each commit. The full 213-test suite ran green after
  the final commit; the per-plan focused gate
  (`pytest tests/smoke/test_concurrency_smoke.py -q`) ran green at
  every task boundary.

## Verification Gates

All plan-level verification commands pass:

| Gate | Result |
|---|---|
| `pytest tests/test_tool_loop_happy_path.py tests/smoke/test_e2e_smoke.py -q` | 3 passed, 1 skipped in 0.07s |
| `pytest tests/smoke/test_concurrency_smoke.py -q` | 1 passed in 0.14s |
| `pytest -q` (full suite) | 213 passed, 1 skipped in 0.42s |
| `rg -n 'limiter\|circuit\|DeepSeek concurrency tuning' tests/smoke/test_concurrency_smoke.py` | 1 hit, on the explicit forbid-list line ("Adding a provider limiter, circuit breaker, retry manager, or…") — allowed under acceptance criterion ("returns 0 except any negative-scope phrase that says the test is not tuning DeepSeek concurrency") |

The single ``data_100k.csv``-backed smoke
(`test_e2e_smoke_20_requests`) skips when the CSV is absent in the
worktree; this is the existing behavior from Phase 5 and is unchanged
by Plan 06-03.

## DelayedScriptedProvider Shape

`DelayedScriptedProvider` is a dataclass subclass of
`ScriptedProvider` carrying one extra field, `delay_seconds: float =
0.005`. Its `generate_with_tools` overrides the base method to call
`time.sleep(delay_seconds)` (when positive) before delegating to
`super().generate_with_tools(...)`. Because the dataclass extends the
base dataclass, the constructor field order stays compatible:
`DelayedScriptedProvider(script=..., delay_seconds=...)` is the
canonical call. The base provider's `received_messages` capture and
scripted-turn indexing are inherited unmodified.

Phase 5 tests that construct `ScriptedProvider` continue to work
unchanged; the new subclass is reserved for the concurrency smoke.

## Concurrency Smoke Shape

`test_concurrent_fake_provider_requests_do_not_cross_contaminate`:

1. Builds 20 synthetic scenarios with deterministic ids `R-00..R-19`
   and a per-request product `P-R-{id}`. Scenarios use empty
   `user_state.behavior` so the copy-generation user-history leak
   check (in `seers_harness/tools/skill_tools.py`) keeps the leak set
   empty by construction and the canonical scripted candidate text
   accepts unconditionally.
2. For each request, a worker function builds a fresh
   `DelayedScriptedProvider` from `build_full_chain_script()` (whose
   `script` it consumes), a fresh `WorkflowRuntime` with a unique
   `output_dir = tmp_path / f"req-{request_id}"`, and a fresh
   `make_nodes()` list.
3. A `ThreadPoolExecutor(max_workers=20)` runs all 20 worker
   invocations concurrently. The synthetic 0.005s sleep before every
   provider call interleaves thread scheduling so any shared mutable
   state would surface as cross-request contamination.
4. Each worker constructs a `TrajectoryRecord` (06-02's
   production trajectory contract) from its own runtime trace and
   artifact paths.
5. After all futures complete, six independent assertion blocks run.

## Cross-Request Contamination Assertions

For each request `R-i`:

- **Provider snapshot scan:** JSON-dump `provider.received_messages`
  and assert no other `R-j` (j != i) substring appears. Failure
  message names the contaminating id.
- **Runtime records scan:** JSON-dump `runtime.records` (the
  RUNNING/SUCCEEDED/FAILED node-run rows) and assert no foreign
  request id appears.
- **Runtime trace scan:** JSON-dump `runtime.trace` (the
  `provider_call` / `tool_loop_summary` / `node_retry_decision`
  events) and assert no foreign request id appears.
- **Trajectory scan:** dump the per-request `TrajectoryRecord` as JSON
  and assert no foreign request id appears in its serialized form.
- **session_id uniqueness:** track the `{node.id}:attempt-{n}:{uuid}`
  session_id from every runtime record across all 20 requests. Two
  different requests producing the same session_id raises an explicit
  cross-owner assertion with both request ids in the message.
- **Owner-segment artifact paths:** each artifact path must contain
  `req-{request_id}` exactly once and must not reference any sibling
  request's owner segment. This is a structural assertion on
  `Path.parts`, not a string heuristic.
- **Trajectory buffer composition:** fold every per-request
  `TrajectoryRecord` through 06-02's `buffer_trajectory` and assert
  the resulting buffer has 20 rows, each owning exactly one
  request_id, with no foreign `req-{other}` segment in any row's
  `artifact_paths` values.

Two-digit zero-padded request ids (`R-00..R-19`) avoid the substring
ambiguity that would arise with single-digit ids (`R-1` is a substring
of `R-10`). This is a deliberate choice documented in the in-source
comment so future edits cannot regress it.

## Scope Boundary (D-18 / D-19 / D-21)

The top-of-file docstring carries an explicit two-section scope
statement:

- **In scope (D-18):** harness-side concurrency safety verification.
  Twenty fake-provider request runs proving runtime, provider base,
  payload builders, tool-loop, and trajectory helpers hold no
  concealed cross-request mutable state.
- **Out of scope (D-19, D-21):** real DeepSeek concurrency capacity,
  rate-limit behavior, or production tuning. Adding a provider
  limiter, circuit breaker, retry manager, or scheduling machinery on
  the basis of a fake-provider result is explicitly forbidden;
  modeling real DeepSeek latency is also explicitly forbidden — the
  per-call sleep is synthetic.

`rg -n 'limiter|circuit|DeepSeek concurrency tuning'
tests/smoke/test_concurrency_smoke.py` returns exactly one hit, on the
sentence that says these are out of scope. The plan's acceptance
criterion explicitly permits negative-scope phrases.

## Threat Model Coverage

| Threat | Mitigation | Evidence |
|---|---|---|
| T-06-07 (concurrent runs leak messages, paths, or records across requests) | Smoke asserts per-request provider snapshots, output dirs, artifact paths, session_ids, runtime records, runtime trace events, and trajectory records are owner-scoped | `test_concurrent_fake_provider_requests_do_not_cross_contaminate` — six assertion blocks, every block names the contaminating request id on failure |
| T-06-08 (a test accidentally hides a global-state bug by running providers without realistic latency) | `DelayedScriptedProvider` sleeps `delay_seconds=0.005` per `generate_with_tools` call before delegating, so 20 threads actually interleave on the GIL boundary rather than running back-to-back instantly | `tests/fakes/scripted_provider.py` `DelayedScriptedProvider.generate_with_tools` |

## Decisions Made

- **Subclass over wrap:** `DelayedScriptedProvider` is a
  `@dataclass`-subclass of `ScriptedProvider` so the base
  `received_messages` capture, `last_usage` field, and scripted-turn
  indexing all carry through without rewrap glue. The base
  `ScriptedProvider` stays untouched and its existing tests stay
  green.
- **In-process scenarios:** the smoke does not depend on
  `data_100k.csv` (it is absent from this worktree). Scenarios are
  built by `_scenario_for(request_id)` with empty user_state behavior
  so the leak check on copy generation passes unconditionally for the
  canonical scripted text.
- **Two-digit owner segments:** `R-00..R-19` avoids `R-1` being a
  substring of `R-10`, so contamination assertions cannot produce a
  false positive on a benign id collision.
- **Use 06-02 trajectory helpers, not test stubs:** the trajectory
  leg of the smoke uses production `TrajectoryRecord` and
  `buffer_trajectory`. The plan's threat model assumes the
  trajectory primitives are the production ones; substituting a
  stub would weaken the proof.
- **One commit per task:** four commits, one per plan task. The
  scope-boundary doc commit (`feabfdd`) is `docs(06-03)` rather than
  `test(06-03)` because it adjusts comment prose only — no test
  behavior change.

## Deviations from Plan

None. Plan executed exactly as written. The `data_100k.csv` fallback
note in task 02 ("reuse the Phase 5 scratch-CSV helper if
`data_100k.csv` exists") resolved to the in-memory branch since the
CSV is not in this worktree, which is the plan's intended behavior.

## What Stayed Fixed

- `workflow-skills/current/` — untouched.
- `harness-runtime/` — untouched. D-23 boundary preserved.
- `seers_harness/` — untouched. No production code changed in this
  plan; the only modification is to a test fake
  (`tests/fakes/scripted_provider.py`) and the only new file is the
  concurrency smoke test. This honors the plan's forbid list ("mutating
  production code solely to make a test easier").
- `ScriptedProvider` (base) — untouched. The delayed subclass adds
  behavior without altering the base.

## Handoff To Next Plans

- **06-04** (progress UX): can read `runtime.trace` and the
  per-request `TrajectoryRecord` produced here for a concurrent
  "delta trial count" / "completed/total" progress line. The
  per-thread isolation contract verified by this plan tells 06-04 it
  can safely sample multiple per-request runtimes without
  cross-contaminating progress counters.
- **06-05** (promotion smoke): the per-request fresh runtime +
  provider pattern is reusable for a dry-run promotion smoke that
  needs more than one concurrent request.

## Known Stubs

None. The smoke does not introduce any UI-bound placeholder data or
unwired components.

## Self-Check

- created files exist:
  - `tests/smoke/test_concurrency_smoke.py` — FOUND
- modified files exist:
  - `tests/fakes/scripted_provider.py` — FOUND (DelayedScriptedProvider added)
- commits exist on branch `worktree-agent-aaf13da39a7293b84`:
  - `8b07845` — FOUND (`test(06-03): add DelayedScriptedProvider for concurrency smoke`)
  - `bbd197f` — FOUND (`test(06-03): add concurrency smoke for fake-provider request runs`)
  - `dba7897` — FOUND (`test(06-03): assert per-request isolation of messages and records`)
  - `feabfdd` — FOUND (`docs(06-03): expand D-18/D-21 scope boundary comment in smoke header`)
- focused gate: 1 passed
- full suite: 213 passed, 1 skipped

## Self-Check: PASSED
