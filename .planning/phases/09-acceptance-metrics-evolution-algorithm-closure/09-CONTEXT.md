# Phase 09: Acceptance Metrics & Evolution Algorithm Closure - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 9 closes the acceptance gaps left by Phase 8 without laundering them
through hardcoded heuristics, old numeric thresholds, or overbuilt audit
machinery.

This phase delivers:

1. A principled production-chain exploration algorithm based on
   information-value triggering plus Thompson sampling over eligible deltas.
2. A replacement acceptance shape for Phase 8's remaining gaps: M5 as a real
   folded-posterior bug, trial cadence as posterior/evidence behavior, factor
   count as bounded quality case-reading, and cache/token as records only.
3. A lightweight assessment and repair path for the merged
   `personalized_copy_generation` node, including a small split-node diagnostic
   control if needed.
4. A lean anti-cheat gate set that prevents known shortcuts while avoiding
   redundant framework or service design.

Out of scope:

- No restoration of a long-term split-node production architecture.
- No token/cost/concurrency pressure in the exploration algorithm.
- No hard factor-count threshold, static trial probability, random skip, or
  hardcoded trial forcing.
- No broad new service graph, complex scheduler, or large audit framework.

</domain>

<decisions>
## Implementation Decisions

### Evolution Algorithm

- **D9-EVO-01:** Delete `token_budget_pressure` from trial selection. Token use
  and cache miss are capacity/observability records only; they are not
  production exploration inputs and not hard acceptance gates.
- **D9-EVO-02:** Delete `production_pressure` from trial selection. Concurrency
  is a configured run/system setting. Phase 9 validation uses 30 requests at
  concurrency 5, but that value must not enter the selection algorithm.
- **D9-EVO-03:** Do not model `no_trial` as a Thompson arm. Every request must
  pass through an explicit `exploration_decision`; `no_trial` is allowed only
  when the reason is structural or evidence-based.
- **D9-EVO-04:** Trial triggering is information-value based. Eligible deltas
  should be trialed while their posterior evidence is insufficient, near a
  decision boundary, or otherwise still informative. A no-trial decision must
  record `no_trial_reason`; allowed reasons include no eligible delta, all
  eligible deltas evidence-sufficient, all eligible deltas non-experimental,
  target unresolvable, or provider/auth/schema blocker.
- **D9-EVO-05:** Forbidden no-trial explanations: token pressure, concurrency
  pressure, random skip, static probability miss, hardcoded trial suppression,
  or artificial/manual priors.
- **D9-EVO-06:** When a trial is triggered, select the delta via Thompson
  sampling over eligible `experimental` deltas. Early behavior may look random
  because posteriors are uncertain; later choices should become shaped by
  rubric win/loss evidence.
- **D9-EVO-07:** Reward provenance is rubric-only. Baseline/main path and
  patched trial path both run full generation plus rubric. A trial succeeds
  when `trial_mean_rubric_score > baseline_mean_rubric_score`.
- **D9-EVO-08:** Aggregate a trial's candidate-level rubric judgments by
  request-level mean score. Score deltas may be logged for analysis, but the
  minimal posterior reward is binary success/failure from mean-score uplift.
- **D9-EVO-09:** Posterior update uses Beta counters: success increments
  `alpha`, failure increments `beta`, and every trial increments
  `sample_count`.
- **D9-EVO-10:** Delta lifecycle transitions use a transparent evidence lower
  bound plus win-rate/statistical threshold after minimum samples. Exact
  numeric thresholds are planner/test choices, but they must be explicit,
  testable, and based on rubric wins/losses only.

### Acceptance Metric Closure

- **D9-MET-01:** Treat Phase 8 gaps by category, not by trying to push all old
  numbers over old thresholds.
- **D9-MET-02:** M5 is an implementation/folding gap. `portfolio_journal.jsonl`
  is raw event evidence only; acceptance requires journal fold into portfolio,
  `sample_count > 0`, alpha/beta update, and `batch_summary.json` reading the
  folded state.
- **D9-MET-03:** Replace the old trial-cadence threshold (`5/20`) with
  exploration-decision evidence. The 30-request run should show early
  random-like exploration and later posterior-shaped decisions; it should not
  target a fixed trial count.
- **D9-MET-04:** Delete hard `factor_count_p50 >= 3` acceptance. Factor count
  is recorded only. Quality is assessed by bounded case-reading of 5-8 real
  requests.
- **D9-MET-05:** The bounded factor/copy reading checks whether major
  user-product tensions were covered, factors are distinct and product-grounded,
  candidates link to their source factors, and tools/reflection were used when
  coverage, separation, or uncertainty warranted it.
- **D9-MET-06:** Cache miss and token consumption are records only. They must
  not block Phase 9 acceptance and must not influence exploration.
- **D9-MET-07:** Real validation configuration: 30 requests at concurrency 5.
  Local pytest/FakeProvider evidence is a precondition, not a substitute.

### Merged Generation Node

- **D9-MERGE-01:** Keep `personalized_copy_generation` as the primary merged
  path. Do not roll back to a long-term split-node production architecture in
  Phase 9.
- **D9-MERGE-02:** Judge whether the merged node works by sampled chain
  evidence, not by structure alone. Read 5-8 real requests: scenario input,
  generation artifact, generation tool calls, and rubric artifact.
- **D9-MERGE-03:** In each sampled request, verify that factors stand as
  independent user-product insights before copy, and that copy is a linked
  transduction from the `source_factor_id`, not a product-only line or a
  slogan-first backfill.
- **D9-MERGE-04:** Tool triggering is evaluated by staged artifact maintenance,
  not raw call count. Factor state should be built/validated before copy state;
  copy candidates should point to existing factor state; uncertainty or
  coverage/separation gaps should trigger reflection or repair when appropriate.
- **D9-MERGE-05:** Add a small split-node diagnostic/control experiment if
  quality is unstable, to identify whether issues come from merge architecture
  or the current merged SKILL/tool workflow. This is diagnostic only, not a
  restored dual-path architecture.
- **D9-MERGE-06:** Repair should stay lightweight: improve SKILL wording and
  existing tool feedback before adding mechanisms.
- **D9-MERGE-07:** Use a plural contract plus multi-record tool-state feedback
  to teach "multiple distinct results." Clarify distinct user-product
  tensions/opportunities, single-angle collapse, duplicate factors, and
  copy-before-factor red flags.
- **D9-MERGE-08:** Do not use hard numeric factor thresholds, internal examples,
  JSON skeletons, or ellipsis templates to force multiplicity. Avoid returning
  to old enumeration/taxonomy-driven prompting.
- **D9-MERGE-09:** Borrow only the useful principles from Matt-style skill
  writing: test documentation against actual model failure modes, write red
  flags/rationalizations, keep descriptions from becoming shortcuts, and verify
  with pressure samples. Do not mimic that format wholesale.

### Anti-Cheat Gates

- **D9-GATE-01 Real Evidence:** Phase 9 acceptance requires a real DeepSeek
  30-request concurrency-5 validation run. Pytest and FakeProvider runs are
  necessary preconditions only.
- **D9-GATE-02 Mechanism Evidence:** Portfolio visibility is not trial evidence.
  A valid trial path needs `exploration_decision`, selected delta when trialing,
  trial workspace, journal event, folded posterior, and status/posterior
  evidence.
- **D9-GATE-03 No Heuristic Laundering:** No token/concurrency pressure, static
  probability, random skip, hardcoded trial forcing, or artificial prior may be
  used to satisfy acceptance.
- **D9-GATE-04 Reward Provenance:** Success/failure comes from baseline vs trial
  mean rubric score. No LLM self-rating, hand-written uplift heuristic, or agent
  intuition decides reward.
- **D9-GATE-05 Bounded Case Reading:** Read 5-8 real sampled requests for
  factor/copy/merged-node quality and tool use. Record concrete failure modes;
  do not create new hard quantity thresholds.

### Agent Discretion

- The planner may choose exact posterior thresholds, minimum sample counts, and
  evidence-sufficiency formulas, but they must be explicit, testable, small,
  and grounded in rubric win/loss evidence.
- The planner may choose the exact shape of the split-node diagnostic/control,
  but it must remain small and diagnostic.
- The planner may choose which 5-8 requests to case-read, but the sample should
  include pressure cases likely to reveal single-angle collapse, tool-skipping,
  weak linkage, or copy-first reasoning.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Authority

- `.planning/PROJECT.md` — workspace boundary and non-negotiable tool-use
  decisions.
- `.planning/REQUIREMENTS.md` — requirements and out-of-scope boundaries,
  including no self-rated metrics and no old compatibility paths.
- `.planning/ROADMAP.md` — Phase 9 registration and dependency on Phase 8.
- `.planning/STATE.md` — current status and watchlist.

### Prior Phase Decisions

- `.planning/phases/06-evolution-chain-production-hardening/06-CONTEXT.md` —
  original evolution system design, especially D-08, D-09, and D-26.
- `.planning/phases/07-real-llm-validation/07-CONTEXT.md` — real-LLM evidence
  standards and VAL-06 trial/reflow expectations.
- `.planning/phases/08-evolution-wiring-and-runner-debt/08-CONTEXT.md` —
  Phase 8 runner/evolution wiring decisions and real-evidence constraints.
- `.planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md` —
  latest `gaps_found` evidence and remaining metric failures.

### Current Code Touchpoints

- `seers_harness/evolution/delta_portfolio.py` — current selection, posterior
  update, portfolio models, and assembly.
- `seers_harness/evolution/status_machine.py` — current status transitions and
  Wilson lower-bound helper.
- `seers_harness/evolution/trial_signal.py` — current token/concurrency/failure
  pressure helpers; token/concurrency pressure should be removed from selection.
- `seers_harness/evolution/portfolio_journal.py` — journal append/read/fold
  path that must drive M5 folded posterior evidence.
- `seers_harness/validation/runner.py` — Stage runner, exploration hook,
  trial workspace execution, journal fold ordering, and real validation config.
- `seers_harness/validation/machine_judges.py` — behavioral metrics and current
  M1/M5 summary calculations.
- `seers_harness/validation/batch_summary_writer.py` — summary writer that must
  report folded portfolio evidence.

### Skill Surfaces

- `workflow-skills/current/personalized-copy-generation/SKILL.md` — merged
  generation SKILL to assess and lightly repair.
- `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md` — rubric
  output used for trial reward provenance.

### Real Run Evidence

- `tests/smoke/.runs/20260528T170042Z/stage3/batch_summary.json` — latest
  Stage 3 behavioral metrics: M1 failed, M5 failed, cache/token recorded high.
- `tests/smoke/.runs/20260528T170042Z/stage3/index.json` — latest 20 OK rows
  and request navigation.
- `tests/smoke/.runs/20260528T170042Z/portfolio_journal.jsonl` — raw trial
  journal entry that did not yet fold into summary M5.

### Skill-Writing References Used During Discussion

- `/Users/macbook/.codex/skills/write-a-skill/SKILL.md` — lightweight local
  skill structure guidance; use for principles only, not format mimicry.
- `/Users/macbook/.codex/superpowers/skills/writing-skills/SKILL.md` —
  Matt-style pressure-test/red-flag ideas for documentation; absorb principles
  only, do not copy wholesale.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `DeltaPortfolioRow`, `belief_mean`, and `update_after_trial` already provide
  Beta-style posterior bookkeeping; Phase 9 should adapt them rather than
  introduce a separate model.
- `apply_status_transitions` already provides a compact status-transition
  surface using lower bounds and sample counts; Phase 9 should refine its
  inputs/thresholds, not build a new lifecycle service.
- `run_request_trial` and baseline/trial workspaces already provide the
  mechanism needed for rubric-linked rewards.
- `personalized-copy-rubric-judge` already emits candidate-level scores that
  can be aggregated into request-level mean reward.

### Established Patterns

- Tool handlers and schemas enforce contracts; tools are hand/eye/mirror, not
  model self-judges.
- Real provider/data evidence is required for provider behavior and production
  quality claims.
- Prefer small module edits and focused tests over service proliferation.
- Keep SKILL prose free of internal examples, hard numeric thresholds, and
  enumeration-style taxonomies.

### Integration Points

- Trial selection currently sits in `runner.py` after the main request path.
  That remains the right integration point for information-value decision plus
  Thompson selection.
- M5 summary currently depends on the timing and visibility of journal folding;
  the fold must happen before summary metrics need folded posterior evidence or
  the summary builder must read the folded state explicitly.
- Merged-generation assessment should use evidence already written under each
  request's `evidence/personalized_copy_generation/` and
  `evidence/personalized_copy_rubric/` directories.

</code_context>

<specifics>
## Specific Ideas

- The validation run shape is fixed for Phase 9 discussion output:
  30 requests at concurrency 5.
- Exploration should look random early only because posteriors are uncertain;
  it should become more intelligent as rubric wins/losses accumulate.
- Trial count in a 30-request run is not a fixed target. It should be explained
  by eligible deltas, posterior information value, and structured
  `no_trial_reason` values.
- Bounded case-reading should deliberately look for:
  - single-angle factor collapse;
  - slogan-first/copy-before-factor reasoning;
  - role/label renamed as factor;
  - duplicate factors with different wording but same predicted user response;
  - tool/state skipping where factor/copy uncertainty was visible.

</specifics>

<deferred>
## Deferred Ideas

- Long-term split-node restoration is deferred unless a later phase decides the
  merged architecture is structurally unsalvageable.
- Product-grade online scheduling, limiters, service orchestration, or broad
  audit dashboards are deferred. Phase 9 should stay lightweight.
- More elaborate contextual bandit features beyond surface/applicability and
  rubric posterior evidence are deferred until the simple Thompson path is
  proven on real runs.

</deferred>

---

*Phase: 09-Acceptance Metrics & Evolution Algorithm Closure*
*Context gathered: 2026-05-29*
