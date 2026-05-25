---
phase: 01-schema-tools-foundation
plan: 01
slug: domain-schema
status: complete
wave: 1
completed: 2026-05-25
requirements_satisfied:
  - DATA-01
  - DATA-02
  - DATA-03
  - DATA-04
  - DATA-05
  - DATA-06
must_haves_verified: 7
tests_green: 13
key_files:
  created:
    - project/pyproject.toml
    - project/seers_harness/__init__.py
    - project/seers_harness/core/__init__.py
    - project/seers_harness/core/errors.py
    - project/seers_harness/domain/__init__.py
    - project/seers_harness/domain/models.py
    - project/seers_harness/tools/__init__.py
    - project/tests/__init__.py
    - project/tests/conftest.py
    - project/tests/test_models_factor.py
    - project/tests/test_models_bridge.py
    - project/tests/test_models_candidate.py
    - project/tests/test_models_rubric.py
    - project/tests/test_models_no_self_rated_fields.py
---

# Plan 01 — Domain Schema (Wave 1) — SUMMARY

## Goal

Establish the C17 domain layer (Pydantic v2 schemas) implementing DATA-01..06 plus the `project/` skeleton, `ToolValidationError`, and shared test fixtures — so Plan 02 tool handlers can import in Wave 2.

## Tasks executed

| Task | Status | Tests | Notes |
|------|--------|-------|-------|
| 1 — Skeleton + ToolValidationError + conftest | ✓ done | 0 (plumbing) | langgraph dropped per anti-pattern memo; pydantic>=2.7, pytest>=8, openai>=1.40 (optional). `core/errors.py` extends c16 verbatim with `ToolValidationError` (category="tool_validation", retryable=True). `tests/conftest.py` ships `sample_scenario_payload` + `sample_target_product_id` for Plan 02. |
| 2 — RED: 5 schema test files (DATA-01..06) | ✓ done | 13 collected, RED on missing models.py | One invariant per test. `test_models_no_self_rated_fields.py` scans every BaseModel subclass in `seers_harness.domain.models` for `{strength, confidence, uncertainty, probability, score}` via `inspect.getmembers` — empty offender list = pass. |
| 3 — GREEN: domain/models.py | ✓ done | 13/13 PASS | 94 non-blank/comment lines, target 60-180. All 7 must-haves satisfied. |

## DATA-* coverage matrix

| Requirement | Test(s) green | Evidence |
|-------------|---------------|----------|
| **DATA-01** transferable_disposition required | `test_transferable_disposition_required`, `test_factor_constructs_with_disposition` | `PersonalizationFactor()` raises `ValidationError` type=missing on `("transferable_disposition",)` |
| **DATA-02** STOP-GATE + c15 plain-text fields removed | `test_stop_gate_fields_absent`, `test_c15_legacy_fields_absent` | 12 forbidden fields all absent from `PersonalizationFactor.model_fields` |
| **DATA-03** BridgeLogic = c16 pair only | `test_c16_pair_present`, `test_c15_slots_absent` | `set(BridgeLogic.model_fields) == {"product_anchor", "relation_anchor"}` (asserted) |
| **DATA-04** considered_drafts + chosen_draft_index, model not enforcing equality | `test_considered_drafts_field_present`, `test_model_does_not_enforce_draft_text_equality` | CopyCandidate constructs with `text != considered_drafts[chosen_draft_index]` — equality deferred to handler in Plan 02 |
| **DATA-05** critique-before-verdict ordering + 7-axis surface, no c15 aggregates | `test_per_axis_field_order_critique_before_verdict`, `test_seven_axes_no_d4`, `test_rubric_judgment_has_seven_axis_capable_per_axis_list`, `test_legacy_rubric_fields_absent` | `PerAxisVerdict.model_fields` index order: `axis_id < verbatim_candidate_quote < bridge_to_anchor < templated_flag < verdict`. No `d4` field. 6 forbidden c15 aggregates all absent. |
| **DATA-06** no LLM self-rated metrics anywhere | `test_no_self_rated_fields_anywhere` | `inspect.getmembers(seers_harness.domain.models, ...)` scan returns empty `offenders` list |

## Architectural notes / deviations

1. **No `ConsideredAndRejected` model**: c16 had it; c17 deletes per ADR-03 §A3 (replaced by `reflect_on_coverage` mirror tool in Plan 02). PATTERNS line 174 said "keep it but drop the [RC-2, RC-7] comment" — but RESEARCH §A3 (which this plan tracks) supersedes: structural critique on PersonalizationFactor is gone in C17 (DATA-02 removes `considered_user_signals` + `considered_and_rejected` from the factor schema itself).
2. **EvidenceRef `model_config = {"extra": "ignore"}` added**: PATTERNS line 48-54 verbatim didn't include `model_config`; c17 adds it for consistency with the other 7 BaseModel subclasses (DATA-06 audit treats EvidenceRef as in-scope).
3. **No `NodeStatus` / `UserState` / `DerivedFeatures` / `Product` / `Scenario` BaseModels in models.py**: those c16 wrappers are out of scope for Plan 01 per PATTERNS lines 175-177 (defer to later phases). Plan 02 handlers will take `state: dict` directly (RESEARCH Pattern 6 dynamic-projection) — no schema upgrade needed for the payload dict.
4. **DataFactor `direction` placed before `transferable_disposition`** in field declaration order: this differs from the suggested order in the plan's <action> but the test suite only requires `transferable_disposition` to be required (no order assertion); placing `direction` earlier matches the `user_to_need / item_to_need / cross` priority. Pure stylistic — no test impact.

## Open questions for Plan 02

1. **`state["copies_artifact"]` vs `state["copy_artifact"]` key naming**: RESEARCH §A9 flagged as undecided. Plan 02 must lock the key. Recommendation: align with `state["factors_artifact"]` (plural-noun suffix) → `state["copies_artifact"]` and `state["judgments_artifact"]`.
2. **`ToolValidationError.__init__` signature** (for Plan 02 callers): `ToolValidationError(message: str, tool_name: str = "", arg_path: str = "")`. The `tool_name` defaults to "" so a handler can `raise ToolValidationError("text exceeds 16 chars", tool_name="record_candidate", arg_path="text")` and the loop layer (Phase 3) can grep `e.tool_name` / `e.arg_path` for fanout messages.
3. **`record_candidate` text/draft equality**: deferred from model to handler per RESEARCH §Pattern 2. Plan 02 TOOL-03 will enforce `text == considered_drafts[chosen_draft_index]` and raise `ToolValidationError(...arg_path="text")` on mismatch.

## Test command (Plan 02 inherits)

```bash
PYTHONPATH=. python -m pytest tests/test_models_*.py -x -q
# 13 passed in ~0.05s
```

## Gate

✓ All 5 success criteria from PLAN.md met. Plan 02 (Wave 2) unblocked.
