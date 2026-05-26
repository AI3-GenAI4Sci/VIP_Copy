---
phase: 06-evolution-chain-production-hardening
plan: 06-01
subsystem: evolution
tags: [evolution, delta-portfolio, tool-use, schema-design]
requirements_completed: [EVO-01, EVO-02, EVO-05, EVO-06, PROC-02]
dependency_graph:
  requires:
    - "seers_harness/domain/models.py — EvidenceRef shape"
    - "seers_harness/core/errors.py — ToolValidationError"
    - "seers_harness/tools/skill_tools.py — universal handler signature"
  provides:
    - "seers_harness/evolution/ — delta contracts and package surface"
    - "seers_harness/tools/evolution_tools.py — distill-skill-deltas handlers + specs"
    - "workflow-skills/evolution/distill-skill-deltas/SKILL.md — live tool-use skill"
    - "docs/reference_v2_schema_design.md — design-only v2 sketch"
  affects:
    - "future Phase 6 plans that build portfolio selection, trial isolation, sedimentation"
tech-stack:
  added: []
  patterns:
    - "tool-use skill: hand handlers + strict DeepSeek /beta specs + final submit artifact"
    - "privacy scan: handler-side string-walk over args rejecting private trace keys"
    - "self-rated metric ban at both spec and handler layer"
key-files:
  created:
    - seers_harness/evolution/__init__.py
    - seers_harness/evolution/delta_portfolio.py
    - seers_harness/tools/evolution_tools.py
    - workflow-skills/evolution/distill-skill-deltas/SKILL.md
    - docs/reference_v2_schema_design.md
    - tests/test_evolution_tools.py
    - tests/test_evolution_schema_design.py
  modified: []
decisions:
  - "Belief is computed by portfolio code from trial outcomes, never model-emitted (Principle 10)"
  - "Reference v2 is design-only in Phase 6; no emitter, migration, or live v2 writer ships"
  - "Privacy scan walks every nested string in args; blocks 6 known private trace key names"
  - "EvolutionTools live in seers_harness/tools/evolution_tools.py (own registry) to keep skill_tools.py focused"
  - "Task 06-01-05 audits consolidated into tests/test_evolution_schema_design.py per plan permission"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-05-26"
  tests_added: 46
  tests_passing: 170
  baseline_before: 125
---

# Phase 6 Plan 06-01: Current-Schema Evolution Contracts And Tool-Use Delta Distillation Summary

Phase 6 plan 06-01 introduces the workspace evolution surface as data —
typed delta contracts, a rewritten ``distill-skill-deltas`` tool-use
skill with privacy-scanning handlers, a docs-only reference v2 sketch,
and source audits proving the retired runtime selection vocabulary did
not leak back into live workspace surfaces.

## Goal

Add the current-schema evolution surface without copying old runtime
evolution flows. The workspace now has strict delta proposal/portfolio
contracts, a tool-use rewrite of ``distill-skill-deltas`` with privacy
and self-rated-metric gates, a v2 schema **design** document explicitly
marked "Not emitted in Phase 6", and audits that lock out the retired
``compare-champion-bundles`` / ``select-seed-probes`` / ``champion``
vocabulary from workspace live surfaces.

## Outputs

| Task | Scope | Commit |
|---|---|---|
| 06-01-01 | `seers_harness/evolution/` package; `DeltaProposal`, `DeltaPortfolioRow`, `DeltaDistillationArtifact` Pydantic contracts with `extra=forbid` and non-empty `evidence_refs` invariant | `ff7ef4d` |
| 06-01-02 | `seers_harness/tools/evolution_tools.py` — three hand handlers + strict DeepSeek /beta specs; privacy scan; self-rated metric ban; 32 unit tests | `7a0fdaf` |
| 06-01-03 | `workflow-skills/evolution/distill-skill-deltas/SKILL.md` — Phase 4 eight-section style with current vocabulary | `b3fe023` |
| 06-01-04 | `docs/reference_v2_schema_design.md` (design only) + `tests/test_evolution_schema_design.py` (13 audits) | `e07a657` |
| 06-01-05 | Plan verification step-3 grep gate as a test; broader negative-surface audits consolidated into 06-01-04 per plan permission | `3fd8612` |

## Requirement Coverage

- **EVO-01** — Workspace live surfaces contain no ``compare-champion-bundles`` /
  ``select-seed-probes`` skill folders. ``workflow-skills/evolution/``
  ships only ``distill-skill-deltas``. Three audit tests
  (``test_workspace_workflow_skills_evolution_does_not_have_compare_champion_bundles``,
  ``test_workspace_workflow_skills_evolution_does_not_have_select_seed_probes``,
  ``test_plan_verification_step_3_grep_gate``) lock it.
- **EVO-02** — ``distill-skill-deltas`` is rewritten as a true tool-use skill.
  Three hand handlers (``record_delta_observation``, ``record_delta_change``,
  ``submit_delta_distillation_final``) enforce structure, evidence refs,
  privacy scan, and final submit; the model never emits self-rated metrics
  or raw private trace text. SKILL.md mentions all three handlers and
  uses current vocabulary (delta / proposal / change / trial / trajectory /
  portfolio / belief update).
- **EVO-05** — Reference v2 is design-only. ``docs/reference_v2_schema_design.md``
  contains the literal phrase "Not emitted in Phase 6" and four audit
  tests enforce no v2 emitter function (``emit_v2_*``, ``write_v2_*``,
  ``materialize_v2_*``, ``export_v2_*``) and no v2 writer class
  (``V2Emitter``, ``V2Writer``, ``ReferenceV2Writer``, ``ReferenceV2Emitter``)
  ships in ``seers_harness/``.
- **EVO-06** — Evolution field names use current schema language
  (delta / proposal / trial / trajectory / portfolio / belief). The
  ``champion`` and ``candidate bundle`` vocabularies are absent from
  workspace evolution Python files; ``test_workspace_evolution_module_files_do_not_contain_champion``
  enforces.
- **PROC-02** — PLAN.md "Skills/Methods" section names ``write-a-skill``,
  ``tdd``, and ``verification-before-completion`` as the skills this
  plan relies on. Each task in this plan applied one of those skills
  (the new SKILL.md follows the Phase 4 Matt-style discipline; tests
  landed alongside implementation; the plan's two grep gates and pytest
  command ran green before each commit).

## Verification Gates

All three PLAN.md verification commands pass:

| Gate | Result |
|---|---|
| `pytest tests/test_evolution_tools.py tests/test_evolution_schema_design.py -q` | 46 passed |
| `rg 'confidence\|score\|probability\|uncertainty\|strength' seers_harness/evolution seers_harness/tools/evolution_tools.py workflow-skills/evolution/distill-skill-deltas/SKILL.md` | only deliberate ban-list literals in `evolution_tools.py`; never a Pydantic field, tool-spec property, or skill-prose claim |
| `rg 'compare-champion-bundles\|select-seed-probes' workflow-skills seers_harness/evolution` | 0 hits |

Full project suite from workspace root:
`uv run --python 3.12 --extra dev python -m pytest -q` → **170 passed, 1 skipped in 0.25s**
(baseline 125 + 46 new tests = 171 collected; the skipped one is a
real-LLM smoke test unrelated to this plan; arithmetic check:
125 + 32 (test_evolution_tools.py) + 14 (test_evolution_schema_design.py) = 171.)

## Tool-Use Contract Shape

The rewritten skill follows the existing harness shape exactly:

- Every handler signature is ``def fn(args: dict, state: dict) -> str``.
- Handlers return literal strings (``"recorded"`` / ``"finalized"``).
- Every spec is strict (``additionalProperties=False``, ``required == properties.keys()``).
- ``record_delta_observation`` and ``record_delta_change`` accumulate into
  ``state["delta_observations"]`` and ``state["delta_changes"]``.
- ``submit_delta_distillation_final`` validates a ``DeltaDistillationArtifact``
  and writes ``state["final_artifact"]``, terminating the loop.

The privacy scan walks every nested string in the args tree and rejects
the six known private trace key names (``private_reasoning``,
``user_state``, ``raw_interest_fragment_private``, ``diagnostic_evidence_refs``,
``blocked_evidence_refs``, ``is_clk_c``). Tests parametrize over every
banned term to prove the gate fires on each one.

The self-rated metric ban runs at two layers: the strict tool spec
declares no field named ``confidence`` / ``score`` / ``probability`` /
``uncertainty`` / ``strength``, and the handler explicitly checks
top-level args for those keys before the Pydantic validator runs.
``test_record_delta_change_spec_does_not_expose_self_rated_keys``
asserts the spec layer; the parametrized handler tests assert the
runtime layer.

## Threat Model Coverage

| Threat | Mitigation | Evidence |
|---|---|---|
| T-06-01 (old runtime flows return as live behavior) | Source audit asserts absent | 3 tests in `test_evolution_schema_design.py` |
| T-06-02 (private trace leaks into durable delta records) | Handler privacy scan walks args | 9 tests in `test_evolution_tools.py` (6 parametrize over private terms + 1 in evidence_refs + 1 in proposed_change + 1 in observation) |
| T-06-03 (model self-rated metrics masquerade as posterior belief) | Spec + handler ban; portfolio computes from outcomes | 10 tests in `test_evolution_tools.py` + 1 spec defense test + `test_evolution_models_forbid_self_rated_metric_fields` |

## Reference v2 Boundary

``docs/reference_v2_schema_design.md`` sketches a flat record set
(``v2_delta``, ``v2_trajectory``, ``v2_evidence_ref``, ``v2_portfolio_row``)
that reuses the in-process field names. The "Not emitted in Phase 6"
section explicitly forbids:

- writing a ``v2`` emitter function or class,
- writing migration / conversion / batch-export helpers,
- promoting in-process records to a v2 file on disk,
- introducing a live ``v2_*`` writer surface,
- coupling the workspace harness to a specific reference storage path.

Two structural audits enforce this boundary against future drift:
``test_no_v2_emitter_function_in_seers_harness`` and
``test_no_v2_writer_class_in_seers_harness``.

## Deviations from Plan

None. Plan executed exactly as written. The one consolidation note —
task 06-01-05's broader negative-surface audits landing alongside task
06-01-04 in a single test file — is explicitly authorized by the plan
text: *"The tests may live in `tests/test_evolution_schema_design.py`
if small."* Task 06-01-05 still received its own commit
(``3fd8612``) for the mirror of PLAN.md verification step 3.

## What Stayed Fixed

- ``seers_harness/domain/models.py`` — untouched; this plan only
  imported ``EvidenceRef`` from it.
- ``seers_harness/tools/skill_tools.py`` — untouched; evolution
  handlers ship in a sibling module with their own registry so the
  existing three-skill tool surface stays as Phase 1-5 left it.
- ``workflow-skills/current/`` — untouched. Phase 6 does not promote
  experimental deltas into live skills.
- ``harness-runtime/`` — untouched. D-23 boundary preserved.

## Handoff To Next Plans

The next Phase 6 plans build on this surface:

- **06-02** (per phase plan layout): portfolio selection, trial
  isolation around ``WorkflowRuntime.run_request``, evidence
  sedimentation. It will read ``DeltaPortfolioRow`` and write
  ``token_cost_delta_sum`` / ``success_count`` / ``belief_alpha`` /
  ``belief_beta`` from real trial outcomes.
- **06-03..06-05**: request-boundary concurrency safety, progress UX,
  promotion smoke. None of these touch evolution contracts — they
  exercise the harness around them.

## Self-Check: PASSED

- created files exist:
  - ``seers_harness/evolution/__init__.py`` — FOUND
  - ``seers_harness/evolution/delta_portfolio.py`` — FOUND
  - ``seers_harness/tools/evolution_tools.py`` — FOUND
  - ``workflow-skills/evolution/distill-skill-deltas/SKILL.md`` — FOUND
  - ``docs/reference_v2_schema_design.md`` — FOUND
  - ``tests/test_evolution_tools.py`` — FOUND
  - ``tests/test_evolution_schema_design.py`` — FOUND
- commits exist on branch ``worktree-agent-ae0830f0bd12c2519``:
  - ``ff7ef4d`` — FOUND
  - ``7a0fdaf`` — FOUND
  - ``b3fe023`` — FOUND
  - ``e07a657`` — FOUND
  - ``3fd8612`` — FOUND
