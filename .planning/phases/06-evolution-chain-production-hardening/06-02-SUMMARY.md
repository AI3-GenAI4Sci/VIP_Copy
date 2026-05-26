---
phase: 06-evolution-chain-production-hardening
plan: 06-02
subsystem: evolution
tags: [evolution, portfolio, trial-isolation, trajectory, sedimentation]
requirements_completed: [EVO-04, PROC-02]
dependency_graph:
  requires:
    - "seers_harness/evolution/delta_portfolio.py — DeltaPortfolioRow, DeltaProposal contracts from 06-01"
    - "seers_harness/workflow/dag_runner.py — WorkflowRuntime.run_request"
    - "tests/smoke/scripted_full_chain.py — 3-node ScriptedProvider chain"
  provides:
    - "load_portfolio_jsonl / write_portfolio_jsonl — durable portfolio I/O"
    - "belief_mean / update_after_trial — pure posterior bookkeeping"
    - "select_trial_delta — scarcity-weighted bandit selector with no-trial gate"
    - "TrajectoryRecord / trajectory_signature / buffer_trajectory / sediment_trajectories"
    - "seers_harness/evolution/trial_runner.py — SkillDeltaPatch + apply_delta_patch_temporarily + run_request_trial"
  affects:
    - "future Phase 6 plans 06-03..05 (request-boundary integration, progress UX, promotion smoke)"
tech-stack:
  added: []
  patterns:
    - "pure-function trial scheduling (D-25): one selector function + one context manager + one trial driver"
    - "lock-by-hash patching: original_text_sha256 refuses drifted live roots"
    - "round-robin diversity sedimentation: rare buckets survive a same-bucket flood"
    - "deterministic selection: injected random.Random keeps tests reproducible"
key-files:
  created:
    - seers_harness/evolution/trial_runner.py
    - tests/test_delta_portfolio.py
    - tests/test_trial_runner.py
    - tests/test_trajectory_evidence.py
  modified:
    - seers_harness/evolution/__init__.py
    - seers_harness/evolution/delta_portfolio.py
decisions:
  - "Posterior shape: Beta(alpha, beta); update_after_trial returns a NEW row (pure)"
  - "Selection trial probability = (1-rfr) * (1-tbp) * (1-pp); independent suppressors"
  - "Scarcity weight 1/(1+sample_count): un-sampled deltas dominate the priority pool"
  - "Empty applicable_surface treated as universally applicable so first-proposal trials work"
  - "Trial isolation via shutil.copytree of the live skill root into workspace_dir/skills"
  - "TrajectoryRecord excludes raw user_state, private reasoning, full provider messages"
  - "Trajectory dedup signature ignores request_id so repeated runs of the same delta dedupe"
  - "Round-robin sedimentation: bucket = (success, quality_bucket, token_cost_bucket, failure_category)"
  - "Task 06-02-04 integration test bundled into tests/test_trial_runner.py per plan instruction"
metrics:
  duration: "~12 minutes"
  completed_date: "2026-05-26"
  tests_added: 42
  tests_passing: 213
  baseline_before: 171
---

# Phase 6 Plan 06-02: Delta Portfolio, Trial Isolation, And Trajectory Evidence Summary

Phase 6 plan 06-02 turns the typed delta surface from 06-01 into runnable
mechanics: durable portfolio JSONL, a pure posterior update, a
deterministic scarcity-weighted selector, a temp-only patch isolation
context manager, a trial driver around `WorkflowRuntime.run_request`,
and a sedimentation pass that preserves rare diversity buckets while
rejecting private trace text.

## Goal

Stand up the lightweight portfolio + trial loop behind Phase 6 without
ever mutating `workflow-skills/current/` and without introducing a
scheduler, daemon, or limiter (D-19, D-25). A request may select one
applicable delta, run the full 3-node chain inside a temp surface,
record a compact trajectory, and update belief from the observed
outcome. Durable evidence is bounded by sedimentation rather than
storing every trace forever.

## Outputs

| Task | Scope | Commit |
|---|---|---|
| 06-02-01 | Portfolio JSONL I/O, `belief_mean`, `update_after_trial`, `select_trial_delta`, `TrajectoryRecord` + buffer/signature/sedimentation primitives, 17 unit tests | `600f2cb` |
| 06-02-02 | `seers_harness/evolution/trial_runner.py` — `SkillDeltaPatch`, `apply_delta_patch_temporarily`, `run_request_trial`, plus `TrialOutcome`; 9 isolation/integration tests in `tests/test_trial_runner.py` | `0faa7b3` |
| 06-02-03 | `tests/test_trajectory_evidence.py` — 16 tests covering dedup, privacy filter (parametrized over all 6 private trace keys), diversity round-robin, `max_rows` bounding, and `extra=forbid` enforcement | `b3b1ecd` |
| 06-02-04 | Integration test (`test_integration_select_trial_buffer_and_update`) bundled into `tests/test_trial_runner.py` per plan instruction; combined gate `pytest tests/test_delta_portfolio.py tests/test_trial_runner.py tests/test_trajectory_evidence.py -q` → 42 passed | `0faa7b3` |

## Requirement Coverage

- **EVO-04** — Lightweight delta-evolution mechanics ship in workspace
  only and never mutate live skills. The portfolio is JSONL data
  (`DeltaPortfolioRow` rows, never an LLM-emitted belief). Trial
  isolation copies the live skill root into a temp workspace and
  restores the temp file on every exit path. The integration test
  asserts the live root is byte-identical after a successful trial.
- **PROC-02** — PLAN.md's "Skills/Methods" section names `tdd`,
  `systematic-debugging`, and `verification-before-completion`. Each
  task in this plan applied tdd (tests landed alongside implementation)
  and verification-before-completion (the focused gate ran green
  before each commit, and the full 213-test suite ran green at the
  end).

## Verification Gates

All three PLAN.md verification commands pass:

| Gate | Result |
|---|---|
| `pytest tests/test_delta_portfolio.py tests/test_trial_runner.py tests/test_trajectory_evidence.py -q` | 42 passed in 0.10s |
| `pytest -q` (full suite) | 213 passed in 0.87s |
| Manual inspect: trial tests leave no modified files under `workflow-skills/current/` | confirmed (live root checked byte-by-byte after every trial test that takes a patch) |

`grep -nE 'workflow-skills/current/.+write|replace' seers_harness/evolution/trial_runner.py`
returns five hits, all in docstring prose, the `replacement_text`
Pydantic field, or the temp-side `target_in_temp.write_text(...)` call.
No hit targets the live `workflow-skills/current/` path.

## Selection Policy Shape

`select_trial_delta` is a single function (D-25 — small, no scheduler
service):

```
trial_prob = (1 - recent_failure_rate) *
             (1 - token_budget_pressure) *
             (1 - production_pressure)
```

If the rng exceeds `trial_prob`, no trial fires. Otherwise the function
filters `portfolio` to `status == "experimental"` rows whose
`applicable_surface` overlaps the caller's surface (or is empty,
treated as universally applicable for first-proposal cases), then
weights each by `scarcity * (belief_mean + 0.1)` where
`scarcity = 1 / (1 + sample_count)`. Weighted random pick over those
weights returns the trialed `delta_id`.

The 500-seed scarcity test asserts a freshly proposed delta is picked
more than 5× as often as a 50-sample delta with similar belief — the
scarcity weight ratio is roughly 50.

## Trial Isolation Contract

`apply_delta_patch_temporarily(live_skill_root, workspace_dir, patch)`:

1. `shutil.copytree(live_skill_root, workspace_dir / "skills")` mirrors
   the entire skill tree.
2. If `patch is not None`:
   - reads the live target file;
   - asserts `sha256(live_text) == patch.original_text_sha256` and
     raises `ValueError(... drift ...)` on mismatch;
   - captures the temp-side original content;
   - writes `patch.replacement_text` into the temp file only.
3. Yields the temp root path.
4. In `finally`, restores the temp file's original content. The live
   root is never touched.

`run_request_trial` wraps this around `runtime.run_request(...)` and
returns a `TrialOutcome` carrying `success`, `failure_category`,
`artifact_paths`, `tool_call_count` (summed from `runtime.trace`
`tool_loop_summary` events), `token_cost_observed` (defaults to 0; the
fake provider does not emit usage), and a derived `trial_delta_id`
(stable slug of the patched path).

Tests prove every leg of the contract: replacement visible inside the
context, restore on normal exit, restore after a body exception, drift
refusal, missing-target refusal, control-run (no patch) shape, full
3-node DAG runs and returns artifact paths under the temp surface, and
end-to-end select+trial+update producing `sample_count == 1` with the
live skill root unchanged.

## Trajectory Sedimentation

`sediment_trajectories` runs three filters in order:

1. **Privacy:** any record whose flat string fields contain
   `private_reasoning`, `user_state`, `raw_interest_fragment_private`,
   `diagnostic_evidence_refs`, `blocked_evidence_refs`, or `is_clk_c`
   is dropped (T-06-06 mitigation).
2. **Dedup:** records with identical `trajectory_signature` collapse;
   first occurrence wins. Signature ignores `request_id`, captures
   `trial_delta_id`, sorted node ids, success flag, failure category,
   quality bucket, and token-cost bucket.
3. **Diversity:** records bucket by `(success, quality_bucket,
   token_cost_bucket, failure_category)` and emit round-robin so a
   flood of `pass / low / no-failure / success` records cannot crowd
   out a rare `fail / low / schema / failure` or
   `pass / high / no-failure / success` row even when `max_rows` is
   tight. The diversity test (`max_rows=3` over a flood of 8 same-bucket
   rows plus 2 rare rows) proves both rare bucket ids survive.

The privacy parametrized test runs all six private trace keys; each
one drops the polluted record while keeping the clean record.

## Threat Model Coverage

| Threat | Mitigation | Evidence |
|---|---|---|
| T-06-04 (selection over-explores a poor delta or ignores scarcity) | Deterministic tests over scarcity, failure rate, and token pressure | 4 tests in `tests/test_delta_portfolio.py` (`test_select_trial_delta_high_failure_rate_yields_none`, `test_select_trial_delta_high_token_budget_pressure_yields_none`, `test_select_trial_delta_scarce_sample_outweighs_well_sampled`, `test_select_trial_delta_skips_non_experimental_rows`) |
| T-06-05 (failed trial leaves the skill surface patched) | Context manager `finally` restores temp file; live root never written | 4 tests in `tests/test_trial_runner.py` (`test_apply_delta_patch_temporarily_restores_on_normal_exit`, `test_apply_delta_patch_temporarily_restores_after_exception`, plus integration tests asserting live-root byte-equality after trial) |
| T-06-06 (evidence storage stores private data or grows without bound) | Sedimentation drops private terms and round-robin caps output at `max_rows` | 6 parametrized tests + 1 path-side test + 3 max_rows tests in `tests/test_trajectory_evidence.py` |

## Decisions Made

- **Posterior shape:** Beta(alpha, beta) with seed prior (1, 1).
  `update_after_trial` is a pure function returning a new
  `DeltaPortfolioRow`. The caller is responsible for replacing the row
  in the portfolio. Tests rely on this purity.
- **Trial probability formula:** independent multiplicative
  suppressors, so a rate=1 in any dimension forces no-trial. This was
  picked over a weighted sum because it makes single-dimension
  suppression a strict gate (PLAN.md "high recent failure rate
  lowering trial probability" reads as a strong signal, not a hint).
- **Scarcity weight:** `1 / (1 + sample_count)` — strictly positive,
  decays smoothly, and never sends weights to zero so a high-sample
  delta still has a non-zero pick probability after enough trials.
- **Applicable surface fallback:** an empty `applicable_surface` is
  treated as universally applicable. Without this, every freshly
  proposed delta would be ineligible until a later step tagged it,
  which would defeat task 06-02-01's "scarce samples increasing
  selection priority" acceptance criterion.
- **Trial isolation via copytree:** the simplest path. Git worktree
  isolation (mentioned in 06-RESEARCH) is left for a future plan that
  needs full git-aware trial orchestration. Phase 6's narrow
  requirement (one file, audit-and-restore) is fully covered by a
  recursive copy + lock-by-hash patch.
- **`trial_delta_id` derivation:** the stable slug `trial:{target_path}`
  when no caller-supplied id is present. Keeps trial outcomes always
  carrying a non-null id when a patch was applied, so trajectories
  group cleanly even if upstream attribution is missing.
- **Bundling 06-02-04 with 06-02-02:** PLAN.md says "Add one
  integration test in `tests/test_trial_runner.py` that combines
  portfolio selection, one isolated trial, trajectory buffering, and
  belief update." It is a single integration test that lives in
  `tests/test_trial_runner.py`. The 06-02-04 acceptance gate is the
  combined-gate pytest invocation, which runs unchanged from any
  commit forward; reserving a separate commit just for one test
  function would split the natural unit. The 06-02-02 commit message
  records the integration test alongside the isolation tests.

## Deviations from Plan

None. Plan executed as written. The one bundling note above (task
06-02-04 integration test landed in the same commit as 06-02-02 because
the test file is `tests/test_trial_runner.py` per plan, and the
combined verification gate runs unchanged) is documented as a
decision, not a deviation: PLAN.md does not mandate one commit per
task and the per-task acceptance criteria all pass.

## What Stayed Fixed

- `workflow-skills/current/` — untouched. Verified by trial-runner
  tests after every patched run.
- `harness-runtime/` — untouched. D-23 boundary preserved.
- `seers_harness/tools/skill_tools.py` — untouched.
- `seers_harness/tools/evolution_tools.py` — untouched. The portfolio
  surface added here is consumed by handlers but the handler module
  did not need new fields.

## Handoff To Next Plans

- **06-03** (request-boundary integration + concurrency safety): can
  attach `run_request_trial` around `WorkflowRuntime.run_request` at
  the request/scenario boundary (D-16) and verify trajectory records
  do not cross-contaminate across concurrent requests by asserting
  unique `(request_id, artifact_paths)` tuples in the buffer.
- **06-04** (progress UX): can read `runtime.trace` and `outcome.success`
  / `outcome.trial_delta_id` for the "delta trial count" line.
- **06-05** (promotion public-entry smoke): can use the portfolio JSONL
  format (`load_portfolio_jsonl`) as the public artifact a
  promotion-chain dry-run reads.

## Self-Check: PASSED

- created files exist:
  - `seers_harness/evolution/trial_runner.py` — FOUND
  - `tests/test_delta_portfolio.py` — FOUND
  - `tests/test_trial_runner.py` — FOUND
  - `tests/test_trajectory_evidence.py` — FOUND
- modified files exist:
  - `seers_harness/evolution/__init__.py` — FOUND (exports new symbols)
  - `seers_harness/evolution/delta_portfolio.py` — FOUND (added I/O,
    posterior, selection, trajectory primitives)
- commits exist on branch `main`:
  - `600f2cb` — FOUND
  - `0faa7b3` — FOUND
  - `b3b1ecd` — FOUND
- focused gate: 42 passed
- full suite: 213 passed (171 baseline + 42 new)
