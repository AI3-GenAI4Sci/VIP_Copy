# Phase 09: Acceptance Metrics & Evolution Algorithm Closure - Research

**Researched:** 2026-05-29  
**Domain:** Python validation runner, evolution posterior selection, rubric reward provenance, real-run acceptance evidence  
**Confidence:** HIGH for codebase and artifact findings; MEDIUM for exact acceptance threshold recommendations because CONTEXT delegates those to the planner.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

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

#### Evolution Algorithm

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

#### Acceptance Metric Closure

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

#### Merged Generation Node

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

#### Anti-Cheat Gates

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

### the agent's Discretion

- The planner may choose exact posterior thresholds, minimum sample counts, and
  evidence-sufficiency formulas, but they must be explicit, testable, small,
  and grounded in rubric win/loss evidence.
- The planner may choose the exact shape of the split-node diagnostic/control,
  but it must remain small and diagnostic.
- The planner may choose which 5-8 requests to case-read, but the sample should
  include pressure cases likely to reveal single-angle collapse, tool-skipping,
  weak linkage, or copy-first reasoning.

### Deferred Ideas (OUT OF SCOPE)

No separate `Deferred Ideas` section exists in `09-CONTEXT.md`; use the Phase
Boundary out-of-scope list above as the deferred scope guardrail. [VERIFIED: `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CONTEXT.md`]
</user_constraints>

## Summary

Phase 9 should be planned as a narrow correction of existing Python evolution and validation surfaces, not as a new framework or service. [VERIFIED: `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CONTEXT.md`; VERIFIED: `seers_harness/evolution/delta_portfolio.py`; VERIFIED: `seers_harness/validation/runner.py`] The highest-impact edits are: replace pressure/probability trial gating with explicit exploration decisions, select trial deltas via Thompson sampling over eligible experimental rows, compute reward from baseline-vs-trial rubric mean scores, fold journal posterior state before `batch_summary.json` reads M5, and update tests/anti-cheat checks around the new evidence shape. [VERIFIED: `seers_harness/evolution/delta_portfolio.py`; VERIFIED: `seers_harness/evolution/uplift.py`; VERIFIED: `seers_harness/validation/runner.py`; VERIFIED: `seers_harness/validation/batch_summary_writer.py`]

The latest real Stage 3 evidence root `tests/smoke/.runs/20260528T170042Z/` shows the exact failures Phase 9 must close: Stage 3 had 20 OK rows, one real trial journal entry, `factor_count_p50 = 2.0`, `trial_belief_update_count = 0`, and most snapshots suppressed trials through `token_budget_pressure = 1.0`. [VERIFIED: `tests/smoke/.runs/20260528T170042Z/stage3/batch_summary.json`; VERIFIED: `tests/smoke/.runs/20260528T170042Z/portfolio_journal.jsonl`; VERIFIED: `tests/smoke/.runs/20260528T170042Z/stage3/*/evolution_snapshot.json`] This means M5 is primarily a fold/write-order issue, while trial cadence is a design issue caused by the old pressure-based gate. [VERIFIED: `seers_harness/validation/runner.py`; VERIFIED: `seers_harness/validation/machine_judges.py`]

**Primary recommendation:** Plan three focused implementation waves: evolution decision/reward semantics, M5 summary folding and evidence reporting, then bounded real-run quality assessment and SKILL repair. [VERIFIED: `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CONTEXT.md`]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Exploration decision and Thompson delta selection | Backend / validation runner | Evolution module | Selection is invoked inside `_run_one_request`, but reusable selection math belongs in `seers_harness/evolution/delta_portfolio.py` or a small adjacent module. [VERIFIED: `seers_harness/validation/runner.py`; VERIFIED: `seers_harness/evolution/delta_portfolio.py`] |
| Posterior update and lifecycle transition | Evolution module | Validation runner | `update_after_trial`, `fold_portfolio_journal`, and `apply_status_transitions` already own posterior/status state; runner should call them in the correct order. [VERIFIED: `seers_harness/evolution/delta_portfolio.py`; VERIFIED: `seers_harness/evolution/portfolio_journal.py`; VERIFIED: `seers_harness/evolution/status_machine.py`] |
| Rubric reward extraction | Evolution module or validation helper | Domain schema | Rubric artifacts are typed as `PersonalizedCopyRubricArtifact`; reward should be derived from `judgments[*].total_score` means. [VERIFIED: `seers_harness/domain/models.py`; VERIFIED: `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md`] |
| Batch acceptance summary | Validation writer layer | Evolution module | `write_batch_summary` currently calls `build_behavioral_report(stage_dir)` before the runner folds the journal, so the writer needs folded state access or runner ordering must change. [VERIFIED: `seers_harness/validation/batch_summary_writer.py`; VERIFIED: `seers_harness/validation/runner.py`] |
| Bounded merged-node quality reading | Human validation artifact | Validation evidence files | The quality verdict depends on reading real scenario, generation artifact, tool calls, and rubric artifact for 5-8 sampled requests. [VERIFIED: `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CONTEXT.md`; VERIFIED: `tests/smoke/.runs/20260528T170042Z/stage3/`] |
| Real DeepSeek acceptance run | CLI runner | Provider runtime | Phase 9 acceptance requires a real 30-request concurrency-5 run; FakeProvider tests are preconditions only. [VERIFIED: `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CONTEXT.md`; VERIFIED: `seers_harness/validation/runner.py`] |

## Project Constraints

No `AGENTS.md` exists at the workspace root, so there are no additional root-agent directives to apply. [VERIFIED: shell `test -f AGENTS.md`] No `.codex/skills/` or `.agents/skills/` project skill directory exists in the workspace. [VERIFIED: shell `find .codex/skills .agents/skills -maxdepth 2 -name SKILL.md`] Project authority instead comes from `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, and `09-CONTEXT.md`. [VERIFIED: `.planning/PROJECT.md`; VERIFIED: `.planning/REQUIREMENTS.md`; VERIFIED: `.planning/STATE.md`; VERIFIED: `.planning/ROADMAP.md`; VERIFIED: `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CONTEXT.md`]

Actionable constraints for planning:

- Tool handlers are hand / eye / mirror only; quality judgment belongs in rubric artifacts, not tool handlers. [CITED: `.planning/PROJECT.md`; CITED: `docs/methodology.md`]
- Real provider/data evidence is required for provider behavior or product-quality claims. [CITED: `.planning/PROJECT.md`; CITED: `docs/rubrics.md`]
- SKILL prose must avoid internal examples, hard numeric thresholds, enumeration-style taxonomies, JSON skeletons, and shortcut templates. [CITED: `.planning/PROJECT.md`; CITED: `.planning/REQUIREMENTS.md`; CITED: `09-CONTEXT.md`]
- Clean deletes beat compatibility shims for retired paths. [CITED: `.planning/PROJECT.md`; CITED: `docs/methodology.md`]
- `harness-runtime/` is out of routine development scope. [CITED: `.planning/PROJECT.md`]
- Each phase plan must name the skills or methods it relies on. [CITED: `.planning/PROJECT.md`; CITED: `.planning/REQUIREMENTS.md`]

## Standard Stack

### Core

| Library / Module | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| Python | 3.12.12 in `.venv`; project requires `>=3.11` | Runtime and tests | Current virtualenv is Python 3.12.12 and project metadata allows Python 3.11+. [VERIFIED: shell `.venv/bin/python --version`; VERIFIED: `pyproject.toml`] |
| Pydantic | `>=2.7` | Domain validation for factors, candidates, rubric judgments, portfolio rows | Existing code uses Pydantic v2 models and validators across domain/evolution schemas. [VERIFIED: `pyproject.toml`; VERIFIED: `seers_harness/domain/models.py`; VERIFIED: `seers_harness/evolution/delta_portfolio.py`] |
| pytest | 9.0.3 in `.venv`; project dev dependency `>=8` | Unit/integration test runner | Existing test suite and config use pytest. [VERIFIED: shell `.venv/bin/pytest --version`; VERIFIED: `pyproject.toml`] |
| OpenAI Python SDK | `>=1.40` optional/dev dependency | OpenAI-compatible DeepSeek provider path | Real provider factory imports the OpenAI-compatible provider lazily and reads DeepSeek env vars. [VERIFIED: `pyproject.toml`; VERIFIED: `seers_harness/validation/runner.py`] |

### Supporting

| Library / Module | Version | Purpose | When to Use |
|------------------|---------|---------|-------------|
| `random.Random` / stdlib | Python stdlib | Injected deterministic sampling in selection tests | Keep deterministic selection tests seeded; do not add a bandit dependency. [VERIFIED: `seers_harness/evolution/delta_portfolio.py`; VERIFIED: `tests/test_delta_portfolio.py`] |
| `statistics` / stdlib | Python stdlib | Existing behavioral medians/diversity | Keep machine metrics pure and local. [VERIFIED: `seers_harness/validation/machine_judges.py`] |
| `concurrent.futures.ThreadPoolExecutor` | Python stdlib | Stage 3 concurrency | Existing runner uses this for stage fan-out. [VERIFIED: `seers_harness/validation/runner.py`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing Pydantic + stdlib selection | External bandit/experiment framework | Not recommended; phase scope explicitly forbids broad service graph or overbuilt audit machinery. [CITED: `09-CONTEXT.md`] |
| Existing JSON/JSONL evidence files | Database-backed experiment store | Not recommended; current evidence paths and acceptance artifacts already exist and Phase 9 is closure, not infra redesign. [VERIFIED: `seers_harness/validation/runner.py`; CITED: `09-CONTEXT.md`] |

**Installation:** No new packages are recommended for Phase 9. [VERIFIED: `pyproject.toml`; CITED: `09-CONTEXT.md`]

## Package Legitimacy Audit

No external packages should be installed for this phase. [VERIFIED: `pyproject.toml`; CITED: `09-CONTEXT.md`] `slopcheck` is not installed locally, but this is non-blocking because the recommended stack adds no package. [VERIFIED: shell `command -v slopcheck`]

**Packages removed due to slopcheck [SLOP] verdict:** none. [VERIFIED: no package recommendations]  
**Packages flagged as suspicious [SUS]:** none. [VERIFIED: no package recommendations]

## Architecture Patterns

### System Architecture Diagram

```text
Real/Fake scenario input
  -> validation.runner._run_one_request
      -> WorkflowRuntime current merged DAG
          -> personalized_copy_generation artifact
          -> personalized_copy_rubric artifact
      -> exploration_decision
          -> eligible experimental deltas?
              no -> record allowed no_trial_reason
              yes -> information-value trigger
                  -> no trial: evidence-sufficient / structural blocker reason
                  -> trial: Thompson sample one delta
                      -> baseline full generation + rubric
                      -> patched trial full generation + rubric
                      -> mean rubric score comparison
                      -> append portfolio_journal.jsonl
  -> fold journal into DeltaPortfolioRow posterior
      -> alpha/beta/sample_count/status update
  -> write index.json + batch_summary.json from folded posterior and records
  -> Phase 9 real acceptance: 30 requests, concurrency 5, bounded case reading
```

### Recommended Project Structure

Keep changes in the existing modules unless a small helper materially improves testability. [VERIFIED: existing module layout]

```text
seers_harness/
├── evolution/
│   ├── delta_portfolio.py       # selection/posterior row helpers
│   ├── portfolio_journal.py     # append/read/fold journal
│   ├── status_machine.py        # status transitions
│   └── uplift.py                # replace or narrow to rubric reward comparison
├── validation/
│   ├── runner.py                # orchestration, evidence order, real-run config
│   ├── evolution_snapshot.py    # exploration decision snapshot shape
│   ├── machine_judges.py        # recorded behavioral metrics only
│   └── batch_summary_writer.py  # folded posterior summary
tests/
├── test_delta_portfolio.py
├── test_validation_runner.py
├── test_portfolio_journal.py
├── test_status_machine.py
├── test_uplift.py
└── test_08_07_behavioral_metrics.py
```

### Pattern 1: Explicit Exploration Decision

**What:** Replace `trial_gate` probability events with a durable `exploration_decision` record carrying eligibility, trigger decision, selected delta, and `no_trial_reason` when no trial runs. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/validation/evolution_snapshot.py`]

**When to use:** Every request with or without an actual trial. [CITED: `09-CONTEXT.md`]

**Required shape:** Include enough evidence to prove no token pressure, concurrency pressure, random skip, static probability miss, hardcoded suppression, or artificial prior caused no-trial. [CITED: `09-CONTEXT.md`]

### Pattern 2: Trigger First, Thompson Sample Second

**What:** First decide whether any eligible delta is still informative; only when trialing, sample the delta via Thompson sampling over eligible `experimental` rows. [CITED: `09-CONTEXT.md`]

**Implementation seam:** Refactor `select_trial_delta(...)` so pressure inputs are deleted and the function either accepts an already-triggered eligible set or returns a richer decision object. [VERIFIED: `seers_harness/evolution/delta_portfolio.py`]

**Planner guidance:** Use `rng.betavariate(row.belief_alpha, row.belief_beta)` for Thompson scores and keep `rng` injectable for deterministic tests. [ASSUMED] This is a standard Beta-Bernoulli Thompson sampling formula, but no external docs were fetched because the phase is codebase-only and CONTEXT already locks the algorithm family. [ASSUMED]

### Pattern 3: Rubric-Only Trial Reward

**What:** Compute baseline and trial request means from `PersonalizedCopyRubricArtifact.judgments[*].total_score`; posterior success is `trial_mean > baseline_mean`. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/domain/models.py`; VERIFIED: `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md`]

**Current mismatch:** `compute_uplift(...)` currently uses run success, token-cost tolerance, and derived behavioral metrics; that violates D9 reward provenance and should be replaced or narrowed. [VERIFIED: `seers_harness/evolution/uplift.py`; CITED: `09-CONTEXT.md`]

### Pattern 4: Fold Before Summary Reads M5

**What:** Ensure `portfolio_journal.jsonl` is folded into in-memory portfolio before `batch_summary.json.behavioral_metrics.trial_belief_update_count` is computed. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/validation/runner.py`; VERIFIED: `seers_harness/validation/batch_summary_writer.py`]

**Current mismatch:** `_run_stage` writes index and summary, then folds the journal and applies status transitions; this explains the real-run `trial_belief_update_count = 0` despite one journal entry. [VERIFIED: `seers_harness/validation/runner.py`; VERIFIED: `tests/smoke/.runs/20260528T170042Z/portfolio_journal.jsonl`; VERIFIED: `tests/smoke/.runs/20260528T170042Z/stage3/batch_summary.json`]

### Anti-Patterns to Avoid

- **Pressure laundering:** Do not keep `token_budget_pressure`, `production_pressure`, or `trial_prob` under renamed fields; Phase 9 explicitly forbids them as selection inputs. [CITED: `09-CONTEXT.md`]
- **No-trial as an arm:** Do not put `no_trial` into Thompson sampling; no-trial is a decision outcome with a reason, not a posterior arm. [CITED: `09-CONTEXT.md`]
- **Reward proxy drift:** Do not use behavioral metric lift, token tolerance, run success, LLM self-rating, or agent intuition to decide posterior success. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/evolution/uplift.py`]
- **Old threshold chase:** Do not restore `5/20` trial cadence, `factor_count_p50 >= 3`, cache miss bounds, or token bands as acceptance gates. [CITED: `09-CONTEXT.md`; VERIFIED: `.planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md`]
- **Split-node rollback:** Do not restore split factor/copy nodes as production architecture; only add a small diagnostic if sampled quality is unstable. [CITED: `09-CONTEXT.md`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Posterior counters | New experiment state model | Existing `DeltaPortfolioRow` + `update_after_trial` | The Beta counters and sample counts already exist and are tested. [VERIFIED: `seers_harness/evolution/delta_portfolio.py`; VERIFIED: `tests/test_delta_portfolio.py`] |
| Journal persistence | Database or audit service | Existing JSONL journal append/read/fold | Phase 9 needs ordering and reward semantics, not a new store. [VERIFIED: `seers_harness/evolution/portfolio_journal.py`; CITED: `09-CONTEXT.md`] |
| Status lifecycle service | Scheduler/service graph | Existing `apply_status_transitions` with planner-chosen thresholds | Compact transition helper and Wilson lower bound already exist. [VERIFIED: `seers_harness/evolution/status_machine.py`; VERIFIED: `tests/test_status_machine.py`] |
| Reward judging | LLM self-rating or heuristic uplift | Rubric artifact `total_score` mean comparison | Rubric is the locked quality judgment surface. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/domain/models.py`; VERIFIED: `docs/rubrics.md`] |
| Acceptance quality check | New numeric factor threshold | 5-8 real request case reading | User locked bounded case reading instead of hard factor-count acceptance. [CITED: `09-CONTEXT.md`] |

**Key insight:** The phase is not missing primitives; it has primitives wired with the wrong semantics and ordering. [VERIFIED: codebase inspection]

## Common Pitfalls

### Pitfall 1: Summary Reads Pre-Fold Portfolio

**What goes wrong:** `batch_summary.json` reports `trial_belief_update_count = 0` even when `portfolio_journal.jsonl` contains a trial. [VERIFIED: `tests/smoke/.runs/20260528T170042Z/stage3/batch_summary.json`; VERIFIED: `tests/smoke/.runs/20260528T170042Z/portfolio_journal.jsonl`]  
**Why it happens:** `_run_stage` writes `batch_summary.json` before folding the journal into `delta_portfolio`. [VERIFIED: `seers_harness/validation/runner.py`]  
**How to avoid:** Fold and transition before summary generation, or pass folded state into `build_behavioral_report`. [VERIFIED: `seers_harness/validation/machine_judges.py`; VERIFIED: `seers_harness/validation/batch_summary_writer.py`]  
**Warning signs:** Journal has rows, but summary M5 remains zero. [VERIFIED: real run artifacts]

### Pitfall 2: Token/Concurrency Pressure Survives Under a New Name

**What goes wrong:** Trial cadence stays low and acceptance appears to improve only through renamed pressure logic. [CITED: `09-CONTEXT.md`]  
**Why it happens:** Current `select_trial_delta` computes `trial_prob = (1-rfr)*(1-tbp)*(1-pp)` and the real run shows many `token_budget_pressure = 1.0` entries. [VERIFIED: `seers_harness/evolution/delta_portfolio.py`; VERIFIED: `tests/smoke/.runs/20260528T170042Z/stage3/*/evolution_snapshot.json`]  
**How to avoid:** Delete token and production pressure from the selection signature, tests, snapshot shape, and runner callsite. [CITED: `09-CONTEXT.md`; VERIFIED: `tests/test_delta_portfolio.py`; VERIFIED: `tests/test_validation_runner.py`]  
**Warning signs:** Any test still asserting `trial_prob`, `token_budget_pressure`, or `production_pressure`. [VERIFIED: `tests/test_validation_runner.py`; VERIFIED: `tests/test_delta_portfolio.py`]

### Pitfall 3: Reward Uses the Wrong Evidence

**What goes wrong:** Posterior alpha/beta updates reflect token cost or structural success instead of rubric quality. [CITED: `09-CONTEXT.md`]  
**Why it happens:** `compute_uplift` currently sets positivity from success lift, token cost tolerance, and behavioral metric lift. [VERIFIED: `seers_harness/evolution/uplift.py`; VERIFIED: `tests/test_uplift.py`]  
**How to avoid:** Add a rubric mean-score helper and make journal `success` depend only on `trial_mean_rubric_score > baseline_mean_rubric_score`. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/domain/models.py`]  
**Warning signs:** Tests mention `budget_tolerance`, `behavioral_metric_lift` as a success condition, or success lift as reward. [VERIFIED: `tests/test_uplift.py`]

### Pitfall 4: Fixed Trial Count Reappears

**What goes wrong:** The algorithm gets tuned to satisfy a target count instead of evidence sufficiency. [CITED: `09-CONTEXT.md`]  
**Why it happens:** Phase 8 had a `5/20` gate, and old tests assert skip/fire through a static probability shape. [VERIFIED: `.planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md`; VERIFIED: `tests/test_validation_runner.py`]  
**How to avoid:** Validate decision traces: early insufficient-evidence trials, later posterior-shaped choices/no-trial reasons, and no forbidden reasons. [CITED: `09-CONTEXT.md`]

### Pitfall 5: Merged Node Quality Is Judged by Counts

**What goes wrong:** The planner tries to push median factor count instead of reading whether factors/copy are distinct, grounded, linked, and staged. [CITED: `09-CONTEXT.md`]  
**Why it happens:** Phase 8 surfaced `factor_count_p50 = 2.0`, but Phase 9 reclassifies factor count as a record only. [VERIFIED: `.planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md`; CITED: `09-CONTEXT.md`]  
**How to avoid:** Plan a bounded 5-8 request case-reading task with concrete failure-mode notes and only lightweight SKILL wording repair unless a later phase explicitly plans tool implementation files and tests. [CITED: `09-CONTEXT.md`]

## Code Examples

### Existing Posterior Update

```python
# Source: seers_harness/evolution/delta_portfolio.py
def update_after_trial(row, *, success: bool, token_cost_delta: int = 0):
    new_alpha = row.belief_alpha + (1.0 if success else 0.0)
    new_beta = row.belief_beta + (0.0 if success else 1.0)
    return row.model_copy(update={
        "belief_alpha": new_alpha,
        "belief_beta": new_beta,
        "sample_count": row.sample_count + 1,
        "success_count": row.success_count + (1 if success else 0),
        "failure_count": row.failure_count + (0 if success else 1),
        "token_cost_delta_sum": row.token_cost_delta_sum + int(token_cost_delta),
    })
```

Use this rather than introducing a new posterior type. [VERIFIED: `seers_harness/evolution/delta_portfolio.py`]

### Rubric Mean Reward Helper Shape

```python
# Planner should ask executor to implement near evolution reward/uplift tests.
def mean_rubric_score(artifact: PersonalizedCopyRubricArtifact) -> float:
    scores = [judgment.total_score for judgment in artifact.judgments]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)

def trial_success_from_rubric(*, baseline, trial) -> bool:
    return mean_rubric_score(trial) > mean_rubric_score(baseline)
```

This is an implementation sketch derived from D9-EVO-07/08 and the existing rubric schema. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/domain/models.py`]

### Existing M5 Computation

```python
# Source: seers_harness/validation/machine_judges.py
def compute_belief_update_count(final_portfolio: list[Any]) -> int:
    return sum(
        1
        for row in final_portfolio
        if int(_field(row, "sample_count", 0) or 0) > 0
    )
```

This function is adequate if it receives folded state. [VERIFIED: `seers_harness/validation/machine_judges.py`]

## State of the Art

| Old Approach | Current Phase 9 Approach | When Changed | Impact |
|--------------|--------------------------|--------------|--------|
| Pressure-gated random trial probability | Information-value trigger plus Thompson sampling over eligible experimental deltas | Phase 9 context gathered 2026-05-29 | Planner must delete token/concurrency selection inputs and replace old tests. [CITED: `09-CONTEXT.md`] |
| `5/20` trial cadence | Exploration decision evidence over 30 requests at concurrency 5 | Phase 9 context gathered 2026-05-29 | Acceptance checks decision shape, not fixed count. [CITED: `09-CONTEXT.md`] |
| `factor_count_p50 >= 3` gate | Factor count as record; quality by bounded case reading | Phase 9 context gathered 2026-05-29 | Planner needs a manual evidence artifact/task, not numeric tuning. [CITED: `09-CONTEXT.md`] |
| Cache miss/token bands as gates | Cache/token as observability records only | Phase 9 context gathered 2026-05-29 | Do not block acceptance or exploration on token/cache numbers. [CITED: `09-CONTEXT.md`] |
| Behavioral/token uplift reward | Baseline-vs-trial mean rubric score uplift | Phase 9 context gathered 2026-05-29 | Posterior alpha/beta provenance becomes rubric-only. [CITED: `09-CONTEXT.md`] |

**Deprecated/outdated:**

- `token_budget_pressure` and `production_pressure` in selection are deprecated for Phase 9. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/evolution/delta_portfolio.py`]
- `trial_gate.trial_prob` evidence is deprecated; replace with `exploration_decision` and allowed `no_trial_reason`. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/validation/evolution_snapshot.py`]
- `compute_uplift(... budget_tolerance, behavioral_metrics_*)` as reward source is deprecated; keep token/metric deltas as records only if retained. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/evolution/uplift.py`]

## Current Code Touchpoints

| File | Current Role | Phase 9 Planning Note |
|------|--------------|-----------------------|
| `seers_harness/evolution/delta_portfolio.py` | Portfolio row, posterior mean/update, current pressure-gated selector | Refactor selector signature and semantics; keep row/update helpers. [VERIFIED: code] |
| `seers_harness/evolution/status_machine.py` | Wilson lower-bound helper and status transition | Remove token-cost promotion block if planner interprets D9 as lifecycle based only on rubric wins/losses. [VERIFIED: code; CITED: `09-CONTEXT.md`] |
| `seers_harness/evolution/trial_signal.py` | Failure/token rolling window and concurrency pressure | Token/concurrency helpers must not feed selection; failure-rate may remain observability or blocker only if planner explicitly scopes it as evidence-based. [VERIFIED: code; CITED: `09-CONTEXT.md`] |
| `seers_harness/evolution/portfolio_journal.py` | Append/read/fold trial journal | Keep; ensure folded state reaches summary and status evidence. [VERIFIED: code] |
| `seers_harness/evolution/uplift.py` | Current paired uplift calculator | Replace/narrow with rubric mean comparison; tests must change. [VERIFIED: code] |
| `seers_harness/validation/runner.py` | Real runner, trial workspace execution, journal append, summary order | Main orchestration edit point. [VERIFIED: code] |
| `seers_harness/validation/evolution_snapshot.py` | Snapshot reducer includes `trial_gate` | Replace snapshot evidence shape with exploration decision. [VERIFIED: code; CITED: `09-CONTEXT.md`] |
| `seers_harness/validation/machine_judges.py` | Behavioral metrics including M1-M5 | Reclassify M1/cache/token as records; M5 works if fed folded portfolio. [VERIFIED: code; CITED: `09-CONTEXT.md`] |
| `workflow-skills/current/personalized-copy-generation/SKILL.md` | Merged generation SKILL | Assess with 5-8 real requests; only light repair if failure modes recur. [VERIFIED: file; CITED: `09-CONTEXT.md`] |
| `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md` | Rubric SKILL producing score spread | Reward provenance depends on this artifact. [VERIFIED: file; CITED: `09-CONTEXT.md`] |

## Runtime State Inventory

Phase 9 is not a rename/refactor/migration phase, so runtime state inventory is not required. [VERIFIED: phase description and `09-CONTEXT.md`]

## Real-Run Evidence Inventory

| Evidence | Finding | Planning Impact |
|----------|---------|-----------------|
| `tests/smoke/.runs/20260528T170042Z/stage3/batch_summary.json` | Stage 3 has 20 requests, all `ok`; behavioral metrics include `factor_count_p50 = 2.0`, `copy_candidate_count_p50 = 3.0`, `trial_belief_update_count = 0`. [VERIFIED: file] | Use as regression fixture for summary semantics and case-reading sample. |
| `tests/smoke/.runs/20260528T170042Z/stage3/index.json` | 20 rows; only request `-6834425217442237829` has `trial_selected_delta_id = "delta_product_anchoring_001"`. [VERIFIED: file] | Use to verify old cadence gate is obsolete and new decision evidence is present for every row. |
| `tests/smoke/.runs/20260528T170042Z/portfolio_journal.jsonl` | One raw journal row exists for `delta_product_anchoring_001` with `success=false`, `token_cost_delta=76664`, and behavioral metric lift. [VERIFIED: file] | Confirms M5 raw evidence exists but reward provenance is currently wrong. |
| `tests/smoke/.runs/20260528T170042Z/stage3/*/evolution_snapshot.json` | Snapshots show `trial_gate` with token/production pressure and static `trial_prob`; many token pressures are `1.0`. [VERIFIED: files] | Direct anti-cheat regression target. |
| `tests/smoke/.runs/20260528T170042Z/stage3/-6834425217442237829/trial_workspace/` | Baseline and patched trial workspaces exist with generation and rubric artifacts. [VERIFIED: file tree] | Mechanism evidence exists; reward extraction should use these artifacts. |

## Open Questions (RESOLVED)

1. **Exact evidence-sufficiency threshold — RESOLVED**
   - Final decision: Use small explicit evidence rules in Plan 09-01 and pin them with deterministic tests. A delta remains informative when `sample_count < 5`, or when its posterior mean is near the decision boundary (`abs(belief_mean - 0.50) <= 0.10`), or when its lower-bound confidence is not yet decisive. A delta is evidence-sufficient only when it has at least 5 rubric win/loss samples and is not near the boundary. [CITED: `09-CONTEXT.md`; planned in `09-01-PLAN.md`]
   - Scope guardrail: These thresholds are exploration evidence thresholds only. They are not trial-count targets, factor-count gates, token gates, or production concurrency gates. [CITED: `D9-EVO-01..06`, `D9-MET-03/04/06`]

2. **Status transition token-cost handling — RESOLVED**
   - Final decision: Remove token-cost lifecycle blocking. `apply_status_transitions` should promote/reject/hold from rubric win/loss posterior evidence only: `sample_count`, `success_count`, `failure_count`, and lower-bound thresholds. Token cost may remain visible as observability metadata, but it must not block promotion, decide reward, or affect exploration. [CITED: `D9-EVO-10`, `D9-MET-06`; planned in `09-02-PLAN.md`]
   - Scope guardrail: Token/cost and cache metrics are records only and never Phase 9 acceptance gates. [CITED: `D9-MET-06`]

3. **Where to store final folded portfolio for summary — RESOLVED**
   - Final decision: Use the folded-summary path in Plan 09-03: fold `portfolio_journal.jsonl` into the in-memory portfolio before `write_batch_summary`, then pass folded portfolio state through the summary/report path or write a stage-level folded portfolio artifact if that is the smallest implementation fit. The acceptance requirement is that `batch_summary.json` reads folded posterior state, not raw journal row count. [CITED: `D9-MET-02`, `D9-GATE-02`; planned in `09-03-PLAN.md`]
   - Scope guardrail: `portfolio_journal.jsonl` remains raw event evidence. M5 is accepted only when `sample_count > 0`, alpha/beta update, status/posterior evidence, and `batch_summary.json` visibility all come from folded state. [CITED: `D9-MET-02`]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Unit tests and runner | yes | system 3.13.5; `.venv` 3.12.12 | Use `.venv/bin/python`. [VERIFIED: shell] |
| pytest | Local validation | yes | 9.0.3 in `.venv` | Use targeted tests if full suite is slow. [VERIFIED: shell] |
| DeepSeek API key / balance | Real Phase 9 acceptance run | unknown | env-dependent | No substitute for final acceptance; FakeProvider is precondition only. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/validation/runner.py`] |
| `jq` | Evidence inspection only | yes | not versioned | Python JSON one-liners. [VERIFIED: shell use] |

**Missing dependencies with no fallback:**

- Real DeepSeek credentials and account balance are required for final acceptance, but availability was not probed because secrets should not be printed or inferred from shell state. [CITED: `09-CONTEXT.md`; VERIFIED: `seers_harness/validation/runner.py`]

**Missing dependencies with fallback:**

- `slopcheck` is missing, but no package install is recommended. [VERIFIED: shell]

## Validation Architecture

`workflow.nyquist_validation` is absent from `.planning/config.json`, so validation research is included. [VERIFIED: `.planning/config.json`]

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 in `.venv`. [VERIFIED: shell] |
| Config file | `pyproject.toml` with `testpaths = ["tests"]`. [VERIFIED: `pyproject.toml`] |
| Quick run command | `.venv/bin/python -m pytest tests/test_delta_portfolio.py tests/test_validation_runner.py tests/test_uplift.py -q` |
| Full suite command | `.venv/bin/python -m pytest -q` |

### Phase Requirements -> Test Map

No phase requirement IDs were provided for Phase 9. [VERIFIED: user prompt; VERIFIED: `09-CONTEXT.md`] Use these behavior-level test targets:

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|--------------|
| Selection signature has no token/concurrency pressure and emits explicit exploration decisions | unit + runner integration | `.venv/bin/python -m pytest tests/test_delta_portfolio.py tests/test_validation_runner.py -q` | yes, needs edits. [VERIFIED: files] |
| Thompson sampling favors high posterior samples after trigger | unit | `.venv/bin/python -m pytest tests/test_delta_portfolio.py -q` | yes, needs new tests. [VERIFIED: file] |
| No-trial reasons are allowed and forbidden reasons are absent | unit + snapshot integration | `.venv/bin/python -m pytest tests/test_validation_runner.py -q` | yes, needs edits. [VERIFIED: file] |
| Reward success uses rubric mean score only | unit | `.venv/bin/python -m pytest tests/test_uplift.py -q` | yes, needs rewrite. [VERIFIED: file] |
| Journal fold reaches M5 summary | unit + integration | `.venv/bin/python -m pytest tests/test_portfolio_journal.py tests/test_08_07_behavioral_metrics.py tests/test_validation_runner.py -q` | yes, needs edits. [VERIFIED: files] |
| M1/cache/token are records only, not gates | verification artifact / summary test | `.venv/bin/python -m pytest tests/test_08_07_behavioral_metrics.py -q` | yes, needs acceptance expectation changes. [VERIFIED: file] |
| Real 30-request concurrency-5 run evidence exists | real smoke/manual gate | `.venv/bin/python -u -m seers_harness.validation.runner --env-file .env.local --stage 3 --num-requests 30` plus concurrency config update | runner exists, concurrency config needs planner task. [VERIFIED: `seers_harness/validation/runner.py`; CITED: `09-CONTEXT.md`] |

### Sampling Rate

- **Per task commit:** Run targeted pytest for touched modules. [ASSUMED]
- **Per wave merge:** Run `.venv/bin/python -m pytest -q`. [VERIFIED: project pytest config]
- **Phase gate:** Full pytest green, then real DeepSeek 30-request concurrency-5 run, then bounded 5-8 request case-reading artifact. [CITED: `09-CONTEXT.md`]

### Wave 0 Gaps

- [ ] Add/replace selection tests so token/concurrency pressure no longer appear in function signatures, snapshots, or assertions. [VERIFIED: `tests/test_delta_portfolio.py`; VERIFIED: `tests/test_validation_runner.py`]
- [ ] Add rubric reward helper tests using `PersonalizedCopyRubricArtifact` with different candidate totals and empty-judgment edge cases. [VERIFIED: `seers_harness/domain/models.py`; VERIFIED: `tests/test_uplift.py`]
- [ ] Add summary-order test that writes a journal row and proves `batch_summary.json.behavioral_metrics.trial_belief_update_count > 0`. [VERIFIED: `tests/test_validation_runner.py`; VERIFIED: `tests/test_08_07_behavioral_metrics.py`]
- [ ] Add anti-cheat grep or unit checks for forbidden selection reasons/fields: `token_budget_pressure`, `production_pressure`, `trial_prob`, static probability skip, random skip. [CITED: `09-CONTEXT.md`; VERIFIED: current code contains these names]
- [ ] Add a case-reading artifact template or checklist under the phase directory for the 5-8 request quality read. [CITED: `09-CONTEXT.md`]

## Security Domain

`security_enforcement` is absent from `.planning/config.json`, so security research is included. [VERIFIED: `.planning/config.json`]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | DeepSeek API key read from env or `--env-file`; never bake or print keys. [VERIFIED: `seers_harness/validation/runner.py`] |
| V3 Session Management | no | No browser/user session surface in this phase. [VERIFIED: codebase scope] |
| V4 Access Control | no | No multi-user authorization surface in this phase. [VERIFIED: codebase scope] |
| V5 Input Validation | yes | Pydantic v2 schemas validate factors, candidates, rubric judgments, journal entries, and portfolio rows. [VERIFIED: `seers_harness/domain/models.py`; VERIFIED: `seers_harness/evolution/portfolio_journal.py`; VERIFIED: `seers_harness/evolution/delta_portfolio.py`] |
| V6 Cryptography | yes, limited | Existing SHA-256 hash check protects trial patch drift; do not hand-roll new crypto. [VERIFIED: `seers_harness/evolution/trial_runner.py`] |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leakage in logs/evidence | Information disclosure | Use existing `safe_exc` / safe message redaction and avoid printing env values. [VERIFIED: `seers_harness/validation/runner.py`; VERIFIED: `seers_harness/validation/evolution_snapshot.py`] |
| Path traversal in request ids | Tampering | Keep `_safe_request_dirname` sanitization. [VERIFIED: `seers_harness/validation/runner.py`] |
| Trial patch escapes live skill root | Tampering | Keep temp workspace copy and SHA-256 original text check. [VERIFIED: `seers_harness/evolution/trial_runner.py`] |
| Quality cheating through self-rated fields | Spoofing / tampering | Keep schemas free of self-rated fields and use rubric artifacts for quality. [VERIFIED: `.planning/REQUIREMENTS.md`; VERIFIED: `tests/test_models_no_self_rated_fields.py`; VERIFIED: `seers_harness/domain/models.py`] |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Thompson sampling should use `rng.betavariate(alpha, beta)` over eligible rows. | Architecture Patterns | Low/medium; any equivalent Beta posterior sampler is acceptable, but tests should lock deterministic behavior. |
| A2 | The smallest folded-summary design is to pass final portfolio into `write_batch_summary` or write a stage-level folded portfolio artifact. | Open Questions | Medium; executor may choose another local pattern if cleaner. |
| A3 | Per task commit should run targeted pytest and per wave merge should run full pytest. | Validation Architecture | Low; project practice may choose stricter gates. |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CONTEXT.md` - locked Phase 9 decisions and anti-cheat gates.
- `.planning/PROJECT.md` - workspace constraints and non-negotiable decisions.
- `.planning/REQUIREMENTS.md` - requirement/out-of-scope boundaries.
- `.planning/STATE.md` and `.planning/ROADMAP.md` - project status and Phase 8/9 sequence.
- `.planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md` - latest gaps and real Stage 3 metrics.
- `seers_harness/evolution/*.py` - portfolio, selection, journal, status, reward, trial surfaces.
- `seers_harness/validation/*.py` - runner, snapshot, summary, behavioral metrics.
- `seers_harness/domain/models.py` - rubric/factor/copy schemas.
- `workflow-skills/current/personalized-copy-generation/SKILL.md` and `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md` - merged generation and rubric surfaces.
- `tests/smoke/.runs/20260528T170042Z/` - latest real evidence named by CONTEXT.

### Secondary (MEDIUM confidence)

- `docs/rubrics.md` and `docs/methodology.md` - project-local method/rubric standards.
- Existing tests under `tests/` - current expected behavior and required rewrites.

### Tertiary (LOW confidence)

- None from web search. This was codebase-only research because the phase concerns existing local architecture and locked user decisions.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - based on `pyproject.toml`, local Python/pytest versions, and code imports.
- Architecture: HIGH - based on direct source reads and real evidence artifacts.
- Pitfalls: HIGH - each major pitfall maps to current code and Phase 8 evidence.
- Exact thresholds: MEDIUM - CONTEXT explicitly delegates them to planner discretion.

**Research date:** 2026-05-29  
**Valid until:** 2026-06-05 for active Phase 9 planning, because runner/evolution code is changing quickly.
