---
phase: 03-tool-loop-dag-integration
plan: 02
slug: loop-06-payloads-audit
subsystem: testing
tags: [pytest, static-audit, loop-06, conditional-skip, payloads]

# Dependency graph
requires:
  - phase: 02-single-provider-path
    provides: pytest harness layout + Phase 2's 100-test green baseline (test_provider_line_budget.py is the canonical static-audit pattern this plan reuses)
provides:
  - LOOP-06 invariant pinned by automated test (1 unconditional + 3 conditional functions)
  - cross-plan handshake — when Plan 03-03 lands payloads.py the 3 skipped tests auto-activate with no edit to this file
affects: [03-03 (creates payloads.py — must satisfy invariants this audit pins), Phase 5 CLEAN-01 (legacy quota field removal in c14_invariants.py — this audit catches any regressive vendoring back into seers_harness/)]

# Tech tracking
tech-stack:
  added: []
  patterns: [static-file audit via pathlib + read_text + substring/regex (no module import), pytest.skip-when-source-file-absent for cross-plan handshake]

key-files:
  created: [project/tests/test_payloads_loop06_audit.py]
  modified: []

key-decisions:
  - "Reused existing pattern from test_provider_line_budget.py: module-level pathlib + read_text, function-scoped pytest/re imports — keeps the test file's static-import surface stdlib-only."
  - "FORBIDDEN_QUOTA_FIELDS as a module-level tuple shared between Test 1 and Test 4 — single source of truth for the three c16 legacy field names; Test 1 walks the whole tree, Test 4 narrows to payloads.py once it exists."
  - "Skip messages on Tests 2-4 use the exact phrase 'payloads.py not yet created — Plan 03-03 will activate this test' for cross-plan traceability per orchestrator constraint."
  - "Collected violations across all files for Test 1 (rather than failing on first hit) — a regressive port to multiple files is reported in one shot, not iteratively."

patterns-established:
  - "Pre/post-creation static audit: a test file can pin invariants for a source file that does not yet exist by combining unconditional tree-wide absence-scans (always run) with PAYLOADS_PATH.exists() short-circuits on the positive presence-scans — gives Plan N a way to ratchet contracts that Plan N+1 will satisfy without requiring Plan N+1 to add new tests."

requirements-completed: [LOOP-06]

# Metrics
duration: ~5min
completed: 2026-05-25
---

# Phase 03 Plan 02: LOOP-06 Payloads Audit Summary

**4-function static audit pins master_plan §4.5's LOOP-06 invariants — works whether or not `seers_harness/workflow/payloads.py` exists, with 1 unconditional tree-wide absence scan + 3 conditional presence/absence checks that activate when Plan 03-03 lands the file.**

## Performance

- **Duration:** ~5 min
- **Tasks:** 2 (Task 1 read-only state verification, Task 2 audit-test write + run)
- **Files modified:** 1 (created `project/tests/test_payloads_loop06_audit.py`)
- **Lines:** 77 total / 63 non-blank-non-comment (planner targeted ~50-70; landed within range)

## Accomplishments

- LOOP-06 turned from "RESEARCH §5 one-time grep verification" into a **continuous automated guard** — any future regressive port of `factor_angles_per_target_product`, `copy_candidates_per_factor_angle`, or `max_candidates_per_request_formula` into `seers_harness/` trips Test 1 immediately, with full path:line:token report listing **all** hits at once (not just first match).
- Cross-plan handshake locked: Plan 03-03 will create `seers_harness/workflow/payloads.py`; the 3 conditional tests auto-activate with no edit to the audit file. Skip messages name Plan 03-03 explicitly for traceability.
- Phase 3 boundary respected: NO `seers_harness/` files modified, NO preemptive `payloads.py` creation, NO `c14_invariants.py` touch (Phase 5 CLEAN-01 territory).

## Files Created/Modified

- `project/tests/test_payloads_loop06_audit.py` — 4 test functions, 77 lines total. Module-level imports stdlib-only (`pathlib`); `pytest` and `re` imported function-locally so the file can be statically analyzed without pytest installed. No `from seers_harness` import — pure source-as-text audit.

## Task Execution Table

| # | Task                                | Outcome                                                                                                                          |
| - | ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 1 | Verify RESEARCH §5 state            | All three checks returned 0 (no payloads.py, no legacy quota fields, no `candidate_generation_policy` references). State sound.  |
| 2 | Write & run audit (TDD static-audit form) | File created; `1 passed, 3 skipped` on the audit; `101 passed, 3 skipped` on full suite (no regression).                   |

## State Verification Record (Task 1)

| Check | Command                                                                       | Expected | Actual |
| ----- | ----------------------------------------------------------------------------- | -------- | ------ |
| 1     | `find project/seers_harness -name payloads.py \| wc -l`                       | 0        | 0      |
| 2     | grep for the 3 legacy quota field tokens across `project/`                    | 0        | 0      |
| 3     | grep for `candidate_generation_policy` across `project/`                      | 0        | 0      |

All three confirm RESEARCH §5's findings still hold — Task 2's audit assumptions are sound.

## LOOP-06 Coverage Matrix (master_plan §4.5 ↔ test functions)

| master_plan §4.5 invariant | Test function | Status today (no payloads.py) | Status post Plan 03-03 |
| -------------------------- | ------------- | ----------------------------- | ---------------------- |
| 1. Three c16 legacy quota fields absent from harness tree | `test_legacy_quota_fields_absent_from_entire_project_tree` | **PASS** (unconditional scan over `seers_harness/*.py`) | PASS (still scans entire tree, including new payloads.py) |
| 2. `candidate_generation_policy` dict with `unit='request/list_group'` and `score_all_candidates_together_after_hard_rules=True` | `test_candidate_generation_policy_present_when_payloads_py_exists` | SKIP | activates → PASS |
| 3. No `projection` / `projected_*` / `user_history_projection` keys | `test_no_projection_fields_in_payloads_py` | SKIP | activates → PASS |
| 4. Narrowed payloads.py-specific quota-field guard | `test_no_quota_field_references_in_payloads_py_when_exists` | SKIP | activates → PASS |

## Skip Behavior Note

`1 passed, 3 skipped` is the **expected end state for Plan 03-02 alone**. The three SKIP outcomes are not failures — they are deferred contracts. Plan 03-03 (Wave 2) creates `seers_harness/workflow/payloads.py` and the skips automatically convert to passes; the audit file does **not** need to be re-edited. The skip messages each include the phrase `"payloads.py not yet created — Plan 03-03 will activate this test"` for cross-plan traceability.

## Decisions Made

1. **`FORBIDDEN_QUOTA_FIELDS` tuple at module level (shared between Test 1 and Test 4)** — single source of truth; the three forbidden tokens appear as literal strings in the source so the planner's grep-count acceptance criterion (`>=3` literal hits) is satisfied via the tuple definition itself rather than via duplicated string literals scattered through test bodies.
2. **Function-scoped `pytest` / `re` imports** — keeps module-level imports stdlib-only, matching the existing pattern in `test_provider_line_budget.py`. Lets future tooling read the test file's static-import surface without requiring pytest in the environment.
3. **Test 1 collects all violations rather than failing on first hit** — a regression that vendors the legacy fields back into multiple files surfaces all of them in one assertion message, accelerating diagnosis.

## Deviations from Plan

None — plan executed exactly as written. Behavior block, action steps, all 7 acceptance criteria, and the verify command outputs all match. No defensive code, no helpers, no parametrization, no conftest changes.

## Issues Encountered

None.

## Verification Output

```
$ PYTHONPATH=. python -m pytest tests/test_payloads_loop06_audit.py -v
tests/test_payloads_loop06_audit.py::test_legacy_quota_fields_absent_from_entire_project_tree PASSED [ 25%]
tests/test_payloads_loop06_audit.py::test_candidate_generation_policy_present_when_payloads_py_exists SKIPPED [ 50%]
tests/test_payloads_loop06_audit.py::test_no_projection_fields_in_payloads_py SKIPPED [ 75%]
tests/test_payloads_loop06_audit.py::test_no_quota_field_references_in_payloads_py_when_exists SKIPPED [100%]
1 passed, 3 skipped in 0.01s

$ PYTHONPATH=. python -m pytest tests/ -q
101 passed, 3 skipped in 0.19s
```

## Acceptance Criteria Trace

| Criterion (PLAN.md Task 2)                                                          | Required           | Actual              |
| ----------------------------------------------------------------------------------- | ------------------ | ------------------- |
| File `project/tests/test_payloads_loop06_audit.py` exists                           | yes                | yes                 |
| `^def test_` count                                                                  | 4                  | 4                   |
| `from seers_harness` count                                                          | 0                  | 0                   |
| `^import pathlib` count                                                             | 1                  | 1                   |
| Forbidden-token literal hits                                                        | ≥3                 | 3                   |
| Audit-only run                                                                      | 1 passed, 3 skipped | 1 passed, 3 skipped |
| Full suite run                                                                      | exit 0, no regress | 101 passed, 3 skipped |
| Files modified outside `project/tests/`                                             | 0                  | 0                   |

## Open Questions for Plan 03-03

1. **payloads.py location** — pinned at `project/seers_harness/workflow/payloads.py` per master_plan §1.3. The audit's `PAYLOADS_PATH` constant fixes this exact path; if Plan 03-03 chooses a different location, the conditional tests will continue to skip silently — a soft failure mode the planner should be aware of. Recommend Plan 03-03 either honours the location OR explicitly updates `PAYLOADS_PATH` in this audit (with rationale recorded).
2. **`candidate_generation_policy` key shape** — Test 2 asserts the three substrings (`candidate_generation_policy`, `request/list_group`, `score_all_candidates_together_after_hard_rules`) appear anywhere in the file. It does NOT enforce that they are a Python dict literal — Plan 03-03 can satisfy the test by exposing the policy as a `Final[dict]`, a Pydantic model, or a function-returned mapping. Test 2 is a string-level audit; semantic correctness is Plan 03-03's design choice.
3. **Phase 5 CLEAN-01 boundary** — `c14_invariants.py` and `dag_runner.py` (legacy quota field references in c16) live outside `seers_harness/` in c17 today; Test 1 only walks `seers_harness/`. If Plan 03-03 ports either of those modules into `seers_harness/`, Test 1 will start scanning them automatically — desired behavior.

## Next Plan Readiness

- LOOP-06 contract live and automated.
- Plan 03-03 (Wave 2) can proceed; success criteria for that plan now include "the 3 skipped tests in `test_payloads_loop06_audit.py` flip to passing once `seers_harness/workflow/payloads.py` is created".
- Full Phase 1+2+2.1 baseline (100 tests) preserved + this plan's 1 active + 3 deferred = **101 passed, 3 skipped**.

## Self-Check: PASSED

- File exists: `project/tests/test_payloads_loop06_audit.py` — FOUND
- Audit-alone outcome: `1 passed, 3 skipped` — confirmed
- Full-suite outcome: `101 passed, 3 skipped` — confirmed
- All 8 PLAN.md Task 2 acceptance criteria — verified above

---
*Phase: 03-tool-loop-dag-integration*
*Completed: 2026-05-25*
