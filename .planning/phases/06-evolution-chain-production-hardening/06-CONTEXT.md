# Phase 6: Evolution Chain + Production Hardening - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 hardens the workspace harness for production-shaped runs and introduces
a lightweight skill-evolution experiment system.

This phase delivers:

1. A current-schema evolution surface in `workspace/` only.
2. A lightweight delta portfolio that can store, select, trial, and update
   experimental skill deltas.
3. A minimal trial loop that can temporarily apply one delta in an isolated
   git worktree or patch workspace, run a full request trajectory, evaluate the
   result, update belief/confidence, and then restore the main path.
4. A trajectory evidence buffer and sedimentation step that avoids evidence
   explosion and local optima.
5. Harness concurrency-safety verification with realistic-latency fake
   provider runs.
6. Minimal terminal progress for long runs with `--no-progress` / CI-safe
   plain output.
7. Current DeepSeek rate-limit fact recording only.
8. Promotion-chain public entry smoke in the workspace/current-schema line.

`harness-runtime/` is out of scope. It is not edited, migrated, reconciled, or
used as an implementation source in this phase.

</domain>

<decisions>
## Implementation Decisions

### Evolution skill fate
- **D-01:** Old runtime evolution skills are not copied into the workspace live
  surface. They may exist historically, but Phase 6 implementation must be
  re-derived for the current workspace harness.
- **D-02:** Old LLM-driven selection/comparison flows are not preserved as live
  execution logic. Any useful value must be distilled as meta-intent or
  transferable principle, not copied as a judgment process.
- **D-03:** `distill-skill-deltas` is rewritten as a true tool-use skill with
  matching handlers. The model proposes observations and changes; handlers
  enforce structure, evidence references, privacy scans, and final submit.
- **D-04:** Skill prose and user-facing artifacts must not expose internal
  rewrite labels or old internal project nicknames. Avoid the old "candidate"
  vocabulary; use project-appropriate terms such as delta, proposal, change,
  trial, trajectory, portfolio, and belief update.

### Delta evolution system
- **D-05:** Phase 6 implements a lightweight incremental skill evolution system,
  not automatic live overwrite. A skill delta may modify an existing skill or
  add a new skill, but it is first stored as an experimental increment.
- **D-06:** A trial run temporarily applies one selected delta, runs a full
  request trajectory, evaluates quality and token cost, updates confidence and
  failure records, then restores the normal main path.
- **D-07:** Durable adoption of a delta into live skills is not an unsafe first
  step. Any future live adoption requires enough accumulated evidence plus a
  later review/approval/rollback gate.
- **D-08:** Delta selection uses a Bayesian / multi-armed-bandit style
  portfolio. Each delta tracks posterior belief, sample count, success/failure
  history, token-cost effect, applicable skill/task surface, and failure types.
- **D-09:** Trial probability is portfolio-adaptive. Exploration pressure,
  sample scarcity, production pressure, token budget, and recent failure rate
  should adjust whether a request enters a trial.
- **D-10:** Naming is up to the planner, but names should describe the harness
  function directly. Suggested roles: `delta_portfolio`, `trial_scheduler`,
  `trial_selector`, `trial_workspace`, `trajectory_judge`, and `belief_update`.
  Do not use `reference` as the organizing concept.

### Cadence and trajectory evidence
- **D-11:** Normal production requests run the main chain as usual. The system
  does not analyze every trajectory synchronously.
- **D-12:** Every trajectory is eligible to enter a short-term buffer, but not
  every trajectory becomes durable evidence.
- **D-13:** When trajectory analysis needs to generate and settle deltas, the
  main production line pauses to avoid compute-pressure explosion under
  concurrency. After delta sedimentation finishes, the main line resumes.
- **D-14:** Long-term evidence uses a lightweight combined filter: cluster and
  deduplicate repeated patterns, keep only reusable patterns or meaningful
  information gain, preserve diversity across task/skill/failure/success/token
  cases, and avoid local optima from over-weighting recent frequent traces.
- **D-15:** There is no special online priority path for structural failures.
  Schema/tool-contract failures belong in development and tests, not as a
  privileged production evolution trigger.
- **D-16:** The random trial mechanism is harness-native. It is inspired by
  hook/event architecture, but it does not depend on real Claude Code hooks.
  Its trigger point belongs to the SEERS request/scenario boundary.
- **D-17:** Trial isolation uses a temporary git patch or worktree. The applied
  delta must be auditable and discardable after the trial.

### Production hardening
- **D-18:** Concurrency work verifies harness safety only. Use realistic-latency
  `FakeProvider` runs to prove artifact paths, tool-loop state, provider
  messages, and trajectory/evidence records do not cross-contaminate.
- **D-19:** Avoid overdesign. Do not introduce limiter, circuit-breaker,
  manager/service proliferation, or production-grade scheduling machinery in
  Phase 6 unless required by the narrow safety verification.
- **D-20:** Progress UX is minimal terminal progress: completed/total, current
  request or scenario, failure count, and delta trial count. CI and
  `--no-progress` use plain stdout.
- **D-21:** DeepSeek rate-limit work is fact recording only. Record current
  model, base URL, SDK retry behavior, 429 behavior, and visible rate-limit
  headers if any. Do not tune concurrency or build a limiter from this phase.
- **D-22:** Promotion-chain smoke covers public entry points only. The goal is
  import/build/run to a dry-run artifact under the current workspace schema,
  not real promotion or live skill writes.

### Runtime boundary
- **D-23:** Do not touch `harness-runtime/` in Phase 6. It remains a release
  line. Do not edit it, migrate code from it, reconcile its schema, or make it
  part of this phase's implementation path.
- **D-24:** `PROMOTE-01` is interpreted in the workspace/current-schema line.
  If public promotion entry points are needed, implement or smoke them in
  `workspace/` rather than repairing old runtime modules.

### Agent discretion
- **D-25:** The planner may choose exact module names and file placement, but
  must keep the design small. Prefer one or two cohesive modules plus focused
  tests over a broad service graph.
- **D-26:** The planner may choose the posterior-update formula, but it must be
  explicit, testable, lightweight, and based on trial frequency, success/fail
  outcomes, token-cost change, and applicability rather than one-off wins.
- **D-27:** The planner may choose `rich`, `tqdm`, or standard-library progress
  after verifying current APIs/dependencies. The chosen path must preserve
  `--no-progress` and CI-safe plain output.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project authority
- `.planning/PROJECT.md` — workspace is the development line; runtime is not
  touched for routine development; non-negotiable tool-use decisions.
- `.planning/REQUIREMENTS.md` — EVO-01..06, PROD-01..02, TERM-01..02,
  PROMOTE-01, and Phase 6 out-of-scope boundaries.
- `.planning/STATE.md` — Phase 6 watchlist, verified baseline, and current
  project position.
- `.planning/ROADMAP.md` — Phase 6 acceptance criteria and dependency on
  Phase 5.
- `.planning/intel/decisions.md` — locked ADRs, especially tools as
  hand/eye/mirror, one provider path, no self-rated metrics, no compatibility
  baggage, real external spec verification, and skill orchestration.

### Prior phase context
- `.planning/phases/04-skill-md-prose-rewrites/04-CONTEXT.md` — current skill
  prose constraints, dropped examples/enumerations/thresholds, and no internal
  project examples in live skills.
- `.planning/phases/05-cleanup-deletes-tests-regression/05-CONTEXT.md` —
  workspace/runtime boundary, single-threaded smoke baseline, deferred Phase 6
  concurrency/progress/rate-limit/promotion items.

### Current workspace code
- `tests/smoke/test_e2e_smoke.py` — existing 20-request fake-provider smoke
  shape and artifact validation pattern.
- `tests/smoke/scripted_full_chain.py` — reusable scripted full-chain provider
  and node setup for production-shaped fake runs.
- `tests/fakes/scripted_provider.py` — existing fake provider protocol shape
  and message-capture behavior.
- `seers_harness/agentic/tool_loop.py` — current tool-call loop and state
  boundary.
- `seers_harness/workflow/dag_runner.py` — current request/node execution
  integration point.
- `seers_harness/workflow/payloads.py` — scenario payload construction.
- `seers_harness/provider_runtime/openai_compatible.py` — current DeepSeek
  provider parameters and usage/response extraction.
- `seers_harness/core/errors.py` — current provider error classification.
- `seers_harness/domain/models.py` — current artifact and schema contract.
- `seers_harness/tools/skill_tools.py` — current handler/tool registry pattern.
- `workflow-skills/current/discover-personalization-factors/SKILL.md` — live
  skill prose surface.
- `workflow-skills/current/generate-copy-candidates/SKILL.md` — live skill
  prose surface.
- `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md` — live
  skill prose surface.

### External design reference
- `https://github.com/shareAI-lab/learn-claude-code/tree/main` — use only as a
  conceptual reference for hook/event architecture and worktree isolation.
  Do not depend on Claude Code hooks for SEERS production evolution trials.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/smoke/test_e2e_smoke.py` already drives a production-shaped fake run
  through the three-node chain and validates artifacts under strict schemas.
  Phase 6 should extend this pattern rather than invent a separate harness.
- `tests/fakes/scripted_provider.py` captures message snapshots and returns
  scripted tool calls. It is the natural base for realistic-latency fake
  provider tests.
- `seers_harness/provider_runtime/openai_compatible.py` already exposes the
  single `generate_with_tools` provider path and current DeepSeek parameters.
  Rate-limit probes should wrap or observe this surface rather than add a
  second provider path.
- `dag_runner` and `tool_loop` already define the main request/node execution
  boundary. Trial scheduling should attach around this boundary, not inside
  handler logic.

### Established Patterns
- Tool handlers enforce artifact contracts; tools are hand/eye/mirror, not
  domain judges.
- Pydantic models are the artifact contract. Evolution artifacts should use
  explicit typed schemas and avoid self-rated fields.
- The workspace line prefers clean, small modules. Phase 6 must not recreate
  broad runtime service surfaces or old compatibility layers.
- External API behavior must be verified against current facts before code
  relies on it.

### Integration Points
- Trial scheduling belongs at the request/scenario boundary before a full chain
  run starts.
- Trajectory recording belongs after a request run completes, using the full
  input/output/tool-call/token path.
- Delta sedimentation can be a separate command or controlled workflow step
  that pauses the main line while it clusters/deduplicates recent trajectories
  and updates the delta portfolio.
- Progress display can wrap long-run iteration without changing the artifact
  contract.

</code_context>

<specifics>
## Specific Ideas

- "Keep old evolution skills because they may still contain useful meta-intent,
  but only as research input."
- "Do not expose internal rewrite labels or old internal terms in public skill
  prose."
- "The old candidate vocabulary is no longer the right language."
- "Automatic evolution should behave like incremental git-style changes plus
  genetic-algorithm-style mutation/crossover, but first as experimental deltas,
  not unsafe live overwrites."
- "A delta can modify a live skill or add a new skill, but first it is saved as
  an increment and trialed."
- "The system should analyze full skill trajectories: input, output, tool
  calls, task quality, and token cost."
- "The ultimate goal of skill evolution is better task completion with fewer
  tokens."
- "When many deltas exist, the core problem is deciding which delta to trial."
- "Triggering evolution analysis should pause the main production line to avoid
  compute explosion; random trial selection happens inside the main request
  flow."
- "Do not overdesign. Keep the phase lightweight and elegant, avoid module
  explosion."

</specifics>

<deferred>
## Deferred Ideas

- Durable automatic live-skill adoption after enough confidence requires a
  later review/approval/rollback gate.
- Full real-chain debugging of the evolution trial loop belongs with later
  real production-shaped validation.
- Real DeepSeek concurrency tuning belongs after the Phase 6 fact-recording
  probe and likely during Phase 7 real runs.

</deferred>

---

*Phase: 06-evolution-chain-production-hardening*
*Context gathered: 2026-05-26*
