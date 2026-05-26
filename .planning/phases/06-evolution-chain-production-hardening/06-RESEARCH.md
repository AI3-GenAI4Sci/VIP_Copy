# Phase 6: Evolution Chain + Production Hardening - Research

**Date:** 2026-05-26
**Phase:** 06-evolution-chain-production-hardening
**Status:** Research complete

## Research Question

What do we need to know to plan Phase 6 well?

Phase 6 must add a small, current-schema evolution surface and production-shaped
hardening without reviving the old runtime line. The strongest implementation
path is not to port `harness-runtime/seers_harness/evolution/*`. Those files
are useful only as historical intent: deltas should be evidence-backed,
reversible, privacy-scanned, and never promoted automatically. The live
workspace has a much smaller shape: typed artifacts, one provider path,
tool-call handlers, a request-level DAG runner, and a 20-request fake-provider
smoke.

## Current Anchors

### Request boundary

`seers_harness/workflow/dag_runner.py` is the right attachment point for trials.
`WorkflowRuntime.run_request` already runs a complete request/list_group through
the three nodes and returns artifact paths keyed by node id. It keeps node state
fresh per request and writes artifacts under the runtime output directory.

Phase 6 should attach trial scheduling around `run_request`, not inside
`run_skill_via_tools` and not inside individual tool handlers. This preserves
D-16: the trigger point is the SEERS request/scenario boundary.

### Full-chain fake runs

`tests/smoke/scripted_full_chain.py` and
`tests/smoke/test_e2e_smoke.py` already provide the full-chain scripted shape:
factor discovery, copy generation, and rubric judgment each execute two tool
turns. The existing smoke proves 20 unique request ids produce 60 unique
forbid-schema artifacts. This is the base for concurrency and progress tests.

### Provider behavior

`seers_harness/provider_runtime/openai_compatible.py` hard-codes the current
DeepSeek facts that matter to the workspace:

- model default: `deepseek-v4-pro`
- base URL default: `https://api.deepseek.com/beta`
- SDK max retries default: `0`
- timeout default: `60`
- request shape: `reasoning_effort="max"`, `extra_body={"thinking":{"type":"enabled"}}`, `tool_choice="auto"`
- 429 classification: exceptions whose type or text implies rate limiting are
  mapped to `ProviderRateLimitError`

Phase 6 should record these facts and, if the local environment has an API key,
run an optional current-facts probe that captures visible headers or confirms
that headers were unavailable. It must not tune concurrency or add a limiter.

### Tool-use skill pattern

`seers_harness/tools/skill_tools.py` is the established handler registry
pattern: strict tool specs, pure handlers, Pydantic validation, hand/mirror
roles, and no handler-side quality judgment. A rewritten
`distill-skill-deltas` should follow this pattern:

- the model proposes observations and proposed changes;
- handler code validates required evidence refs, blocks private terms, and
  records structured deltas;
- final submit validates the artifact and writes no live skill file;
- no LLM-emitted `confidence`, `score`, or probability-like field is accepted.

Use computed posterior fields in portfolio code instead of self-rated model
fields. Suggested names: `belief_alpha`, `belief_beta`, `belief_mean`,
`sample_count`, `success_count`, `failure_count`, and `token_cost_delta_sum`.

### Historical evolution input

The old runtime evolution skills say the useful part plainly:

- distill feedback into small skill hypotheses, not broad rewrites;
- do not claim online lift;
- do not optimize only for a judge preference;
- do not promote from one sample;
- patches must be narrow, reversible, and evidence-cited.

The obsolete parts are equally important to avoid:

- `compare-champion-bundles` and `select-seed-probes` are old LLM-driven
  judgment flows and should not become live workspace execution logic;
- old `candidate` / `champion` vocabulary does not match Phase 6 language;
- old runtime schemas carry self-rated fields and release-line machinery that
  conflicts with the current workspace schema.

## Recommended Architecture

### Small module set

Keep the implementation to a few cohesive surfaces:

| Surface | Suggested file | Purpose |
|---|---|---|
| Evolution contracts and portfolio | `seers_harness/evolution/delta_portfolio.py` | typed deltas, JSONL persistence, posterior update, adaptive selection |
| Tool-use delta distillation | `seers_harness/tools/evolution_tools.py` plus `workflow-skills/evolution/distill-skill-deltas/SKILL.md` | strict handlers for proposing and submitting experimental deltas |
| Trial and trajectory mechanics | `seers_harness/evolution/trial_runner.py` | optional trial scheduling, temporary patch/worktree isolation, trajectory records, sedimentation |
| Progress display | `seers_harness/workflow/progress.py` | minimal terminal progress with no-progress and CI-safe plain mode |
| Fact/probe docs | `docs/deepseek_rate_limit_facts.md` | current provider/rate-limit facts only |
| Promotion smoke | `seers_harness/evolution/promotion_smoke.py` | dry-run public entry smoke against current schema, no live writes |

If execution finds the module count growing, merge before adding another
surface. The phase goal favors small explicit functions over service objects.

### Delta portfolio

The portfolio should store experimental deltas as data, not as live skill
mutations. Each record needs:

- stable `delta_id`
- `target_skill`
- `change_type`: modify existing skill or add new skill
- observation and proposed change text
- evidence refs
- applicable task/skill surface
- failure types
- sample count, success/failure counts
- token-cost effect accumulator
- posterior update fields such as alpha/beta and computed mean
- status: experimental, held, rejected, or ready_for_review

No durable adoption occurs in Phase 6. `ready_for_review` is only a future gate
marker and must not write to `workflow-skills/current/`.

### Selection and trial probability

A lightweight multi-armed-bandit policy is enough. Use deterministic functions
that accept current portfolio state plus a random source. Inputs:

- sample scarcity
- posterior belief
- recent failure rate
- token budget pressure
- production pressure flag
- task/skill applicability

Output should be either no trial or one selected delta. Do not add a scheduler
service. A function such as `select_trial_delta(portfolio, request_context,
rng)` is sufficient.

### Trial isolation

Trial isolation should support two testable paths:

1. Temporary patch directory for unit tests and local workspace simulation.
2. Git worktree or git patch command path for real workspace trial isolation.

The acceptance condition is that a trial applies at most one delta, runs a full
request trajectory, records the applied delta id and artifact paths, updates the
portfolio, and restores the main path afterward. Tests should prove the live
skill file is unchanged after a trial.

### Trajectory evidence buffer

Every trajectory can be eligible for the buffer, but durable evidence must be
filtered. Keep:

- request id and scenario id
- node artifact paths
- tool call count
- token usage if provider exposes it
- trial delta id if any
- failure category if any
- compact quality outcome supplied by the caller or test harness

Sedimentation should deduplicate repeated signatures, preserve diversity across
task/skill/failure/success/token cases, and emit a bounded evidence JSONL. This
is a batch/control step that pauses main production evolution work; it is not an
online emergency path.

### Progress

No dependency is required. The standard library can print compact progress
lines and works in CI. Use a small abstraction that can be disabled by
`--no-progress` or by CI detection. The visible fields are exactly the Phase 6
contract:

- completed/total
- current request or scenario
- failure count
- delta trial count

Avoid `rich` or `tqdm` unless execution discovers an existing dependency. The
current `pyproject.toml` has only `pydantic`, `openai`, and `pytest`.

### Concurrency test strategy

Use `ThreadPoolExecutor` or `concurrent.futures` in tests only. Give every
request a fresh `WorkflowRuntime`, fresh `ScriptedProvider`, and distinct
output directory. Extend `ScriptedProvider` or wrap it with a delayed provider
that sleeps small realistic latencies per provider call.

Assert:

- 20 concurrent request runs finish;
- artifact paths are unique;
- provider `received_messages` snapshots do not contain another request id;
- runtime records and traces stay per request;
- trajectory/evidence records do not cross-contaminate.

This verifies harness safety. It does not claim DeepSeek production concurrency
capacity.

### Promotion public entry smoke

Do not edit `harness-runtime/`. Implement a workspace current-schema dry-run
surface that can import, build a smoke report, and write a dry-run artifact
under temp output. It should verify that public promotion-chain entry points can
read current `workflow-skills/current/` and evolution portfolio artifacts
without touching live skills.

## Risks And Pitfalls

- Overbuilding a scheduler/manager layer. The request boundary and small pure
  functions are enough for Phase 6.
- Reintroducing self-rated metrics through model-emitted delta fields. Keep
  posterior belief computed from outcomes, not asserted by the model.
- Copying old runtime modules and inheriting incompatible schemas. Historical
  runtime is research input only.
- Treating fake-provider concurrency as real DeepSeek concurrency. Record this
  distinction in tests and docs.
- Letting a failed trial leave a patched skill file behind. Trial cleanup must
  be asserted.
- Making structural schema/tool failures a special online evolution trigger.
  Those belong in tests and development fixes.

## Validation Architecture

Phase 6 needs automated verification at three layers:

1. Unit tests for portfolio update, privacy scan, strict tool handlers,
   sedimentation, progress rendering, and provider fact extraction.
2. Integration tests for trial isolation around `WorkflowRuntime.run_request`.
3. Smoke tests for 20 realistic-latency fake-provider concurrent requests and
   promotion public-entry dry run.

Recommended commands:

- Quick focused tests during execution:
  `uv run --python 3.12 --extra dev python -m pytest tests/test_evolution_*.py tests/test_workflow_progress.py -q`
- Full suite:
  `uv run --python 3.12 --extra dev python -m pytest -q`

Nyquist coverage should require every Phase 6 requirement ID to appear in at
least one plan and one automated or documented verification. Real DeepSeek
rate-limit headers may be environment-dependent; the fact probe should be
optional and documented as fact recording, while static provider defaults and
429 classification must be automated.

## Research Complete

The phase is plannable as five vertical slices:

1. current-schema evolution contracts and tool-use delta distillation;
2. portfolio selection, trial isolation, and evidence sedimentation;
3. request-boundary integration plus concurrency safety;
4. progress UX and DeepSeek rate-limit fact recording;
5. promotion public-entry smoke and final coverage gates.

## RESEARCH COMPLETE
