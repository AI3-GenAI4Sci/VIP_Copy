---
phase: 07-real-llm-validation
plan: 07-05
subsystem: testing
tags: [audit, case-analysis, val-03, val-05, val-06, manual-review]

# Dependency graph
requires:
  - phase: 07-real-llm-validation
    provides: D-13/D-14/D-15/D-16 source-of-truth (07-CONTEXT.md)
provides:
  - In-tree audit artifact `case_analysis.md` for VAL-03/VAL-05/VAL-06 verdicts
  - Fixed F1..F4 sub-headings under VAL-05 quoted verbatim from D-15
  - Reading-scope note anchored to D-16 (~20-30 factors per batch)
affects: [07-01, 07-02, 07-03, 07-04, 07-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Audit artifact admits only user-confirmed conclusions (D-14)"
    - "VAL-05 failure-mode taxonomy with fixed F1..F4 verbatim labels (D-15)"

key-files:
  created:
    - .planning/phases/07-real-llm-validation/case_analysis.md
  modified: []

key-decisions:
  - "Honor D-13 — case_analysis.md is the sole in-tree audit artifact for VAL-03/VAL-05/VAL-06"
  - "Honor D-14 — only user-confirmed conclusions admitted; bodies are empty placeholders"
  - "Honor D-15 — F1..F4 sub-headings use the exact CONTEXT.md descriptions; no shortened labels"
  - "Honor D-16 — reading scope ≈20-30 factors per batch noted explicitly"

patterns-established:
  - "User-confirmation gate: agent observations stay in working notes; only confirmed verdicts enter case_analysis.md"

requirements-completed: [VAL-03, VAL-05, VAL-06]

# Metrics
duration: 5min
completed: 2026-05-26
---

# Phase 07 Plan 07-05: Case Analysis Template Summary

**Seeded `case_analysis.md` audit skeleton with D-14 admittance rule, three VAL sections, four verbatim D-15 F1..F4 sub-headings, and D-16 reading-scope note — ready for user-driven manual case analysis post-batch.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-26
- **Completed:** 2026-05-26
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments

- Created the in-tree audit artifact `.planning/phases/07-real-llm-validation/case_analysis.md` (D-13).
- Embedded the D-14 user-confirmed-only admittance rule in the file header.
- Locked the four VAL-05 failure-mode sub-headings (F1..F4) using the verbatim D-15 wording from `07-CONTEXT.md`.
- Added the D-16 reading-scope note (≈20-30 factors per batch) as the closing section.
- Verified absence of invented short labels (Misroute / Hallucinated Coverage / Reflow Trigger / Trial-Selection Anomaly).

## Task Commits

1. **Task 1: Write the case_analysis.md skeleton** — `0056ad6` (docs)

**Plan metadata:** committed in step 7 below.

## Files Created/Modified

- `.planning/phases/07-real-llm-validation/case_analysis.md` — Audit-template markdown with H1, D-14 header note, VAL-03 / VAL-05 (with F1..F4) / VAL-06 sections (italic placeholder bodies), and the D-16 Reading Scope Note.

## Decisions Made

- **Honor D-13:** `case_analysis.md` lives at `.planning/phases/07-real-llm-validation/case_analysis.md` as the single in-tree audit artifact for VAL-03 / VAL-05 / VAL-06.
- **Honor D-14:** Bodies are empty italic placeholders; no inferred or auto-generated conclusions. Header explicitly states "Only user-confirmed conclusions are admitted here (D-14)".
- **Honor D-15:** F1..F4 sub-headings use the exact CONTEXT.md descriptions verbatim — F1 ("Specific case wrapped in generic-sounding language"), F2 ("Causal chain broken between `user_side_signal` and `bridge_to_product`"), F3 ("Boilerplate-template `transferable_disposition` text untethered to a real signal"), F4 ("`covers_product_ids` claims multi-product reach but `transferable_disposition` only explains one"). Invented short labels are NOT used.
- **Honor D-16:** Closing "Reading Scope Note" caps per-batch manual review at ≈20-30 factors and prioritises reflow_triggered / trial_selected_delta_id rows when the manual_review_queue exceeds that cap.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- VAL-03 / VAL-05 / VAL-06 audit skeleton is on disk; ready to be filled in once 07-01..07-04 (run-mechanism + evidence-capture + batch-summary) deliver `tests/smoke/.runs/<ts>/index.json` + `batch_summary.json`.
- Next focus: plans **07-01, 07-02, 07-03, 07-04, 07-06** — three-stage runner mechanics, evidence-capture wrapper, batch-summary indices, and evolution observability hooks.
- No blockers.

## Self-Check: PASSED

- File exists: `[ -f .planning/phases/07-real-llm-validation/case_analysis.md ]` → FOUND
- H1 heading: `grep -c "^# Case Analysis"` → 1
- D-14 header note: `grep -c "D-14"` → 1
- VAL-03 / VAL-05 / VAL-06 H2s: each grep → 1
- F1..F4 H3 headings (verbatim): each grep → 1
- Verbatim phrase checks (`generic-sounding language`, `user_side_signal`, `bridge_to_product`, `Boilerplate`, `untethered`, `covers_product_ids`, `multi-product`): each grep ≥ 1
- Invented labels (Misroute / Hallucinated Coverage / Reflow Trigger / Trial-Selection Anomaly): grep → 0
- D-16 reading-scope phrase (`20.?30 | 20-30 | 20 to 30`): grep → 2
- Commit `0056ad6` exists: `git log --oneline | grep 0056ad6` → FOUND

---
*Phase: 07-real-llm-validation*
*Completed: 2026-05-26*
