# Phase 5 Discussion Log

**Date:** 2026-05-26
**Mode:** default

## Domain Boundary Presented

Phase 5 = remove c14/c15/c16 carryover, tighten Pydantic schemas, stand up end-to-end smoke link `data_100k.csv → intake → tool_loop → DAG → stable artifact`, verify CLEAN-03, keep 122-test baseline green. `harness-runtime/` out of scope.

## Gray Areas Presented

| Code | Area | Resolution |
|---|---|---|
| A | Runtime-skills reconciliation strategy (workspace → harness-runtime promotion) | **Cancelled by user.** New architecture: workspace = development line, runtime = release line, no promotion in Phase 5. |
| B | `intake/` module disposition | **Load-bearing.** Wire into smoke link. |
| C | Legacy-tolerance posture on `models.py` | **`extra="forbid"`.** Reconstruct against new harness; older artifacts not expected to round-trip. |
| D | c16 inline-comment scrub vs preserve | **Scrub everything**, including internal-meme tokens across all workspace code/tests/docs. |
| E | Regression sweep scope (REGRESS-01) | **Negative sweep on workspace only.** Runtime modules out of new-architecture scope. |
| F | CLEAN-03 hard-check gate survival | **Accept hypothesis.** Single grep pass during research to confirm. |

## Discussion Threads

### Thread 1 — Phase 5 vs Phase 6 boundary (raised from user reply on B)

**Problem:** User said "high-concurrency, info, full chain CSV → stable output." But ROADMAP places concurrency (PROD-01), terminal progress (TERM-01/TERM-02) in Phase 6.

**Options presented:**
- B1: Phase 5 = single-threaded smoke + cleanup; Phase 6 keeps concurrency + progress.
- B2: Phase 5 absorbs concurrency + info; Phase 6 reshaped.
- B3: Split Phase 5 into 5a (cleanup + smoke) and 5b (concurrency + info).

**User selected:** B1.

### Thread 2 — Batch size (raised from "≤ 50 requests" in user reply)

**Problem:** ADR-RUNTIME-BATCH locks real-LLM batch = 20. User initially said "≤ 50 requests."

**Options presented:**
- B-data-1: FakeProvider 50 for smoke, real-LLM stays 20.
- B-data-2: Change ADR-RUNTIME-BATCH to 50 across the board.
- B-data-3: 50 is smoke ceiling regardless of provider.

**User correction:** "I misspoke — it's 20." Decision: 20 for all batches (smoke + real-LLM).

### Thread 3 — Explanation of `extra="forbid"` (requested by user)

**User question:** "I don't understand what `extra="forbid"` does."

**Explained:**
- `extra="ignore"`: unknown fields silently dropped — `confidence=0.8` from a drift-y LLM would disappear without trace.
- `extra="allow"`: unknown fields silently retained.
- `extra="forbid"`: unknown fields → `ValidationError`.

**Rationale offered:** `extra="ignore"` *is* the c14/c15 baggage Principle 8 forbids; it also silently swallows the self-rated metric fields Principle 10 forbids. The flip is the structural enforcement, not a reviewer's eye.

**User reply:** "Got it — since SKILLs were rewritten, the output JSON field shapes are also re-arranged; older artifacts won't necessarily round-trip into the new version."

**Decision locked:** `extra="forbid"` on every BaseModel in `workspace/seers_harness/domain/models.py` (D-07).

## Deferred (recorded in CONTEXT.md)

- PROD-01 concurrency at batch 20 → Phase 6
- TERM-01, TERM-02 terminal progress / `--no-progress` → Phase 6
- Structured INFO/DEBUG logging routing → Phase 6
- PROD-02 real DeepSeek rate-limit verification → Phase 6
- PROMOTE-01 promotion-chain smoke → Phase 6
- VAL-01..06 real-LLM validation → Phase 7
- Reference v2 emitter implementation → post-Phase-7
- Runtime promotion of new SKILL files / schema → separate reviewed step
- `harness-runtime/` storage/assets/evaluation/gates/CLI positive sweep → out of new-architecture scope unless explicitly reopened
- EVO-01..06 evolution chain rewrites → Phase 6

## Claude's Discretion (recorded in CONTEXT.md)

- Choice of grep tooling, deletion order, commit slicing for cleanup pass.
- Whether scrub passes use per-file `Edit` or a single bulk pass.
- Where the smoke-link entry point lives.
- Whether to use a pytest marker or a separate runner.
- Whether `extra="forbid"` flip is one commit or per-model commits, depending on test regression pattern.

---

*Phase: 05-cleanup-deletes-tests-regression*
*Discussion gathered: 2026-05-26*
