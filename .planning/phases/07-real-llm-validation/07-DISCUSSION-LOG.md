# Phase 7: Real-LLM Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 07-real-llm-validation
**Areas discussed:** run mechanics; evidence capture; acceptance shape; evolution wiring; VAL-05 case-reading protocol; cost guardrails

---

## Domain 1 — Run mechanics: concurrency & retry

### 1.1 Concurrency posture

| Option | Description | Selected |
|--------|-------------|----------|
| A | Fully serial (concurrency=1) — safest, evidence ready quickly, no real-concurrency proof | |
| B | Real concurrency 20 in one shot — matches Phase 6 fake-side verification | |
| C | Staged: bring-up → small concurrency → optionally 20; separate "completion" from "stress" | ✓ |
| D | Other | |

**User's choice:** C — staged execution.
**Notes:** User wants "跑通" and "压测" decoupled with independent evidence per stage.

### 1.2 Stage-3 boundary

| Option | Description | Selected |
|--------|-------------|----------|
| A | Stages 1+2+3 all in Phase 7 | ✓ |
| B | Stages 1+2 only; concurrency stress to a follow-up phase | |
| C | Stages 1+2 + a light concurrency sample (c=4, N=8); full c=20 deferred | |
| D | Other | |

**User's choice:** A — all three stages in Phase 7.
**Notes:** Full bring-up → main evidence → real concurrency loop closed in one phase.

### 1.3 Failure handling within a stage

| Option | Description | Selected |
|--------|-------------|----------|
| A | Fail-fast — any single failure stops the stage immediately | ✓ |
| B | Continue-on-error — run all 20, classify failures, report distribution | |
| C | Stage-specific (1 fail-fast; 2/3 continue-on-error) | |
| D | Other | |

**User's choice:** A — fail-fast across all stages.
**Notes:** Acceptance is anchored to 20/20 clean — naturally tightens the definition of failure.

### 1.4 Per-request retry budget

| Option | Description | Selected |
|--------|-------------|----------|
| A | Zero retries; any transient surfaces as request failure | |
| B | SDK built-in retries only (`max_retries=N`) — no extra wrapper | ✓ (N=3) |
| C | Per-layer split: 0 at node, 1 transient retry inside tool-loop | |
| D | Other | |

**User's choice:** B with N=3.
**Notes:** Acknowledged tradeoff — masks real concurrency-induced rate ceilings, recorded as a known property of Stage 3.

---

## Domain 2 — Evidence capture

### 2.1 Per-request evidence depth

| Option | Description | Selected |
|--------|-------------|----------|
| A | Final artifact JSON only | |
| B | Artifact + full message trajectory + tool-call sequence + token usage | |
| C | B + evolution-system state snapshot (trial selection, reflow events, portfolio before/after) | ✓ |
| D | Other | |

**User's choice:** C — full evidence including evolution snapshot.
**Notes:** VAL-06 must have structured evidence, not log-grep.

### 2.2 Storage location & version boundary

| Option | Description | Selected |
|--------|-------------|----------|
| A | Git-ignored `tests/smoke/.runs/<timestamp>/`; nothing committed | ✓ |
| B | A + a "canonical run" copied into `.planning/phases/07-real-llm-validation/runs/canonical/` | |
| C | A + a summary-only canonical (metrics CSV/JSON + failure dumps) | |
| D | Other | |

**User's choice:** A.
**Notes:** Acknowledged consequence — deep trajectories live only locally; later full-trajectory audit would require re-running.

### 2.3 File layout

| Option | Description | Selected |
|--------|-------------|----------|
| A | One directory per request, one file per concern (machine-friendly tree) | ✓ |
| B | One file per request (merged JSON) | |
| C | One JSONL dump per batch + Markdown index | |
| D | Other | |

**User's choice:** A.
**Notes:** Machine-readable navigation prioritized. Top-level `index.json` and `batch_summary.json` mandatory and machine-first (not Markdown).

---

## Domain 3 — Acceptance definition

### 3.1 VAL-03 acceptance granularity

| Option | Description | Selected |
|--------|-------------|----------|
| A | ≥1 reflection call across batch | |
| B | ≥N% of requests touch reflection | (basis for E below) |
| C | Every scenario must touch reflection (conflicts with reflection-as-mirror design) | |
| D | Don't gate on VAL-03; record observation only | |
| E | Statistics + case analysis: machine count is navigation, user-confirmed reading is the verdict | ✓ |

**User's choice:** E — case analysis over pass-rate threshold.
**Notes:** User explicitly: "比起指标通过率, 我更看重真实case分析." Generalised to VAL-03 / VAL-05 / VAL-06.

### 3.2 Case-analysis scaffolding

| Option | Description | Selected |
|--------|-------------|----------|
| A | Auto-generate `case_analysis.md` skeleton (with sample paths, blank judgment slots) | |
| B | No skeleton — just read `.runs/` directly | ✓ |
| C | LLM produces a draft for human review | |
| D | Other | |

**User's choice:** B.
**Notes:** Direct reading; no auto-scaffolding.

### 3.3 Case-analysis archival policy

**User's response:** "可以作为审计证据, 但必须是与我沟通确认的可信结论才能进证据."

**Decisions captured:**
1. `case_analysis.md` is the sole in-tree audit artifact (raw `.runs/` per D-09 is local-only).
2. Only **user-confirmed conclusions** enter the file.
3. Agent observations stay as "待你确认的观察" in working notes; do not enter the file unilaterally.

---

## Domain 4 — Evolution wiring (VAL-06)

### 4.1 Evolution system on/off in Phase 7

| Option | Description | Selected |
|--------|-------------|----------|
| A | Fully ON — trial scheduler runs, trials apply deltas, reflow fires by cadence | ✓ |
| B | Reflow event hook ON, trial execution OFF — observe cadence only, no extra trial cost | |
| C | All OFF; replay deltas offline against captured trajectories | |
| D | Other | |

**User's choice:** A — full evolution on under real LLM.

### 4.2 Seeding the portfolio

| Option | Description | Selected |
|--------|-------------|----------|
| A | Pre-seed portfolio with N≈3-5 deltas before Stage 1 | |
| B | Portfolio empty, observe cadence + scheduler-on-empty behavior | |
| C | Portfolio empty; deltas grow in-flight from trajectory buffer via `distill-skill-deltas` | ✓ |
| D | Other | |

**User's choice:** C.
**Notes:** Stage 1 / early Stage 2 will almost certainly produce zero trials — expected, recorded in plan.

### 4.3 Trial failure routing

| Option | Description | Selected |
|--------|-------------|----------|
| A | Trial failure recorded only; never stops batch | |
| B | Trial failure ⇒ host request fails ⇒ batch stops | |
| C | Split by class: schema/protocol stops batch; transient/rate-limit recorded only | ✓ |
| D | Other | |

**User's choice:** C — split by error class.
**Notes:** A delta breaking the schema is a real finding, not noise.

### 4.4 Trial trigger rate

| Option | Description | Selected |
|--------|-------------|----------|
| A | Phase 6 portfolio-adaptive cadence runs unmodified | ✓ |
| B | Override Phase-6 cadence with a fixed forced-trial frequency | |
| C | Adaptive normally + force one trial if zero across 20 | |
| D | Other | |

**User's choice:** A — adaptive logic untouched.
**Notes:** Zero observed trials in 20 requests is a legitimate observation, not failure.

### 4.5 Trial isolation mechanism

User's first-pass response: "B (`shutil.copytree`), 但内网部署 A (worktree) 我认为最好."

This was contradictory; resolved by inspecting Phase 6's actual implementation: `evolution/trial_runner.apply_delta_patch_temporarily` already uses `shutil.copytree` + SHA-256 lock + finally-restore — meeting the audit / isolation needs Phase 7 has.

**Final decision:** Reuse Phase 6 implementation as-is for Phase 7. Worktree upgrade deferred to pre-deployment ADR review.

---

## Domain 5 — VAL-05 case-reading protocol

### 5.1 Fixed "fake-transferable" failure shapes

| Option | Description | Selected |
|--------|-------------|----------|
| A | All four (F1 generic-wrap, F2 broken causality, F3 boilerplate, F4 covers/disposition mismatch) | ✓ |
| B | F1 + F2 only | |
| C | No predefined shapes — read by intuition | |
| D | Other | |

**User's choice:** A — fix all four as standing checks.

### 5.2 Sampling strategy

| Option | Description | Selected |
|--------|-------------|----------|
| A | Read all factors of all requests | |
| B | Stratified: ≥1 per request + extreme samples | ✓ |
| C | All-but-machine-ranked-by-suspicion | |
| D | Other | |

**User's choice:** B — stratified sampling, ~20-30 factors total.

### 5.3 Extreme-sample dimensions

User answered "先 E1~4 即可":
- E1: longest `covers_product_ids`
- E2: shortest `transferable_disposition` text
- E3: longest `transferable_disposition` text
- E4: highest literal overlap between `user_side_signal` and `transferable_disposition`

E5(a) fuzzy near-miss + E5(b) cross-request similarity clusters: deferred.

---

## Domain 6 — Cost & budget guardrails

### 6.1 Pre-flight gating

| Option | Description | Selected |
|--------|-------------|----------|
| A | Stage 1 (N=1) is the sole gating step; no extra | ✓ |
| B | Add a Stage 1.5 (N=3, c=1) distribution sample | |
| C | Token-cost estimation between stages, ask user to confirm continuation | |
| D | Other | |

**User's choice:** A.

### 6.2 Per-request token cap

| Option | Description | Selected |
|--------|-------------|----------|
| A | None — trust `tool_loop` max-iter guard | ✓ |
| B | Hard cap (e.g., 50K input + output) | |
| C | Soft warning + hard cap | |
| D | Other | |

**User's choice:** A — no extra token cap.

### 6.3 Inter-stage human checkpoint

| Option | Description | Selected |
|--------|-------------|----------|
| A | Fully automatic — Stage 1 → 2 → 3 in one shot | ✓ |
| B | Manual checkpoint between every stage | |
| C | Stage 1 → 2 auto; Stage 2 → 3 manual | |
| D | Other | |

**User's choice:** A.
**Notes:** Case analysis happens after the full run, not between stages.

---

## Claude's Discretion (per CONTEXT.md D-22)

The planner chooses:
- Stage 3 stepping policy (one-shot c=20 vs intermediate 4 / 8 samples).
- Filenames inside per-request directories (provided `index.json` + `batch_summary.json` machine-readable contracts hold).
- Whether evolution observability hooks (D-11) live inside `evolution/` modules or in a thin wrapper layer.
- Whether `batch_summary.json` is built per request on-the-fly or post-batch from per-request files.
- Runner entry-point location (extension to existing smoke test, new module, or `intake/__main__.py` CLI).

---

## Deferred Ideas

1. Real-DeepSeek concurrency tuning / rate-limit absorption (separate follow-up phase).
2. Trial isolation upgrade to git worktree with diff history (pre-deployment ADR review).
3. Hand/eye/mirror taxonomy consolidation (ADR-01-PRINCIPLE-01 review candidate; user-flagged).
4. Fuzzy-match / cross-request cluster sampling for VAL-05 (E5(a)/(b) from sampling discussion).
5. In-tree canonical run archival (revisit if Phase 7 case-reading needs it).
6. Reference v2 emitter (post-Phase 7).
7. Long-running production evolution-loop tuning (cadence, sedimentation, adoption gates).
