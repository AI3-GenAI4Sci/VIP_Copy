---
phase: 08-evolution-wiring-and-runner-debt
status: stub
created: 2026-05-27T02:55:00Z
last_updated: 2026-05-27T03:40:00Z
parent_decision: phase-7 Option 3 — defer runner-touch fixes + evolution wiring
---

# Phase 8 — Runner ↔ Evolution Wiring + Runner-Debt Cleanup + Phase-7 Real-LLM Hardening

## Charter

Phase 7's revised acceptance bar (2026-05-27) required, among five
conditions, that "the evolution mechanism is observed firing on real
runs (at least one non-empty `trials[]` in an `evolution_snapshot.json`)."
Investigation during phase 7 surfaced two distinct deliverable groups
that share a single root cause — **all touch
`seers_harness/validation/runner.py`** — and one new group that emerged
from the 2026-05-26 real-LLM trajectory analysis (timeout, transient
retry, env handling).

### Why phase 8 (not phase 7)

Phase 7's plan 07-01 only added the *observability seam* on the evolution
module; the *runner-side wiring* was left for follow-up. Separately, the
2026-05-26 real-LLM batch on commit `aa49f06` exposed three real-world
failure modes that phase 7 did not anticipate:

1. **httpx ReadTimeout at 60s default** — DeepSeek-v4-pro reasoning model
   TTFB exceeds 60s on heavy prompts (`reasoning_tokens=2644` observed).
   Surfaced in `tests/smoke/.runs/20260526T183142Z/runner-*.log` as
   `httpx.ReadTimeout → openai.APITimeoutError`.
2. **DeepSeek-side JSON truncation** — `tool_call.arguments` arrived
   truncated mid-`evidence_refs:` at char 940. CR-05 already added a
   bounded parse-layer retry; phase 8 must verify the retry actually
   absorbs this in real-LLM runs (an audit, not a fix).
3. **Shell ENV stale-key drift** — the runner reads `DEEPSEEK_API_KEY`
   from process env. Operators inevitably forget to re-export the latest
   `.env.local` value before launching long batches; the 174546 run
   401-failed because `****92c7` had been rotated to `****ab06` in
   `.env.local` but the shell still held the old key.

None of these are runner *defects against phase-7 charter* — they are
real-LLM operational hardening that landed on the runner-touch boundary.
Phase 8 batches them with the evolution wiring and the seven WR/IN
runner-debt items because all three groups touch the same file.

## Goals

### Group 1 — Phase-7 real-LLM hardening (NEW, post-2026-05-26)

A. **Timeout default 60s → 180s.** Bump
   `seers_harness/provider_runtime/openai_compatible.py:141`
   `DEEPSEEK_TIMEOUT_SECONDS` default from `"60"` to `"180"`. Reasoning
   models with `reasoning_effort="max"` + `thinking={"type":"enabled"}`
   routinely hit 60-90s TTFB; 60s default trips before the first token.
   Operators can still override via env. **Why 180s:** observed worst
   case ≈110s, doubled headroom.

B. **Request-level transient retry.** Wrap `_run_one_request`'s
   `generate_with_tools` invocation with up to 2 additional attempts
   (3 total) on `ProviderTransientError` only. Backoff 5s, 15s. Does not
   affect D-03 (`max_retries=0` SDK setting stays); this is a
   *request*-level retry, not an *HTTP*-level retry. `ProviderAuthError`,
   `ProviderRateLimitError`, `ProviderResponseError`, and
   `TrialFailure`/`AssertionError`/`SchemaError` continue to fail-fast
   per D-02 / D-19.

C. **CR-05 audit (verify, do not modify).** After the next real-LLM
   batch lands at least one `tool_call.arguments` truncation event,
   read the runner log for `parse_retry_*` markers and confirm the
   bounded retry absorbed the truncation without raising. If the audit
   fails (retry exhausted but D-19 routing wrong), file a new WR item.
   No code change unless the audit fails.

D. **Runner `--env-file` flag.** Add an optional
   `--env-file <path>` argument to `runner.py`'s CLI. When provided,
   parse the file (KEY=VALUE lines, `#` comments, no shell expansion)
   and merge into `os.environ` BEFORE constructing the provider. This
   removes the "stale shell env" failure mode permanently —
   the runner reads `.env.local` itself, so the operator no longer has
   to remember `DEEPSEEK_API_KEY="$ENV_KEY" nohup …`.
   **Security:** never log the resolved key; only log
   `loaded N keys from <path>` and the suffix of `DEEPSEEK_API_KEY`
   (last 4 chars).

E. **Failure classification column in `index.json`.** Add
   `failure_class` to each row, drawn from `{auth, rate_limit, transient,
   malformed_tool_args, schema_violation, runner_bug, ok}`. Materialised
   from the existing exception types (`ProviderAuthError →
   auth`, `ProviderRateLimitError → rate_limit`,
   `ProviderTransientError → transient`,
   `ProviderResponseError → malformed_tool_args`,
   `SchemaError → schema_violation`, anything else → `runner_bug`,
   success → `ok`). Lets `batch_summary.json` aggregate by class so
   the operator sees "12/20 failed: 8 transient + 3 timeout + 1 auth"
   instead of an undifferentiated `requests_failed=12`.

### Group 2 — Runner ↔ evolution wiring (PRIMARY phase-8 deliverable)

F. **Wire runner ↔ evolution.** Make `_run_one_request` call
   `assemble_portfolio` + `run_request_trial` (with `events=events`)
   when `delta_portfolio` is non-empty. Seed at least one test delta
   into the portfolio at process start so `trials[]` is observably
   non-empty on real-LLM runs. Closes the phase-7 acceptance condition
   "the evolution mechanism is observed firing on real runs".

### Group 3 — Phase-7 runner-debt (deferred from `07-WRIN-TRIAGE.md`)

G. **Land the 7 phase-7 runner-debt items**:
   - **WR-01** Stage 3 fail-fast must drain in-flight futures before
     stopping, so disk and `index.json` agree on which requests ran.
   - **WR-02** Wrap `flush_evidence` / `write_evolution_snapshot` in
     the runner's `finally` clause with best-effort logging so a
     cleanup failure does not mask the original exception.
   - **WR-03** Delete the duplicate `_detect_delimiter` in `runner.py`
     and use the canonical one from
     `seers_harness.intake.request_preprocessor`.
   - **WR-04 callsite** Migrate runner's `_cv.reset(token)` to the
     public `reset_current_node_id(token)` helper landed in `aa49f06`.
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

- Group 1 (A-E) is **phase-7 hardening** that landed on phase-8 because
  the fixes touch `runner.py` and the long-running real-LLM batch on
  PID 98270 needed to stay on `aa49f06`. They are required for phase-7
  acceptance to actually re-run cleanly; they are not stretch goals.
- Group 2 (F) is the **primary** phase-8 deliverable. The 7 runner-debt
  items (G) batch alongside it.
- No new evolution-design changes — phase 6 designed evolution; phase 8
  only *connects* phase 6 evolution to phase 7 runner.
- Re-run real-LLM Stage 1 + Stage 2 + Stage 3 after wiring lands; the
  acceptance gate now includes "at least one non-empty `trials[]` in
  the produced `evolution_snapshot.json`."

## Sequencing recommendation

User's own ordering preference (from phase-7 close-out): WR-03/WR-04
callsite/IN-08 first (pure cleanup), then evolution wiring (F), then
WR-01/WR-02/WR-05/IN-01 (touch the new wiring directly).

Group 1 (A-E) inserts cleanly *before* the cleanup items because
Group 1 lifts the runner out of "can't actually re-run real LLM" into
a runnable state. Suggested order:

1. A (timeout 60→180), D (--env-file), E (failure classification) —
   make the runner re-runnable on real LLM.
2. C (CR-05 audit) — gated on a real-LLM batch landing first.
3. WR-03, WR-04 callsite, IN-08 — pure cleanup.
4. F — evolution wiring.
5. B (request-level transient retry) — wraps the new wiring naturally.
6. WR-01, WR-02, WR-05, IN-01 — touch the new wiring directly.

## Acceptance bar

Phase 8 closes when ALL of the following hold:

1. A real-LLM Stage 1 + Stage 2 + Stage 3 batch completes end-to-end
   on a single commit, with no requests dropped due to 60s timeout,
   shell-env staleness, or unhandled transient errors.
2. `evolution_snapshot.json` carries at least one non-empty
   `trials[]` entry (the seeded test delta fired and was recorded).
3. `index.json` carries `failure_class` per row; `batch_summary.json`
   aggregates by class.
4. `pytest -q` passes on the runner-touch sweep (covers WR-01..05,
   IN-01, IN-08, plus new tests for A, B, D, E).
5. `07-WRIN-TRIAGE.md` is updated: all 7 scheduled items move from
   `scheduled (phase 8)` to a phase-8 commit reference.
6. Phase 8's own VERIFICATION.md is `passed`.

## Open questions for the user (when phase 8 starts)

1. What test delta should be seeded at process start? Options: a
   no-op patch on `discover-personalization-factors/SKILL.md` for
   smoke purposes, or a real prompt-level delta from
   `.planning/intel/` so the trial measures something meaningful.
2. Trial cadence — fire one trial per N host requests, or one per
   `assemble_portfolio` policy decision (phase-6 default)?
3. Group 1 timeout default — 180s or higher? (Worst case observed
   ≈110s; 180s gives ~60% headroom. If the user has seen slower
   prompts elsewhere, raise the default.)
4. Group 1 transient retry budget — 2 attempts (3 total)? Or 1 (2
   total) to keep cycle time tight on Stage 3 c=20?

## Status

- 2026-05-27T02:55:00Z — stub created; awaits user kick-off after
  phase 7 closes (real-LLM batch on PID 98270 + case_analysis F1..F4).
- 2026-05-27T03:40:00Z — expanded with Group 1 (phase-7 real-LLM
  hardening) after 2026-05-26 trajectory analysis confirmed three
  root causes (timeout, transient flakes, shell-env drift). User
  approved expansion 2026-05-27 with "开干". Charter now covers
  three groups (A-E hardening, F wiring, G WR/IN debt) on a single
  runner-touch sweep.
