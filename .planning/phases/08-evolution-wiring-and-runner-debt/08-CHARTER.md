---
phase: 08-evolution-wiring-and-runner-debt
status: stub
created: 2026-05-27T02:55:00Z
parent_decision: phase-7 Option 3 — defer runner-touch fixes + evolution wiring
---

# Phase 8 — Runner ↔ Evolution Wiring + Runner-Debt Cleanup

## Charter

Phase 7's revised acceptance bar (2026-05-27) required, among five
conditions, that "the evolution mechanism is observed firing on real
runs (at least one non-empty `trials[]` in an `evolution_snapshot.json`)."
Investigation during phase 7 surfaced that the current
`seers_harness/validation/runner.py`:

- creates `events: list[dict] = []` per request,
- passes it to `_run_one_request`,
- reduces it via `write_evolution_snapshot(events, ...)`,

but **never invokes `assemble_portfolio(...)` or `run_request_trial(...)`**,
and never seeds the `delta_portfolio` with a candidate. The result is
that `trials[]` is structurally always empty regardless of how long the
runner runs.

This is not a runner defect against phase-7 charter — phase 7's plan
07-01 only added the *observability seam* on the evolution module; the
*runner-side wiring* was left for a follow-up. Phase 8 is that follow-up.

## Goals

1. **Wire runner ↔ evolution.** Make `_run_one_request` call
   `assemble_portfolio` + `run_request_trial` (with `events=events`)
   when `delta_portfolio` is non-empty. Seed at least one test delta
   into the portfolio at process start so `trials[]` is observably
   non-empty on real-LLM runs.
2. **Migrate the 7 phase-7 runner-debt items** (deferred from
   `07-WRIN-TRIAGE.md`):
   - **WR-01** Stage 3 fail-fast must drain in-flight futures before
     stopping, so disk and `index.json` agree on which requests ran.
   - **WR-02** Wrap `flush_evidence` / `write_evolution_snapshot` in
     the runner's `finally` clause with best-effort logging so a
     cleanup failure does not mask the original exception.
   - **WR-03** Delete the duplicate `_detect_delimiter` in `runner.py`
     and use the canonical one from
     `seers_harness.intake.request_preprocessor`.
   - **WR-04 callsite** Migrate runner's `_cv.reset(token)` to the
     public `reset_current_node_id(token)` helper landed in
     `aa49f06`.
   - **WR-05** Narrow `trial_runner`'s `except Exception` to
     `(TrialFailure, AssertionError, SchemaError)` and re-raise
     `(ProviderAuthError, ProviderRateLimitError, ProviderTransientError)`
     so D-19 fail-fast holds once trials actually run.
   - **IN-01** Plumb `runtime.trace[*].usage` into
     `TrialOutcome.token_cost_observed` so the field is real, not dead.
   - **IN-08** Extract the `max_retries=3` provider-side budget into
     `deepseek_provider_from_env(..., max_retries=3)` and remove the
     `"max_" + "retries"` scan-evasion in the runner.

## Scope guardrails

- Runner ↔ evolution wiring is the **primary** deliverable. The 7
  runner-debt items are batched along with it; they are not the lead.
- No new evolution-design changes — phase 6 designed evolution; phase 8
  only *connects* phase 6 evolution to phase 7 runner.
- Re-run real-LLM Stage 1 + Stage 2 + Stage 3 after wiring lands; the
  acceptance gate now includes "at least one non-empty `trials[]` in
  the produced `evolution_snapshot.json`."

## Open questions for the user (when phase 8 starts)

1. What test delta should be seeded at process start? Options: a
   no-op patch on `discover-personalization-factors/SKILL.md` for
   smoke purposes, or a real prompt-level delta from
   `.planning/intel/` so the trial measures something meaningful.
2. Trial cadence — fire one trial per N host requests, or one per
   `assemble_portfolio` policy decision (phase-6 default)?
3. How much of the 7 runner-debt items should land *before* the
   evolution wiring (so phase 8's first commit is debt-cleanup) vs
   *after* (wiring first, then debt)? Recommendation: WR-03/04/IN-08
   first (pure cleanup), then wiring, then WR-01/02/05/IN-01 (touch
   the new wiring directly).

## Status

- 2026-05-27T02:55:00Z — stub created; awaits user kick-off after
  phase 7 closes (real-LLM batch on PID 98270 + case_analysis F1..F4).
