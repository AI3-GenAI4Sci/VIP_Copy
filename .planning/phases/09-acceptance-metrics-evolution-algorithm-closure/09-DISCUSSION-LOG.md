# Phase 09: Acceptance Metrics & Evolution Algorithm Closure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `09-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 09-acceptance-metrics-evolution-algorithm-closure
**Areas discussed:** Evolution algorithm hard constraints, Phase 8 acceptance metric closure, Merged generation node assessment, Anti-cheat acceptance gates

---

## Evolution Algorithm Hard Constraints

| Question | Options Considered | Selected |
|---|---|---|
| Token budget pressure | Pressure lowers weight; two-layer eligibility + budget; keep multiplicative gate; freeform | Delete `token_budget_pressure`; token/cache are records only |
| Production/concurrency pressure | Keep as pressure input; delete from algorithm; freeform | Delete `production_pressure`; concurrency is configured, not adaptive |
| No-trial behavior | No no-trial arm; baseline/no-trial as arm; warm-start then baseline arm; information-value trigger | No-trial is not an arm; use `exploration_decision` with evidence-based reasons |
| Delta selection | Thompson sampling; fixed probability; manual priority; freeform | Thompson sampling over eligible experimental deltas |
| Trial reward | Rubric score uplift; heuristic uplift; manual/judge verdict; freeform | Baseline vs trial mean rubric score |
| Candidate aggregation | Request-level mean; best candidate; product-paired score | Request-level mean rubric score |
| Lifecycle update | Evidence lower bound + win-rate threshold; accumulate only; fast reject on consecutive failures | Beta posterior plus evidence lower bound/status thresholds |

**Notes:** User wants exploration to evolve from random-like early behavior into posterior-shaped decisions. Static probability, token pressure, concurrency pressure, and heuristic reward are explicitly rejected.

---

## Phase 8 Acceptance Metric Closure

| Question | Options Considered | Selected |
|---|---|---|
| Treating Phase 8 gaps | Classify per gap; keep all old thresholds; re-sign all metrics | Classify per gap |
| Cache/token | Hard gate; record only; use as trial pressure | Record only |
| Factor count | Delete threshold and use quality evidence; lower threshold; keep p50 >= 3 with anti-padding | Delete hard quantity threshold; add bounded quality/tool case-reading |
| M5 belief update | Folded portfolio; journal only; both | Folded portfolio is source of truth |
| Real run shape | 20/concurrency20; 30/concurrency5; freeform | 30 requests at concurrency 5 |
| Trial triggering metric | Information-value trigger; every eligible request always trials; fixed k/30 | Information-value trigger and explanation, not fixed count |

**Notes:** Cache miss and token consumption are capacity records, not hard acceptance gates. Factor count is recorded, but quality and coverage are judged through bounded samples.

---

## Merged Generation Node Assessment

| Question | Options Considered | Selected |
|---|---|---|
| Judging merged node | Sample chain evidence; structure-only metrics; restore split-node A/B | Sample chain evidence |
| Tool triggering evidence | Staged artifact maintenance; minimum call count; final artifact only | Staged artifact maintenance |
| If quality is unstable | Repair merged node only; rollback condition; small split-node control while repairing | Keep merged primary path and add a small diagnostic split-node control |
| Teaching multiplicity | Abstract red flags + plural contract; tool/schema multi-record feedback; examples; 1 + 2 | Plural contract + multi-record tool-state feedback |
| Matt-style skill guidance | Mimic style; absorb principles only; ignore | Absorb principles only |
| Design weight | Lightweight; more automation; full redesign | Lightweight |

**Notes:** User specifically wants "multiple" to be taught without hard thresholds: clearer plural language, abstract positive/negative patterns, multi-record tool feedback, and no JSON ellipsis/template forcing. Avoid overdesign.

---

## Anti-Cheat Acceptance Gates

| Question | Options Considered | Selected |
|---|---|---|
| Gate set size | Five lightweight gates; add overdesign gate; more strict gates | Five lightweight gates |
| Real evidence | Real evidence required; tests sufficient; manual override | Real DeepSeek run required |
| Mechanism evidence | Mechanism evidence; visibility-only; journal-only | Mechanism evidence |
| Heuristic laundering | Forbid laundering; allow heuristic exceptions; manual judgment | Forbid laundering |
| Reward provenance | Rubric provenance; heuristic uplift; manual feeling | Rubric provenance |
| Case-reading scope | 5-8 bounded samples; broad audit; no case reading | 5-8 bounded samples |

**Notes:** The gate set should block known shortcuts without creating a redundant audit framework.

---

## Agent Discretion

- Choose exact posterior thresholds and minimum sample counts, as long as they are explicit, testable, and based on rubric win/loss evidence.
- Choose exact shape of the small split-node diagnostic/control, as long as it remains diagnostic and lightweight.
- Choose 5-8 real requests for bounded case-reading, biased toward pressure cases that reveal the known failure modes.

## Deferred Ideas

- Long-term split-node restoration.
- Broad online scheduling/limiter/service orchestration.
- More elaborate contextual bandit features beyond the simple Thompson path.
