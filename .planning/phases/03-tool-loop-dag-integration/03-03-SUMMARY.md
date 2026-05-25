---
phase: 03-tool-loop-dag-integration
plan: 03
slug: dag-runner-integrate
status: complete
wave: 2
completed: 2026-05-25
requirements_satisfied: [LOOP-05]
must_haves_verified: 5
tests_green: 119
key_files:
  created:
    - project/seers_harness/workflow/__init__.py
    - project/seers_harness/workflow/payloads.py
    - project/seers_harness/workflow/dag_runner.py
    - project/tests/test_dag_runner_integration.py
  modified: []
metrics:
  duration: ~25min
  task_count: 3
  file_count: 4
---

# Phase 3 Plan 03-03: dag-runner-integrate Summary

## Goal restatement

Per LOOP-05 + master_plan §4.4, `WorkflowRuntime._run_node` collapses to one
`run_skill_via_tools(...)` call followed by `model_type.model_validate(result.artifact)`.
Plan 03-03 lands the c17 DAG runner that does exactly that — replacing c16's
~30 lines of polling-counter / closure-smuggle / lazy-import / re-injection
machinery with a single tool-loop call. It also lands `workflow/payloads.py`
for the first time in c17, activating Plan 03-02's three skipped LOOP-06
audits via cross-plan handshake (skipped → passing) without editing 03-02's
test file.

## Tasks executed

| # | Task | Files | Outcome |
|---|------|-------|---------|
| 1 | RED end-to-end integration test (2 functions) | `project/tests/test_dag_runner_integration.py` | Module-level `pytest.importorskip` flips test from skipped (pre-Task-3) to active (post-Task-3); pre-existing 114-test suite unaffected. |
| 2 | GREEN payloads.py + workflow/__init__.py | `project/seers_harness/workflow/__init__.py`, `project/seers_harness/workflow/payloads.py` | Module-level `candidate_generation_policy` literal landed; four payload builders exported (`provider_payload_for_node`, `factor_payload_for`, `copy_payload_for`, `rubric_payload_for`); zero forbidden tokens; cross-plan audit handshake activated (3 skipped → passing). |
| 3 | GREEN dag_runner.py with `_run_node` ≤80 lines | `project/seers_harness/workflow/dag_runner.py` | 57-line `_run_node` body, single `run_skill_via_tools(...)` call, `tool_loop_summary` event emitted, RUNNING/SUCCEEDED/FAILED records, classify_exception-driven retry shell. Both integration tests turn GREEN. |

## LOOP-05 coverage matrix

| ROADMAP success criterion | Test name | Evidence |
|---|---|---|
| #3 single-call chain `run_skill_via_tools(...) → model_validate(result.artifact)` | `test_run_node_factor_discovery_happy_path_returns_validated_artifact` | `grep -c 'run_skill_via_tools' dag_runner.py` = 3; `grep -c 'model_validate(result.artifact)' dag_runner.py` = 2; `_run_node` body = **57 visible lines** (target ≤80). |
| #4 no quota fields in payloads.py | `test_legacy_quota_fields_absent_from_entire_project_tree` + `test_no_quota_field_references_in_payloads_py_when_exists` | `grep -cE 'factor_angles_per_target_product\|copy_candidates_per_factor_angle\|max_candidates_per_request_formula' payloads.py` = **0**. |
| RESEARCH §4 REWRITE: `agent_loop_summary` → `tool_loop_summary` | Test A trace assertion + `grep -c 'tool_loop_summary' dag_runner.py` ≥ 1 | Test A asserts `"tool_loop_summary" in types and "agent_loop_summary" not in types`; both pass. `grep -c 'tool_loop_summary'` = 3; `grep -c 'agent_loop_summary'` = **0**. |
| RESEARCH §8 pitfall #4: inner `max_tool_calls=30` and outer `node.max_attempts` are two distinct budgets | `test_run_node_outer_retry_shell_kicks_in_when_inner_transient_budget_exhausts` | `node.max_attempts=2` + 3 transient turns + 1 happy turn → outer shell records 2 RUNNING / 1 FAILED (`error_category=transient_provider`) / 1 SUCCEEDED → artifact validates. |
| Five c16 anti-patterns deleted (raw_holder, _call closure, lazy import, check_feedback, max_rounds) | `grep -cE 'check_feedback\|raw_holder\|max_rounds\|lazy.*import\|from seers_harness.harness.agent_loop\|provider.generate_json\|response_format\|agent_loop_summary' dag_runner.py` | **0** matches. |

## `_run_node` line count (exact)

```
$ awk '/def _run_node/{flag=1; next} /^    def |^class /{flag=0} flag && !/^[[:space:]]*$/ && !/^[[:space:]]*#/' seers_harness/workflow/dag_runner.py | wc -l
      57
```

Budget target was ≤80 visible non-blank non-comment lines; achieved 57. The
margin reflects user-instruction discipline ("最少代码 — task goal first") —
the c17 runtime only carries the surface needed for Phase 3 integration
(provider, output_dir, trace, records). c16's ArtifactStore / SkillRegistry /
CircuitBreaker / ProviderLimiter / SessionManager / AgenticController were
not ported; their absence is intentional and consistent with the c17
rebuild philosophy. If any of them are required by Phase 4 SKILL.md prose
or Phase 7 real-DeepSeek runs, they will arrive in their own plan, not as
preserved scaffolding.

## Cross-plan handshake confirmation

```
$ PYTHONPATH=. python -m pytest tests/test_payloads_loop06_audit.py -v 2>&1 | tail -5
tests/test_payloads_loop06_audit.py::test_legacy_quota_fields_absent_from_entire_project_tree PASSED
tests/test_payloads_loop06_audit.py::test_candidate_generation_policy_present_when_payloads_py_exists PASSED
tests/test_payloads_loop06_audit.py::test_no_projection_fields_in_payloads_py PASSED
tests/test_payloads_loop06_audit.py::test_no_quota_field_references_in_payloads_py_when_exists PASSED
============================== 4 passed in 0.01s ===============================
```

Pre-Plan-03-03 state was "1 passed, 3 skipped" (Plan 03-02 baseline).
Post-Plan-03-03 Task 2 state is "4 passed, 0 skipped". The three audit
tests activated automatically because `PAYLOADS_PATH.exists()` flipped
`True` — no edit to `tests/test_payloads_loop06_audit.py` was made.

## Phase boundary respected

Per RESEARCH §4 + ROADMAP boundary, `c14_invariants.py` and `agent_loop.py`
deletion are Phase 5 work (CLEAN-01 + CLEAN-02). In the c17 rebuild these
two files do not exist at all — they were never carried forward from c16:

```
$ find seers_harness -name "c14_invariants.py" -o -name "agent_loop.py"
(empty result)
```

This plan touched ONLY `project/seers_harness/workflow/` (3 new files) and
`project/tests/test_dag_runner_integration.py` (1 new file). No edits to
`agentic/`, `tools/`, `core/`, `domain/`, `provider_runtime/`, or any
existing test file.

## Deviations from plan

**1. [Rule 3 - Blocking issue resolved] Removed deletion-narrative tokens from module docstrings**
- **Found during:** Task 2 + Task 3 verification
- **Issue:** The audit grep is a literal substring scan. My initial module
  docstrings on `payloads.py` and `dag_runner.py` enumerated the deleted
  legacy tokens by name (e.g., "factor_angles_per_target_product is
  deliberately ABSENT") — which the audit then flagged as **violations**
  because the literal token appears in the file regardless of whether it
  describes presence or absence.
- **Fix:** Rewrote both docstrings to describe the absences abstractly
  (e.g., "the c16 legacy fan-out quota fields are deliberately ABSENT from
  this module — see tests/test_payloads_loop06_audit.py for the literal
  token guard"). Same for the dag_runner deletion narrative — it now
  references "RESEARCH §4 + §8 for the table and pitfalls" instead of
  enumerating the c16 line numbers and token names.
- **Files modified:** `seers_harness/workflow/payloads.py` (docstring),
  `seers_harness/workflow/dag_runner.py` (docstring)
- **Diagnosis:** The deletion narrative was helpful prose for a reader but
  hostile to a literal-substring auditor. The fix preserves intent and
  defers the "what was deleted" detail to the RESEARCH document, which is
  the proper home for archaeology anyway.

**2. [Plan-spec ↔ schema field-name mismatch] Test fixtures use c17 schema field names**
- **Found during:** Task 1 fixture design
- **Issue:** Plan 03-03's behavior block (line 132) asserts
  `.personalization_factors length == 1`, but the c17 `FactorDiscoveryArtifact`
  schema (`seers_harness/domain/models.py` L112-114) declares the field
  as `factors: list[PersonalizationFactor]` — not `personalization_factors`.
- **Fix:** Test A asserts `len(artifact.factors) == 1` against the actual
  c17 Pydantic schema. The plan's `personalization_factors` was carried
  over from c16 schema naming; c17 chose the shorter form during Phase 1.
  The plan's contract (1 factor materialized, factor_id matches input)
  is preserved verbatim — only the attribute name is corrected.
- **Files modified:** none beyond the new test file

**No other deviations.** No Rule 4 architectural decisions surfaced — the
c17 minimal-runtime approach was already implicit in master_plan §4.4 and
the user's "minimum viable code, task goal first" instruction.

## Open questions for Phase 4

1. **SKILL.md prose mention of `tool_loop_summary`?** — The renamed trace
   event surfaces in `runtime.trace`. Phase 4's SKILL.md rewrite phase
   should consider whether SKILL prose mentions tool-loop diagnostics
   (e.g., "if turns_used > 5 the model is over-deliberating") or whether
   that diagnostic guidance lives in the rubric/judge SKILL only. The
   trace contract is locked here in Phase 3; SKILL prose is locked in
   Phase 4; the cross-reference is a Phase-4-input flag.

2. **WorkflowRuntime concurrency / observability** — c17's `WorkflowRuntime`
   is single-threaded with in-memory `trace` and `records` lists. c16
   carried `ProviderLimiter`, `CircuitBreaker`, `ArtifactStore` (filesystem
   trace persistence). For Phase 7 real-DeepSeek runs we will need at
   least filesystem trace persistence — flag this as a Phase 5/6/7
   carrying-capacity question, not a Phase 3 LOOP-05 question.

## Phase 7 confirmation points

- The `reasoning_content` echo wire format (LOOP-02 + RESEARCH §2) is
  locked at the loop layer (Plan 03-01 Task 4) and exercised at the
  integration layer (Plan 03-03 Test A's `last_reasoning_content == "R"*30`).
  ScriptedProvider is a contract proxy; Phase 7 must verify the same
  echo path against the live DeepSeek `/beta` endpoint with
  `model=deepseek-v4-pro` + `reasoning_effort=max`.

- The two distinct retry budgets (inner `max_transient_retries_per_turn=2`
  vs. outer `node.max_attempts`) are locked at the dag_runner layer here
  (Test B walks both budgets through one happy-path artifact). Phase 7
  should observe both budgets honored under real network jitter.

## Gate

```
$ PYTHONPATH=. python -m pytest tests/ -q 2>&1 | tail -1
119 passed in 0.21s
```

- **Tests green:** 119 passed, 0 skipped (Phase 1 68 + Phase 2 32 + Phase 3
  03-01 ~13 + Phase 3 03-02 4 + Phase 3 03-03 2 = 119; matches the
  plan's ≥119 target).
- **`_run_node` body line count:** 57 ≤ 80 (verified by awk + wc -l).
- **Cross-plan handshake:** activated; 4 audit tests passing, 0 skipped.
- **Anti-pattern grep:** 0 hits across all 8 forbidden tokens.
- **Phase boundary:** `c14_invariants.py` and `agent_loop.py` not present
  in c17; this plan did not introduce them.

## Self-Check: PASSED

Created files (all confirmed via `test -f` or filesystem inspection):
- FOUND: `project/seers_harness/workflow/__init__.py`
- FOUND: `project/seers_harness/workflow/payloads.py`
- FOUND: `project/seers_harness/workflow/dag_runner.py`
- FOUND: `project/tests/test_dag_runner_integration.py`

Deltas confirmed:
- Pre-plan baseline: 114 passed, 3 skipped.
- Post-plan: 119 passed, 0 skipped.
- Delta: +5 tests (3 audit-skips activated + 2 new integration tests).
