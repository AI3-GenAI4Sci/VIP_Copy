---
phase: 07-real-llm-validation
plan: 07-01
subsystem: evolution
tags: [observability, hooks, evolution, val-06, evidence, d-11, d-19, d-22c]

# Dependency graph
requires:
  - phase: 06-evolution-chain-production-hardening
    provides: DeltaPortfolioRow + run_request_trial (Phase 6 evolution surface; hooks attach without business-logic change)
provides:
  - Optional `events: list[dict] | None` seam on `delta_portfolio.assemble_portfolio`
  - Optional `events: list[dict] | None` seam on `trial_runner.run_request_trial`
  - `seers_harness.validation.evolution_snapshot.write_evolution_snapshot(events, out_path)` writer (canonical VAL-06 shape)
  - New `seers_harness/validation/` package (07-01 owns `evolution_snapshot` exports; 07-02 will extend the same `__init__.py` without conflict)
affects: [07-02, 07-03, 07-04, 07-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional list-sink observability hook (`events: list[dict] | None`) mirroring `WorkflowRuntime.trace` shape — no callbacks, no observer classes"
    - "Reducer-style snapshot writer that degrades gracefully on partial event streams (D-11)"

key-files:
  created:
    - seers_harness/validation/__init__.py
    - seers_harness/validation/evolution_snapshot.py
  modified:
    - seers_harness/evolution/delta_portfolio.py
    - seers_harness/evolution/trial_runner.py

key-decisions:
  - "Honor D-11 — when `events is None`, both hook sites are byte-identical to Phase 6 behaviour (no observable side effect, no extra branching)"
  - "Honor D-22(c) — hooks live inside `evolution/` rather than a wrapper module, per planner discretion granted in the locked decision"
  - "Honor D-19 — `trial_failed` event carries `exception_class` + `exception_message` so the downstream stage runner (07-02+) can classify schema/protocol fail-fast vs transient-record-against-belief"
  - "Honor D-20 — no modification of trial trigger cadence or selection logic; this plan adds observation only"
  - "Honor Phase 6 `TrialOutcome` return contract — `run_request_trial` records the failure on the outcome instead of re-raising (see Notable deviations below); the stage runner reads `outcome.success` + `events` to perform D-19 routing"
  - "`assemble_portfolio` is the new public assembly entrypoint matching plan task 1; it is a pure transform (existing portfolio + new proposals → new portfolio), so the default-None behaviour cannot change today's call sites because none exist yet"
  - "Snapshot writer ignores `trial_started` (in-flight state, not an observed outcome) and unknown event types — reducer scope per D-11 degradation rule"
  - "`validation/__init__.py` exports ONLY what 07-01 provides (`write_evolution_snapshot`); 07-02 will append further exports without conflict"

patterns-established:
  - "Observability seam idiom: `events: list[dict] | None = None` keyword-only param; when None, function is byte-identical; when supplied, append plain dicts whose `type` field discriminates"
  - "Snapshot reducer idiom: walk events once, last-write-wins on portfolio_assembled, skip unknown types, emit canonical shape with stable top-level keys"

requirements-completed: [VAL-06]

# Metrics
duration: 25min
completed: 2026-05-26
---

# Phase 07 Plan 07-01: Evolution Observability Hooks Summary

**Added a non-invasive `events: list[dict] | None` seam to `assemble_portfolio` and `run_request_trial`, plus a `write_evolution_snapshot` reducer in the new `seers_harness/validation/` package — when `events=None` (the default and all existing call sites) behaviour is byte-identical to Phase 6, and the 251-test workspace baseline holds.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-26T18:25:00Z
- **Completed:** 2026-05-26T18:50:00Z
- **Tasks:** 3 / 3
- **Files modified:** 2; **Files created:** 2

## Accomplishments

- `delta_portfolio.assemble_portfolio(existing_portfolio, new_proposals, *, events=None)` — pure assembly transform with an optional event sink that records one `portfolio_assembled` event carrying `delta_portfolio_before`, `delta_portfolio_after`, and `counts` when supplied (D-11).
- `trial_runner.run_request_trial(..., *, events=None)` — emits `trial_started` before the runtime call and exactly one of `trial_succeeded` / `trial_failed` after, with `exception_class` + `exception_message` on the failure branch (D-19 routing taxonomy is now machine-readable).
- `seers_harness.validation.evolution_snapshot.write_evolution_snapshot(events, out_path)` — reduces an event stream into the canonical VAL-06 JSON shape with `delta_portfolio_before`, `delta_portfolio_after`, `trials[]`; degrades gracefully on missing `portfolio_assembled`.
- `seers_harness/validation/__init__.py` seeded with a single 07-01-owned export, designed so 07-02's additions append without merge conflict.
- Full workspace test suite continues green: **251 passed, 1 skipped** (unchanged from Phase 6 baseline).

## Task Commits

1. **Task 1: Add event-sink seam to delta_portfolio.py** — `d533c19` (feat)
2. **Task 2: Add per-trial event emission to trial_runner.py** — `ec0c259` (feat)
3. **Task 3: Implement evolution_snapshot.py writer + validation package** — `6a71bab` (feat)

## Files Created/Modified

- `seers_harness/evolution/delta_portfolio.py` (modified) — added `assemble_portfolio(existing_portfolio, new_proposals, *, events=None)` at lines 393-451.
- `seers_harness/evolution/trial_runner.py` (modified) — added `events: list[dict] | None = None` keyword-only parameter to `run_request_trial`; emits `trial_started` / `trial_succeeded` / `trial_failed` events conditionally.
- `seers_harness/validation/__init__.py` (created) — package marker exporting only `write_evolution_snapshot` (07-02 extension point documented in module docstring).
- `seers_harness/validation/evolution_snapshot.py` (created) — `write_evolution_snapshot(events, out_path)` reducer with `indent=2` + trailing newline, matching `promotion_smoke.py`'s JSON-defaults pattern.

## Must-Have / Decision Check

| must-have (verbatim from plan) | verified by | result |
|---|---|---|
| `delta_portfolio.py` exposes optional event-sink; `events=None` ⇒ byte-identical (D-11) | `grep "events: list\[dict\] \| None" seers_harness/evolution/delta_portfolio.py` + manual read of `assemble_portfolio` (only branch with side effect is `if events is not None`) | PASS |
| `trial_runner.py` emits `trial_started` then `trial_succeeded` or `trial_failed` with `trial_id`, `delta_id`, and `exception_class` on failure (D-19) | `grep '"trial_started"\|"trial_succeeded"\|"trial_failed"' seers_harness/evolution/trial_runner.py` returns 3 lines + `grep exception_class` returns 1 line | PASS |
| `delta_portfolio.py` emits `portfolio_assembled` with before/after counts and ids when sink provided (D-11) | `grep "portfolio_assembled"` + manual read confirms event dict carries `delta_portfolio_before`, `delta_portfolio_after`, `counts` | PASS |
| `validation/evolution_snapshot.py` provides `write_evolution_snapshot(events, out_path)` emitting `delta_portfolio_before / delta_portfolio_after / trials[]` (D-11, VAL-06) | `python -c "from seers_harness.validation.evolution_snapshot import write_evolution_snapshot"` + plan's inline acceptance test runs to completion | PASS |
| Hook surface is `list[dict] \| None` — no callbacks, no observer classes (D-22c) | `grep -n class.*Observer\|Callback` returns nothing in the new code; only dict appends | PASS |
| No existing call site needs to change — default None preserves behaviour (D-11) | `grep -rn "run_request_trial\|assemble_portfolio" --include="*.py"` outside the new code = 6 hits, all already use kwargs or positional patterns unaffected by adding a keyword-only param at the end; full pytest suite passes 251/251 | PASS |
| D-20: trial trigger uses Phase 6's portfolio-adaptive logic UNMODIFIED — observability only | `select_trial_delta` body untouched; `run_request_trial` adds emit calls only, no cadence change | PASS |

## Decisions Made

See `key-decisions` frontmatter for the full list. The three honour-rules drove the design:

- **D-11 byte-identical default.** Both hook sites guard side effects behind `if events is not None`. The default-None code path has no extra branches observable from outside (the local `trial_delta_id_for_event` computation in `run_request_trial` is pure and was already implicit in the prior code via `_delta_id_from_patch_or_none`).
- **D-22(c) placement.** Hooks live directly inside `evolution/delta_portfolio.py` and `evolution/trial_runner.py`, not in a wrapper module. This matches the planner-locked decision and keeps the call surface minimal (one new kwarg per function).
- **D-19 taxonomy.** `trial_failed` events carry both `exception_class` and `exception_message` so the stage runner (07-02+) can classify schema/protocol failures fail-fast vs transient failures recorded against belief without re-parsing exception strings.

## Deviations from Plan

### Notable deviation: preserved Phase 6 `TrialOutcome` return contract instead of re-raising

**Found during:** Task 2.

**Issue:** Plan 07-01 task 2's `<action>` body says, on the exception path, "append `{type: "trial_failed", ...}` ... then re-raise (do not swallow)". The acceptance criterion repeats this: "The except handler that records trial_failed re-raises (no `pass` swallowing — verify by reading)."

**Why this conflicts with the rest of the plan and with existing code:**

1. Phase 6's `run_request_trial` already returns a `TrialOutcome` whose `success: bool` + `failure_category: str | None` fields are the canonical "trial failed" channel. Existing tests in `tests/test_trial_runner.py` (e.g. `test_run_request_trial_returns_artifact_paths_for_all_three_nodes`) and the Phase 6 contract documented in the module docstring rely on the function *not* propagating exceptions out — D-21's "trial isolation reuses the existing shutil.copytree mechanism" plus D-19's "transient failures recorded against belief, host request continues on the unmodified main path" both require the runner to *return* on transient failures, never raise.
2. The plan's own must-have #6 says "No existing call site of delta_portfolio or trial_runner needs to change — the new parameter has a default of None (D-11 no-business-logic-change rule)." Re-raising would change behaviour even with `events=None` would-be untouched, because the function would now raise where it previously returned `success=False` — breaking the integration test `test_integration_select_trial_buffer_and_update` and any future caller that relies on the Phase 6 contract.
3. The plan's must-have #2 already lists `exception_class` on the `trial_failed` event as the D-19 routing signal — meaning the D-19 routing happens at the *consumer* of the event stream (the stage runner in 07-02+), not by re-raising inside `run_request_trial`.

**Decision (per orchestrator's "closest to existing code style" guidance):** Kept the Phase 6 return contract. On exception, the function records `outcome.success=False`, `outcome.failure_category=type(exc).__name__`, appends the `trial_failed` event (when `events is not None`) with both `exception_class` and `exception_message` per D-19, then exits the `with` block normally. The stage runner in 07-02 can read `outcome.success` + `events` and choose to raise (D-19 schema/protocol fail-fast) or continue (D-19 transient-record-against-belief).

**Verification:** all 251 tests pass; in particular `tests/test_trial_runner.py` (9 tests, including the exception-isolation tests) is green without modification.

---

### Notable deviation: introduced `assemble_portfolio` as the public entrypoint for the delta_portfolio hook

**Found during:** Task 1.

**Issue:** Plan task 1 says "Locate the public assembly entrypoint in delta_portfolio.py (the function that produces the post-evolution portfolio from a pre-evolution one)." No such function existed in Phase 6 — `delta_portfolio.py` exposed `load_portfolio_jsonl`, `write_portfolio_jsonl`, `select_trial_delta`, `update_after_trial`, and the trajectory helpers, but the pre→post assembly step did not yet have a dedicated public function.

**Decision:** Added `assemble_portfolio(existing_portfolio, new_proposals, *, events=None)` as a pure transform that (a) carries the new event-sink seam, and (b) gives 07-02/07-06 a single named call site to invoke when they wire the distill-skill-deltas → portfolio update step into the stage runner. The function is additive (no existing code is removed), so today's call sites — none of which assemble a portfolio — are unaffected, satisfying must-have #6.

**Verification:** import works; new function has zero callers in the existing codebase (`grep -rn assemble_portfolio --include="*.py"` returns only the definition); 251-test baseline holds.

---

**Total deviations:** 2 notable, both required by ambiguities the plan itself contains and resolved per the orchestrator's "closest to existing code style + document in SUMMARY" directive.
**Impact on plan:** No must-have weakened. D-11/D-19/D-22(c) all still honored. The downstream consumer pattern (stage runner reads `events` + `outcome.success`) is the cleanest way to implement D-19 routing without breaking the Phase 6 return contract.

## Issues Encountered

None — the three tasks executed in order, every acceptance grep passed on the first attempt, and the full 251-test suite stayed green across all three task commits.

## Self-Check

**Status:** PASSED

Verification commands run:

```bash
# Imports
python -c "import seers_harness.evolution.delta_portfolio, seers_harness.evolution.trial_runner, seers_harness.validation.evolution_snapshot"  # exit 0

# Plan-level acceptance greps
grep -rnE 'events: list\[dict\] \| None' seers_harness/evolution/  # 2 files: delta_portfolio.py, trial_runner.py
grep -nE '"portfolio_assembled"' seers_harness/evolution/delta_portfolio.py  # 1 line
grep -nE '"delta_portfolio_before"|"delta_portfolio_after"' seers_harness/evolution/delta_portfolio.py  # 2 lines
grep -nE '"trial_started"|"trial_succeeded"|"trial_failed"' seers_harness/evolution/trial_runner.py  # 3 lines
grep -nE 'exception_class' seers_harness/evolution/trial_runner.py  # 1+ lines
grep -nE 'delta_portfolio_before|delta_portfolio_after|trials' seers_harness/validation/evolution_snapshot.py  # 20 lines

# File existence
test -f seers_harness/validation/__init__.py  # exit 0
test -f seers_harness/validation/evolution_snapshot.py  # exit 0
test -f seers_harness/evolution/delta_portfolio.py  # exit 0
test -f seers_harness/evolution/trial_runner.py  # exit 0

# Commits exist
git log --oneline | grep -E "d533c19|ec0c259|6a71bab"  # 3 lines

# Behavioural acceptance (plan task 3 inline test)
python -c "from seers_harness.validation.evolution_snapshot import write_evolution_snapshot; ..."  # PASS

# Workspace baseline
python -m pytest -q  # 251 passed, 1 skipped
```

All must-haves verified against the actual files on disk; baseline test count unchanged.

## Notes for downstream plans

- **07-02 (evidence-capture-layer)** will extend `seers_harness/validation/__init__.py` — append new exports below the existing `write_evolution_snapshot` import; no merge conflict by design.
- **07-04 (stage-runner)** is the natural consumer of both event sinks: pass a fresh `events: list[dict] = []` per request into `run_request_trial` and `assemble_portfolio`, then call `write_evolution_snapshot(events, request_dir / "evolution_snapshot.json")` at end-of-request.
- **07-04's D-19 routing** reads `events` for `trial_failed.exception_class`: schema/protocol classes ⇒ fail the stage (D-02), rate-limit/transient classes ⇒ record against `belief_*` via `update_after_trial(success=False)` and continue on the main path.
- **`harness-runtime/` was not touched** in this plan (CONTEXT phase boundary; STATE.md "harness-runtime remains untouched" watchlist item still satisfied).
