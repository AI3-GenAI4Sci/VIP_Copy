---
status: partial
phase: 07
plan_id: 07-06
subsystem: validation
tags: [real-llm-execution, evidence, fail-fast, d-02, d-07, d-09, d-18, d-19]

# Dependency graph
requires:
  - phase: 07-real-llm-validation
    plan: 07-04
    provides: seers_harness.validation.runner CLI + exception_classifier (D-19 router)
  - phase: 07-real-llm-validation
    plan: 07-03
    provides: index.json / batch_summary.json writers
  - phase: 07-real-llm-validation
    plan: 07-02
    provides: RecordingProvider + flush_evidence
  - phase: 07-real-llm-validation
    plan: 07-01
    provides: write_evolution_snapshot + evolution observability events shape
  - phase: 07-real-llm-validation
    plan: 07-05
    provides: case_analysis.md skeleton (downstream case-reading target)
provides:
  - .planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md (Stage 1 fail-fast evidence record)
affects: [07-end (downstream verifier; case_analysis.md remains unpopulated until a successful run)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-fast partial-artifact preservation pattern — Stage 1 produced index.json, batch_summary.json, evolution_snapshot.json on disk despite the very first provider call returning 401, confirming the runner's `finally`-flush contract from 07-04."
    - "Exception cause chain attestation pattern — when a provider exception is wrapped by `dag_runner` before reaching `classify`, the on-disk classification under-reports the real cause; the EXECUTION-LOG records the full cause chain so downstream auditors can recover the truth without re-running."

key-files:
  created:
    - .planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md
  modified: []
  untracked:
    - tests/smoke/.runs/20260526T114136Z/ (Stage 1 partial artifacts; git-ignored per D-09; local-only)

key-decisions:
  - "Honor D-02 — Stage 1 fail-fasted on the first request (`infra_error` per D-19 routing of the wrapped `RuntimeError`); the runner correctly returned exit code 1 and DID NOT advance to Stage 2 or Stage 3."
  - "Honor D-07 — the run was a single CLI invocation with no inter-stage human checkpoint; Stage 1 failure stopped the run cleanly without prompting the user mid-stage."
  - "Honor D-09 — all artifacts under tests/smoke/.runs/20260526T114136Z/ are git-ignored; nothing was force-staged; the only file that entered the repo is .planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md (the audit artifact)."
  - "Honor D-13 / D-14 — VAL-03 / VAL-05 / VAL-06 verdicts are deferred to manual case-reading in case_analysis.md and are NOT recorded in the execution log. (They are structurally impossible to record from a 0-successful-request run anyway.)"
  - "Honor D-17 / D-18 — evolution_snapshot.json was written for the single Stage 1 request with `delta_portfolio_before=[]`, `delta_portfolio_after=[]`, `trials=[]`. Zero trials is recorded as expected, NOT as a VAL-06 failure."
  - "Honor D-19 — the runner classified the wrapped exception (`RuntimeError: Node factor_discovery failed after 1 attempts`) as `infra_error` because `RuntimeError` is not in the explicit allow-list; the deeper `ProviderAuthError` cause was preserved in the EXECUTION-LOG cause chain for auditors. This is the conservative, never-silently-absorb behaviour 07-04 contracted for."
  - "Honor D-22 — no runner mechanics were modified in this plan; no wrapper retry was added; no provider was swapped to a fake; no `harness-runtime/` files were touched. The plan's job was to *run* the canonical batch and *record what happened* — not to repair the upstream environment."

patterns-established:
  - "Pattern: fail-fast logged with full cause chain — when classify() under-reports the real cause due to upstream wrapping, the EXECUTION-LOG carries both the classified label (for machine consumption) and the full cause chain (for human auditors)."
  - "Pattern: empty manual_review_queue on zero-success runs — when no request produces a valid artifact, the queue is intentionally empty rather than fabricated; case_analysis.md remains a stub until real evidence exists."

requirements-completed: []
requirements-deferred: [VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06]

# Metrics
duration: ~3min (read-context, single-shot run that fail-fasted in 1s, log + summary)
completed: 2026-05-26
---

# Phase 07 Plan 07-06: Real-LLM Execution and Evidence — Summary (PARTIAL)

**Single default invocation `python -m seers_harness.validation.runner` was launched against real DeepSeek; Stage 1 (N=1, c=1) fail-fasted on the very first request with a 401 `Authentication Fails, Your api key: ****92c7 is invalid`; per D-02 the runner correctly stopped without advancing to Stage 2 or Stage 3 and returned exit code 1; partial canonical artifacts (index.json + batch_summary.json + evolution_snapshot.json) are on disk under git-ignored `tests/smoke/.runs/20260526T114136Z/`; per-node `evidence/<node_id>/` JSONLs were not produced because the failure occurred before any provider call returned a payload to record. VAL-01..06 verdicts could not be recorded — VAL-01/02/04 read as zero-pass for the single executed request, and VAL-03/05/06 are structurally impossible to read without successful artifacts. The plan's mechanics (D-01 stage matrix, D-02 fail-fast, D-07 no inter-stage checkpoint, D-09 git-ignored output, D-18 empty-portfolio expected, D-19 classifier behaviour) all behaved exactly as specified by 07-04.**

## Performance

- **Duration:** ~3 min (orchestration + context-read + 1-second run + log/summary)
- **Run wall-clock:** 1 second (Stage 1 fail-fast)
- **Started:** 2026-05-26T11:41:36Z
- **Completed:** 2026-05-26
- **Tasks:** 1 / 2 (Task 1 pre-flight checkpoint cleared by user input "a"; Task 2 executed but did not satisfy its full acceptance criteria due to the upstream auth failure)
- **Files created:** 1; **Files modified:** 0; **Untracked (local-only per D-09):** 1 directory

## Accomplishments

- Single-invocation execution confirmed end-to-end behaviour through Stage 1: the runner imports cleanly, reads `DEEPSEEK_API_KEY` from the environment, builds the scratch CSV from `data_100k.csv`, drives the 3-node DAG against real DeepSeek, classifies the failure via D-19 routing, writes `index.json` + `batch_summary.json` + `evolution_snapshot.json` per-stage even on the fail-fast path, and exits non-zero. This is **all** of the runner's plumbing exercised against the real provider in one shot.
- D-19 classifier behaviour validated under a real DeepSeek auth failure: the wrapped `RuntimeError` from `dag_runner` correctly fell through to the `infra_error` default rather than being silently absorbed, AND the underlying `ProviderAuthError` is preserved in the cause chain captured in `07-EXECUTION-LOG.md` so auditors can recover the true cause without re-running.
- D-18 empty-portfolio behaviour validated under a real run: `evolution_snapshot.json` carries `delta_portfolio_before=[]`, `delta_portfolio_after=[]`, `trials=[]` exactly as the contract requires for Stage 1; zero trials is logged as expected, not flagged as a failure.
- D-02 partial-artifacts-on-disk behaviour validated: even though the first request raised before producing a usable artifact, the per-stage finally block successfully flushed `index.json` and `batch_summary.json` with the failed row recorded under `fail_lists.{VAL-01,VAL-02,VAL-04}` and an `exception` field on the request row.
- D-07 no-inter-stage-checkpoint behaviour validated: the run terminated cleanly via `return 1` from `run()` without any "review .runs/ then re-invoke" pause prompt; the only human interaction in this plan was the pre-stage Task 1 pre-flight (cleared via the orchestrator's "a" → "go" mapping, per the orchestrator's instruction that the checkpoint is approved).
- `.planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md` captures the full cause chain plus the resume instruction (`python -m seers_harness.validation.runner --stage 1` after rotating the rejected key) so downstream agents and the user can pick up cleanly.

## Notable deviations

- **Stage 1 fail-fasted on a 401 from DeepSeek (`****92c7 is invalid`).** The plan's "happy-path" must_have ("full canonical artifact tree across all three stages") was therefore not satisfied. This is **not a runner defect** — the runner's behaviour was correct under D-02 — it is a real-world environmental fact that the API key currently in the shell was rejected by DeepSeek. Per orchestrator instruction this plan does NOT attempt to "fix" the auth (no fallback to a fake provider, no re-attempt with a different key, no wrapper retry layer added).
- **Exception classified as `infra_error` rather than `provider_error`.** The runner classified the `RuntimeError` it received from `dag_runner` (which wraps the original `ProviderAuthError`) as `infra_error` because `RuntimeError` is not in the D-19 allow-list. Per the 07-04 classifier contract, this is the correct conservative behaviour ("never silently absorb"); the EXECUTION-LOG documents the deeper cause for human review. **A future enhancement** could let `classify` traverse `__cause__` to surface the underlying `ProviderAuthError`, but per D-19 ("classification is by exception class only, never the message string, never the cause chain") this is explicitly out of scope here. Tagged as a deferred review point, not a fix.
- **Per-node `evidence/<node_id>/{messages.jsonl, tool_calls.jsonl, artifact.json, usage.json}` were NOT produced.** Because the very first provider call returned 401 before any payload reached `RecordingProvider`, the request's `request_log` was empty when `flush_evidence` ran in `_run_one_request`'s finally block. This is consistent with the writer's degradation rule (an empty log produces no JSONL files) — it is the documented behaviour, not a bug.

## Issues Encountered

| Severity | Issue | Action |
|---|---|---|
| BLOCKING | DeepSeek 401 on the API key whose suffix is `****92c7` | Documented in `07-EXECUTION-LOG.md`; user must rotate / verify the key, then re-run with `python -m seers_harness.validation.runner --stage 1` (single-stage retry per the runner's CLI contract). |
| OBSERVATION | `classify()` reported `infra_error` for a true provider auth failure because `dag_runner` wraps the cause | Documented as a deferred review point in `07-EXECUTION-LOG.md`; **NOT** patched in this plan because doing so would violate D-19's "classification by exception class only" contract. |

## Self-Check: PARTIAL

- Exit code: 1 (Stage 1 fail-fast — expected behaviour given the upstream 401)
- `.planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md` was written and committed (`692b0ae`).
- Only ONE file entered the git index from this plan (the EXECUTION-LOG); the `.runs/` tree is correctly untracked.
- `must_haves` audit (from the plan):
  - **Canonical artifact tree under `.runs/<ts>/`:** PARTIAL — Stage 1 only.
  - **Single CLI invocation, end-to-end Stages 1 → 2 → 3:** PARTIAL — invoked exactly once (CONFIRMED), but Stages 2/3 not started (CORRECT per D-02).
  - **Stage subdirs with index.json + batch_summary.json:** CONFIRMED for Stage 1.
  - **`batch_summary.json` totals + fail_lists:** CONFIRMED.
  - **`evolution_snapshot.json` keys present:** CONFIRMED.
  - **Zero trials in Stage 1 logged as expected:** CONFIRMED.
  - **Fail-fast at request level with exception class recorded:** CONFIRMED.
  - **Case analysis NOT performed:** CONFIRMED.

The plan is marked **PARTIAL** because the upstream 401 prevented a successful end-to-end three-stage run; the plan's runner-mechanics objectives all behaved correctly (every D-* anchor it claimed to validate held under fire), and the upstream block is honestly recorded for the user to resolve and re-run.

## Resume / Next Steps

1. The user (or operator) verifies / rotates the DeepSeek API key — the rejected suffix is `****92c7`.
2. Re-run **Stage 1 only** as a bring-up: `python -m seers_harness.validation.runner --stage 1`.
3. If Stage 1 passes, re-run the full pipeline: `python -m seers_harness.validation.runner` (no `--stage` flag — drives Stages 1 → 2 → 3 end-to-end).
4. After a successful real-DeepSeek run, the user populates `.planning/phases/07-real-llm-validation/case_analysis.md` per D-13 / D-14 / D-15 / D-16 — that step lives outside execute-phase.

---
*Phase: 07-real-llm-validation*
*Plan: 07-06 real-llm-execution-and-evidence*
*Status: PARTIAL — Stage 1 fail-fast on upstream 401; runner mechanics validated; awaiting key rotation + re-run before VAL-01..06 verdicts can be read.*
*Completed: 2026-05-26*
