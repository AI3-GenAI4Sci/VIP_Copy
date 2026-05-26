# DeepSeek Rate-Limit Facts (2026-05-26)

This document records the **read-only** facts that govern how the workspace
harness talks to DeepSeek today. It is the single source of truth for the
rate-limit-and-retry surface during Phase 6, and it is paired with
`seers_harness.provider_runtime.openai_compatible.deepseek_runtime_facts()`
so docs and code never drift.

**Phase 6 explicitly does not tune concurrency or add a limiter.** This
document is fact recording only. Any concurrency/limiter work belongs to
a later phase that has real DeepSeek production traffic to learn from.

## Fact Date

- **Recorded:** 2026-05-26
- **Source:** the locked ADR-PROBE-7.1.1 plus the static defaults baked into
  `seers_harness/provider_runtime/openai_compatible.py`.

## Current Facts

| Fact                            | Value                              |
| ------------------------------- | ---------------------------------- |
| Default model                   | `deepseek-v4-pro`                  |
| Default base URL                | `https://api.deepseek.com/beta`    |
| Default request timeout         | 60 seconds                         |
| SDK max retries: 0              | (no SDK-level auto-retry)          |
| `reasoning_effort`              | `max`                              |
| `thinking` enabled              | yes (`{"type": "enabled"}`)        |
| `tool_choice`                   | `auto`                             |
| 429 / rate-limit error category | `rate_limit`                       |

These values come straight out of `deepseek_runtime_facts()`. If the live
defaults change, update both the function and this table together.

## Error Classification

`seers_harness.core.errors.classify_exception` maps exception text and type
into the workspace error taxonomy. A 429-shaped exception (HTTP 429, the
literal phrase "rate limit", or the SDK's `RateLimitError`) classifies as
`rate_limit` and is wrapped in `ProviderRateLimitError`.

The Phase-6 contract is that this classifier is the only rate-limit signal
the harness reacts to. There is no separate header probe and no in-process
limiter — see "Optional Probe Policy" below.

## Optional Probe Policy

A real-network probe of DeepSeek's response headers is **off by default**.
Tests must not call the network. If a future operator wants to spot-check
visible rate-limit headers (e.g. `x-ratelimit-*`, `retry-after`), they may
add an opt-in script that:

1. Requires `DEEPSEEK_API_KEY` to be present in the environment.
2. Runs only when an explicit `--probe` / `RUN_DEEPSEEK_PROBE=1` flag is
   set, never on `pytest` collection.
3. Records exactly which headers were observed and which were absent. If
   the probe cannot see a header, the document must say so plainly — it
   must not claim a header exists when none was observed.

The current state, as of the fact date above, is: no probe has been run in
this workspace, so no real-header observations are claimed.

## Phase-6 Non-Goal: Concurrency Tuning And Limiters

Phase 6 records facts; it does not introduce:

- a `Limiter` / `RateLimiter` / circuit-breaker class,
- a token-bucket / leaky-bucket scheduler,
- a `concurrency_tuning` module or config,
- in-process retry-with-backoff that bypasses the SDK's `max_retries=0`,
- any production-grade scheduling machinery on top of `WorkflowRuntime`.

Real DeepSeek production concurrency tuning is deferred to Phase 7 (real-LLM
validation), where there will be actual traffic to measure. The fake-provider
concurrency safety verification in plan 06-03 covers harness-side state
isolation only — it does not claim DeepSeek-side capacity.

## Phase-7 Hook Point For Long-Run Progress

When Phase 7 wires real DeepSeek calls into long-running scenario sweeps,
the natural hook for `seers_harness.workflow.progress.ProgressReporter` is
the request loop that fans out scenarios into `WorkflowRuntime.run_request`
calls. The reporter writes one plain line per request — `--no-progress` /
CI mode produces log-friendly output. See
`seers_harness/workflow/progress.py` for the surface.

Phase 6 deliberately does not refactor `tests/smoke/test_e2e_smoke.py` to
attach the reporter, because the existing 20-request smoke prints its own
plain `smoke i/N: <request_id>` line per request and the assertions there
are already the Phase-5 reference shape.
