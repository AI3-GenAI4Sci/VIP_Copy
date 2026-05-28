---
phase: 08-evolution-wiring-and-runner-debt
plan: G2
subsystem: workflow-payloads + copy-skill
tags: [context-disclosure, F-08-C, copy-payload, rubric-payload, prompt-cache]
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    plan: G1
    provides: real SKILL.md prose is loaded into production nodes via load_skill_prose
  - finding: F-08-C-context-budget
    provides: copy_generation cache_miss was too low because user_state was stripped
  - artifact: seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md
    provides: signed field boundary and cache_miss target band
provides:
  - copy_payload_for now includes signed user_state_summary and user_state_signals groups
  - rubric_payload_for now receives the same bounded user signals plus factors_artifact
  - rubric candidate rows preserve bridge_logic / used_copyable_hooks / intended_effect
  - generate-copy-candidates hook source rule now allows signed payload fields while banning visible behavior-list identifiers
  - tests/test_payloads_disclosure.py pins the signed boundary, field order, exclusions, bridge passthrough, dispatch, and SKILL prose gate
affects:
  - 08-G3
  - 08-G4
  - 08-G5
  - phase-7 real-LLM acceptance rerun
tech-stack:
  added: []
  patterns:
    - "bounded user_state disclosure via ordered helper functions, never blanket-whitelist raw user_state"
    - "payload ordering: stable summary before high-entropy per-request signals"
    - "float normalization to 2 decimal places for prompt stability"
key-files:
  created:
    - tests/test_payloads_disclosure.py
  modified:
    - seers_harness/workflow/payloads.py
    - workflow-skills/current/generate-copy-candidates/SKILL.md
key-decisions:
  - "CONTEXT_DISCLOSURE_ANALYSIS.md remains the source of truth; Task 2 did not modify it."
  - "copy_payload_for and rubric_payload_for expose exactly the signed field groups, not raw user_state."
  - "rubric_payload_for keeps copy_artifact-only calls backward compatible by defaulting factors_artifact to None."
  - "The pre-existing rewrite of generate-copy-candidates/SKILL.md was preserved; G2 only changed the hook-source rule line in that dirty file."
patterns-established:
  - "Disclosure helpers should centralize signed field lists and emit nulls for absent fields to preserve fixed key order."
  - "Rubric payloads should carry candidate bridge metadata verbatim instead of forcing the judge to infer it from visible copy."
requirements-completed: []
metrics:
  duration: 55min
  completed: 2026-05-28T02:55:45Z
  tests_added: 6
  tests_total: 340
---

# Phase 08 Plan G2: Context Disclosure Boundary Summary

**`copy_payload_for` and `rubric_payload_for` now expose the signed G2 field boundary: stable user summaries first, signal-dense behavior/product fields second, and candidate bridge logic preserved for the rubric judge.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-05-28T02:00:00Z
- **Completed:** 2026-05-28T02:55:45Z
- **Tasks:** 1 implementation task after prior G2-T1 sign-off
- **Files modified:** 3
- **Files created:** 1

## Accomplishments

- Added ordered payload helpers in `seers_harness/workflow/payloads.py` for:
  - `user_state_summary.profile`: `gender`, `age`, `city_level`, `vip_level`, `is_svip`
  - `user_state_summary.context`: `device_type`, `hour`
  - `user_state_signals.profile_counts`: signed count/price fields with 2-decimal float normalization
  - `user_state_signals.behavior_top_lists`: signed behavior top-list fields only
  - `user_state_signals.target_product_derived`: `price_vs_user_baseline_ratio`, `brand_recent_touched`, `ctr_band`, `is_new`
- Extended `rubric_payload_for` with `factors_artifact` and candidate-level `bridge_logic`, `used_copyable_hooks`, and `intended_effect`, while keeping old copy-only callsites working.
- Updated `provider_payload_for_node` so `personalized_copy_rubric` receives both factor and copy artifacts.
- Rewrote the `generate-copy-candidates` hook-source rule to permit signed payload fields while forbidding behavior-list identifiers from becoming visible copy tokens.
- Added `tests/test_payloads_disclosure.py` with 6 tests covering sign-off, field order, exclusion list, float normalization, rubric bridge passthrough, provider dispatch, backward compatibility, and SKILL prose gates.

## Task Commits

- `ca1ea21` — recovery commit containing G2 context-disclosure implementation, tests, and current production SKILL prose used by the runner.

## Files Created/Modified

- `seers_harness/workflow/payloads.py` — adds bounded disclosure helpers and wires them into copy/rubric payloads.
- `workflow-skills/current/generate-copy-candidates/SKILL.md` — updates the hook-source rule inside the already-dirty rewritten SKILL prose.
- `tests/test_payloads_disclosure.py` — pins the signed disclosure boundary and related routing/prose contracts.

## Decisions Made

- `CONTEXT_DISCLOSURE_ANALYSIS.md` was treated as the signed source of truth and left untouched.
- Missing fields are emitted as fixed keys with `None`; this keeps output shape and key order stable across requests.
- Floats are rounded to 2 decimals at payload construction time to avoid long unstable float strings in prompts.
- Rubric payloads get the full signed copy disclosure boundary because the judge must reconstruct why the candidate should fit this user.

## Deviations from Plan

### Auto-fixed Issues

**1. Local pytest runner selection**
- **Found during:** RED verification for `tests/test_payloads_disclosure.py`
- **Issue:** `/opt/miniconda3/bin/python` is Python 3.13.5 and `pytest` segfaults in `_pytest.capture` before test collection.
- **Fix:** Used project `.venv/bin/python -m pytest`, which is Python 3.12.12 and matches the established workspace test path.
- **Verification:** New tests and full suite pass under `.venv`.
- **Impact:** Future G3/G4/G5 commands should use `.venv/bin/python -m pytest`, not bare `pytest`.

### Other Deviations

- `workflow-skills/current/generate-copy-candidates/SKILL.md` had a pre-existing full-file rewrite. G2 preserved that rewrite and changed only the signed hook-source rule line.
- The written plan mentions committing `feat(08-G2): impl context disclosure boundary`; this was not done because the current worktree contains unrelated dirty SKILL files and local untracked state.

## Issues Encountered

- Bare `pytest` and `/opt/miniconda3/bin/python -m pytest` both segfaulted with no normal pytest output. `python -X faulthandler -m pytest ...` identified the crash in `_pytest.capture.py` during initial conftest loading. The project virtualenv test runner is healthy.

## Verification

```bash
.venv/bin/python -m pytest tests/test_payloads_disclosure.py -q
# 6 passed in 0.01s

.venv/bin/python -m pytest tests/test_payloads_loop06_audit.py tests/test_payloads_disclosure.py -q
# 12 passed in 0.02s

grep -nE '低.{0,3}价.{0,3}大牌|大牌.{0,3}不贵|周三|代理父亲|信息饕餮|多娃妈妈|金卡仪式|睡前种草' workflow-skills/current/generate-copy-candidates/SKILL.md || true
# 0 hits

.venv/bin/python -m pytest -q
# 340 passed in 46.69s
```

Acceptance checks satisfied:

- `CONTEXT_DISCLOSURE_ANALYSIS.md` contains signed `Sign-off: 2026-05-28 ...`.
- `copy_payload_for` emits the signed §4 groups in fixed order and excludes explicit non-disclosed fields.
- `rubric_payload_for` receives factors plus per-candidate bridge metadata.
- `provider_payload_for_node` dispatches both `factor_discovery` and `copy_generation` artifacts into the rubric payload.
- SKILL prose contains no forbidden user-example phrases.
- Full test suite is green.

## User Setup Required

None.

## Next Phase Readiness

G2-T2 is complete. Proceed to **08-G3**: distill SKILL prose rewrite, target_skill 3-site contract, and distill evidence persistence. Use `.venv/bin/python -m pytest` for all verification commands.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-28*
