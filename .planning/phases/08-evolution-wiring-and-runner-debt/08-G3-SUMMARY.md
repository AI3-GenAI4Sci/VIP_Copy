---
phase: 08-evolution-wiring-and-runner-debt
plan: G3
subsystem: evolution-distill + validation-runner
tags: [distill-skill, target-skill, evidence, trial-skipped, F-08-01, F-08-D]
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    plan: G1
    provides: distill-skill-deltas is loaded through the single skill_loader primitive
  - phase: 08-evolution-wiring-and-runner-debt
    plan: G2
    provides: production copy/rubric payloads now expose the signed user context boundary
  - finding: F-08-01-d8f-trial-unreachable
    provides: target_skill path mismatch root cause
  - finding: F-08-D-delta-mechanism-redesign
    provides: dual-track distill and evidence-persistence gap analysis
provides:
  - distill-skill-deltas SKILL prose with success-path and failure-path trajectory attention
  - canonical target_skill contract: current/<skill-slug>/SKILL.md
  - target_skill pattern in record_delta_observation, record_delta_change, and submit_delta_distillation_final specs
  - runtime target_skill validation in all three distill handlers
  - _patch_from_portfolio_row emits observable trial_skipped stderr lines for skipped deltas
  - _distill_after_stage1 persists distill RecordingProvider trace under distill_evidence/
affects:
  - 08-G4
  - 08-G5
  - Stage 3 real-LLM evolution diagnostics
tech-stack:
  added: [python re module]
  patterns:
    - "tool spec pattern + handler runtime validation + runner path gate stay aligned"
    - "distill evidence uses the same flush_evidence path as production nodes"
    - "skipped trial deltas are observable, one stderr line per rejected row"
key-files:
  created: []
  modified:
    - workflow-skills/evolution/distill-skill-deltas/SKILL.md
    - seers_harness/tools/evolution_tools.py
    - seers_harness/validation/runner.py
    - tests/test_evolution_tools.py
    - tests/test_validation_runner.py
key-decisions:
  - "target_skill is now canonical live-root relative path, not a bare skill name."
  - "submit_delta_distillation_final validates target_skill after DeltaDistillationArtifact validation so final artifacts cannot bypass the record handler pattern check."
  - "distill_evidence flush is best-effort; a cleanup failure logs safe_exc and does not mask the distill artifact."
  - "distill SKILL prose uses project vocabulary only and avoids user-example literals."
patterns-established:
  - "For LLM-emitted file paths, enforce the same regex at JSON schema, handler validation, and runner resolution."
  - "Every skip branch in the trial gate should say why it skipped."
requirements-completed: []
metrics:
  duration: 46min
  completed: 2026-05-28T03:43:00Z
  tests_added: 11
  tests_total: 351
---

# Phase 08 Plan G3: Distill Contract + Evidence Summary

**The distill loop now has a canonical `target_skill` path contract, dual-track trajectory prose, observable skipped trials, and on-disk `distill_evidence/` traces.**

## Performance

- **Duration:** ~46 min
- **Completed:** 2026-05-28T03:43:00Z
- **Tasks:** 2
- **Tests added:** 11
- **Full suite:** 351 passed

## Accomplishments

- Rewrote `workflow-skills/evolution/distill-skill-deltas/SKILL.md` around `success-path pattern attention` and `failure-path pattern attention`, with a dedicated `target_skill format` section.
- Added `_TARGET_SKILL_PATTERN` and shared target_skill schema property to `seers_harness/tools/evolution_tools.py`.
- Added runtime pattern validation for:
  - `record_delta_observation`
  - `record_delta_change`
  - `submit_delta_distillation_final`
- Added stderr observability in `_patch_from_portfolio_row`:
  - `reason=non_modify_skill`
  - `reason=target_unresolvable`
- Added `flush_evidence(distill_provider.request_log, stage1_request_dir / "distill_evidence")` in `_distill_after_stage1`, with safe best-effort cleanup logging.

## Task Commits

- `ca1ea21` — recovery commit containing G3 distill target-skill contract, evidence persistence, skipped-trial observability, and tests.

## Files Created/Modified

- `workflow-skills/evolution/distill-skill-deltas/SKILL.md` — dual-track prose and target_skill contract.
- `seers_harness/tools/evolution_tools.py` — target_skill schema pattern and runtime validation.
- `seers_harness/validation/runner.py` — skip logging and distill evidence persistence.
- `tests/test_evolution_tools.py` — target_skill pattern/spec/prose gates.
- `tests/test_validation_runner.py` — skip logging and distill evidence persistence tests.

## Deviations from Plan

- Existing evolution tool fixtures used bare skill names. They were updated to canonical `current/.../SKILL.md` paths as part of RED setup so existing happy-path tests reflect the new contract.
- The plan requested 9 tests; 11 were added because submit-final target_skill validation and the successful `_patch_from_portfolio_row` no-log path were worth pinning explicitly.

## Verification

```bash
.venv/bin/python -m pytest tests/test_evolution_tools.py -q
# 38 passed in 0.09s

.venv/bin/python -m pytest tests/test_validation_runner.py -k "patch_from_portfolio_row or distill_persists or distill_evidence_flush_failure" -q
# 5 passed, 22 deselected in 0.08s

.venv/bin/python -m pytest tests/test_evolution_tools.py tests/test_validation_runner.py tests/test_evolution_schema_design.py -q
# 79 passed in 0.57s

grep -nE '低价大牌|周三早.{0,2}9.{0,2}点|代理父亲|信息饕餮|多娃妈妈' workflow-skills/evolution/distill-skill-deltas/SKILL.md || true
# 0 hits

.venv/bin/python -m pytest -q
# 351 passed in 46.58s
```

## Next Phase Readiness

G4 can now wire the real selection/trial mechanism: invalid or non-actionable deltas will be visible, valid `current/<skill>/SKILL.md` deltas can resolve, and distill traces will be available under `.runs/.../distill_evidence/` for Stage 3 debugging.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-28*
