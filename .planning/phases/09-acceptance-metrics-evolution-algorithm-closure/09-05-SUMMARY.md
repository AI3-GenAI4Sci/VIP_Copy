---
phase: 09-acceptance-metrics-evolution-algorithm-closure
plan: 05
subsystem: testing
tags: [phase-09, acceptance, merged-node, skill-contract, real-run-evidence]
requires:
  - phase: 09-04
    provides: completed real DeepSeek Stage 3 evidence for run 20260530T022014Z
provides:
  - bounded 8-request reading tied to exact real-run evidence paths
  - merged-node stability verdict with diagnostic-only split guidance
  - lightweight SKILL wording repair and contract test against forcing patterns
affects: [phase-09-acceptance, personalized-copy-generation, acceptance-gates]
tech-stack:
  added: []
  patterns: [bounded case reading, skill prose contract testing, evidence-linked merged-node assessment]
key-files:
  created:
    - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CASE-READING.md
    - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-MERGED-NODE-ASSESSMENT.md
    - tests/test_phase09_skill_contract.py
    - .planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-05-SUMMARY.md
  modified:
    - workflow-skills/current/personalized-copy-generation/SKILL.md
key-decisions:
  - "Keep personalized_copy_generation as the merged production path; sampled failures map to wording-level repair, not architecture rollback."
  - "Use the completed real run 20260530T022014Z as the sole evidence source and record only exact local paths plus qualitative findings."
  - "Apply lightweight SKILL prose repair for plural distinctness, staged state awareness, and semantic source_factor_id linkage."
patterns-established:
  - "Bounded request reading replaces hard factor-count gates with evidence-linked quality assessment."
  - "SKILL contract tests enforce anti-forcing rules on prompt prose without scanning unrelated source files."
requirements-completed: [D9-MET-04, D9-MET-05, D9-MERGE-01, D9-MERGE-02, D9-MERGE-03, D9-MERGE-04, D9-MERGE-05, D9-MERGE-06, D9-MERGE-07, D9-MERGE-08, D9-MERGE-09, D9-GATE-05]
duration: 10min
completed: 2026-05-30
---

# Phase 09 Plan 05: Acceptance Metrics & Evolution Algorithm Closure Summary

**Bounded real-run reading for the merged personalized copy node, with evidence-linked stability verdict and a lightweight prose-only SKILL repair**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-30T04:29:05Z
- **Completed:** 2026-05-30T04:39:04Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Created an 8-request bounded reading from real run `20260530T022014Z`, with exact paths for scenario/input, generation artifact, generation `tool_calls.jsonl`, rubric artifact, and `evolution_snapshot.json`.
- Assessed the merged node as production-stable but wording-fragile, and explicitly kept any split-node idea diagnostic-only.
- Added a TDD-backed SKILL contract test and applied a prose-only repair to strengthen plural distinctness, staged state language, and semantic `source_factor_id` transduction.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create bounded case-reading artifact from real run evidence** - `44d22d5` (docs)
2. **Task 2: Decide merged-node stability and optional diagnostic control** - `f4e0f65` (docs)
3. **Task 3 RED: Add failing SKILL contract test** - `d2068b4` (test)
4. **Task 3 GREEN: Apply guarded lightweight SKILL repair** - `fb57bde` (feat)

**Plan metadata:** pending summary commit

## Files Created/Modified

- `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CASE-READING.md` - 8 sampled request readings with exact evidence paths and qualitative failure modes.
- `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-MERGED-NODE-ASSESSMENT.md` - merged production path verdict, repair decision, and diagnostic-only control rationale.
- `workflow-skills/current/personalized-copy-generation/SKILL.md` - lightweight wording repair for merged-path state handling, plural distinctness, and red-flag language.
- `tests/test_phase09_skill_contract.py` - source assertions for merged-path contract plus negative checks for forcing patterns.
- `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-05-SUMMARY.md` - execution summary for Plan 09-05.

## Decisions Made

- Kept the merged production path because sampled evidence showed intact staged factor/copy state and valid structural `source_factor_id` linkage.
- Treated repeated quality misses as wording-level shortcuts rather than architecture failure because the dominant failures were semantic weak linkage, product invisibility, single-angle collapse, and role/label compression.
- Applied only prose changes to the live SKILL surface and blocked hard thresholds, JSON skeletons, internal examples, enumeration prompting, and split-node production language through a dedicated contract test.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `tests/` is ignored in the current repository rules, so `tests/test_phase09_skill_contract.py` had to be staged with `git add -f`. This was limited to the single planned test file.
- `workflow-skills/current/personalized-copy-generation/SKILL.md` is currently untracked in the worktree, so the planned SKILL repair also required targeted force-staging of that single file. No raw `.runs/` artifacts or unrelated ignored files were staged.

## User Setup Required

None - no external service configuration required.

## Verification

- `.venv/bin/python -m pytest tests/test_phase09_skill_contract.py -q` -> PASS (`3 passed`)
- `.venv/bin/python -m pytest tests/test_phase09_skill_contract.py tests/test_phase09_acceptance_gates.py -q` -> PASS (`7 passed`)
- Artifact gate check for sampled-request count and assessment repair decision -> PASS

## Next Phase Readiness

- Phase 09 now has a real-run bounded reading artifact and a merged-node assessment that can be cited without reintroducing factor-count gates.
- The live merged SKILL surface now encodes the specific failure patterns seen in run `20260530T022014Z`.
- No blocker remains inside Plan 09-05 scope.

## Self-Check: PASSED

- Found `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CASE-READING.md`
- Found `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-MERGED-NODE-ASSESSMENT.md`
- Found `workflow-skills/current/personalized-copy-generation/SKILL.md`
- Found `tests/test_phase09_skill_contract.py`
- Found commits `44d22d5`, `f4e0f65`, `d2068b4`, `fb57bde` in `git log`

---
*Phase: 09-acceptance-metrics-evolution-algorithm-closure*
*Completed: 2026-05-30*
