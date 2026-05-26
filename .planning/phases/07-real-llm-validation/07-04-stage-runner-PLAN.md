---
phase: 07-real-llm-validation
plan_id: 07-04
wave: 3
depends_on:
  - 07-01
  - 07-02
  - 07-03
files_modified:
  - seers_harness/validation/__init__.py
  - seers_harness/validation/runner.py
  - seers_harness/validation/exception_classifier.py
autonomous: true
requirements_addressed:
  - VAL-01
  - VAL-02
  - VAL-04
  - VAL-06
skills_used:
  - verification-before-completion
  - claude-api
  - error-analysis
  - systematic-debugging
  - eval-audit
  - dispatching-parallel-agents
  - gsd-verify-work
---

<objective>
Build the single CLI/test-runner that drives the canonical evidence batch end-to-end against real DeepSeek. The runner builds the (N, concurrency) matrix per D-01, swaps in the RecordingProvider around the existing `tests/smoke/scripted_full_chain` shape, runs N requests through the harness's chat → tool-call → reflow → trial pipeline, captures evidence per-node, writes index.json + batch_summary.json + evolution_snapshot.json, and exits non-zero on stage failure. Default invocation runs Stage 1 → Stage 2 → Stage 3 end-to-end automatically with no inter-stage human checkpoint (D-07); a `--stage` flag is preserved for retries after fixing a failure. Fail-fast at request level (D-02), max_retries=3 inside the provider only (D-03), no extra wrapper retry, no token cap (D-06). Trial isolation reuses `apply_delta_patch_temporarily` (D-21). Output writes to `.runs/<ts>/` git-ignored (D-09). D-19 trial-failure routing flows through exception_classifier. The Stage 3 stepping policy is decided in this plan (one-shot c=20 vs 4→8→20) — given Phase 6 PROD-02 confirmed DeepSeek tolerates the rate at c=20 for short bursts, we go one-shot c=20 (rationale recorded in the plan and the runner module docstring; D-04's rate-mask consequence is acknowledged in the same docstring).
</objective>

<must_haves>
  <truth>seers_harness/validation/runner.py exposes a CLI: `python -m seers_harness.validation.runner` (D-22a, D-22e).</truth>
  <truth>Default invocation (no flag) runs Stage 1 → Stage 2 → Stage 3 end-to-end automatically; if Stage N passes, Stage N+1 starts immediately with no human checkpoint (D-07).</truth>
  <truth>An optional `--stage {1|2|3}` flag runs only the named stage (used for retries after fixing a failure); not required for canonical end-to-end runs (D-22e planner discretion on entry-point/CLI shape).</truth>
  <truth>Stage 1 = (N=1, c=1); Stage 2 = (N=20, c=1); Stage 3 = (N=20, c=20) (D-01).</truth>
  <truth>Stage 1 passing is the only pre-flight gate before Stages 2/3: if Stage 1 fails the run stops and Stages 2/3 do not run; if Stage 1 passes the run continues automatically (D-05 read together with D-07).</truth>
  <truth>Stage 3 runs concurrency=20 one-shot (no 4→8→20 stepping). Rationale, anchored to Phase 6 PROD-02 rate-limit observations and acknowledging D-04's rate-mask consequence (per-request max_retries=3 × 20 concurrent = 60 retries of slack), is in the runner module docstring (D-22a, D-22e).</truth>
  <truth>The runner reuses the tests/smoke/scripted_full_chain shape (chat → tool-call → reflow → trial) — provider is swapped via dependency injection, no chain logic copy-pasted (D-22a).</truth>
  <truth>Trial isolation uses apply_delta_patch_temporarily — runner does not implement its own checkout-out machinery (D-21).</truth>
  <truth>All run output (index.json, batch_summary.json, evolution_snapshot.json, evidence/) writes under tests/smoke/.runs/&lt;timestamp&gt;/ which is git-ignored — no canonical run artifact enters the repo (D-09).</truth>
  <truth>Fail-fast: any unhandled non-trial exception during a request aborts the current stage and the overall run, surfacing a non-zero exit; per-request fails do not silently continue (D-02).</truth>
  <truth>No retry wrapper around the provider call — max_retries=3 is owned by the underlying OpenAICompatibleProvider only (D-03).</truth>
  <truth>No token cap on the request (D-06) — the provider sends whatever the harness assembles.</truth>
  <truth>D-19 trial-failure exception classification routes to exception_classifier.classify(exc) returning {trial_failure | infra_error | provider_error}; trial_failure is recorded in evolution_snapshot via the trial_runner hook from 07-01 and the host request continues; infra_error / provider_error fail-fast.</truth>
  <truth>After every stage finishes (success or fail-fast), the runner flushes evidence: per-node JSONL via flush_evidence (07-02), index.json + batch_summary.json (07-03), evolution_snapshot.json (07-01).</truth>
  <truth>Runner initialises delta_portfolio empty at process start; zero trials in Stage 1 / early Stage 2 is expected, not a fail-fast trigger (D-18).</truth>
</must_haves>

<tasks>

<task type="auto">
  <name>Task 1: Implement exception_classifier.py</name>
  <files>seers_harness/validation/exception_classifier.py</files>
  <read_first>
    - seers_harness/evolution/trial_runner.py (exception types raised by trials)
    - seers_harness/providers/openai_compatible.py (provider exceptions — read enough to enumerate)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-19 trial-failure routing)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (exception taxonomy)
  </read_first>
  <action>
    Create exception_classifier.py exporting classify(exc: BaseException) -> Literal["trial_failure", "infra_error", "provider_error"]. Routing:
    - trial_failure: any subclass of the trial-domain exceptions raised inside trial_runner (e.g. patch-apply errors, trial assertion failures) — recorded in evolution_snapshot but NOT fail-fast at the stage runner (the stage continues to the next request because trial outcomes are evidence, not infra failure) per D-19.
    - provider_error: HTTP / API errors from the provider (rate limits, auth, 5xx) — fail-fast.
    - infra_error: everything else (KeyError, AttributeError, FileNotFoundError, etc.) — fail-fast.
    Implement as isinstance checks against a small explicit allow-list. Default to "infra_error" — never silently absorb. Also export is_trial_failure(exc) -> bool for runner use.
  </action>
  <acceptance_criteria>
    - python -c "from seers_harness.validation.exception_classifier import classify, is_trial_failure" exits 0
    - python -c "from seers_harness.validation.exception_classifier import classify; assert classify(KeyError('x'))=='infra_error'" exits 0
    - grep -nE '"trial_failure"|"infra_error"|"provider_error"' seers_harness/validation/exception_classifier.py returns three or more lines
    - grep -nE "isinstance" seers_harness/validation/exception_classifier.py returns at least one line
  </acceptance_criteria>
  <done>classify() returns one of three labels for any exception, with trial failures isolated from infra/provider failures per D-19.</done>
</task>

<task type="auto">
  <name>Task 2: Implement runner.py CLI and stage matrix</name>
  <files>seers_harness/validation/runner.py</files>
  <read_first>
    - tests/smoke/scripted_full_chain (or the equivalent smoke fixture / module — locate and read)
    - seers_harness/validation/recording_provider.py (07-02)
    - seers_harness/validation/evidence_writer.py (07-02)
    - seers_harness/validation/index_writer.py (07-03)
    - seers_harness/validation/batch_summary_writer.py (07-03)
    - seers_harness/validation/evolution_snapshot.py (07-01)
    - seers_harness/validation/exception_classifier.py (Task 1)
    - seers_harness/evolution/trial_runner.py (apply_delta_patch_temporarily import, hook param shape from 07-01)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-01 stage matrix, D-02 fail-fast, D-03 max_retries=3 owned by provider, D-04 rate-mask consequence to acknowledge in docstring, D-05 stage-1-as-only-gate, D-06 no token cap, D-07 no inter-stage human checkpoint, D-09 .runs/&lt;ts&gt;/ git-ignored, D-18 portfolio-starts-empty, D-19 trial-failure routing, D-21 trial isolation, D-22a/e planner discretion)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (runner skeleton)
    - .planning/phases/06-*/06-CONTEXT.md (PROD-02 rate-limit facts — for the Stage 3 stepping rationale)
  </read_first>
  <action>
    Create runner.py with module-level docstring documenting (1) the Stage 3 stepping decision: "Stage 3 runs concurrency=20 one-shot rather than stepping 4→8→20. Rationale: Phase 6 PROD-02 confirmed DeepSeek tolerates a 20-request burst at the harness's per-request payload size; stepping would consume budget without surfacing a different failure mode. Stepping is reintroduced only if a Stage 3 run fails-fast on rate-limit before completion."; and (2) the D-04 acknowledgement: "Stage 3 may mask real concurrency-induced rate ceilings because per-request max_retries=3 × 20 concurrent = 60 retries of slack collectively. This is observation, not stabilisation (D-04)."
    Implement main() with argparse. CLI shape: `python -m seers_harness.validation.runner [--stage {1,2,3}] [--out-dir PATH]`. `--stage` is OPTIONAL; default behaviour (no flag) runs Stage 1 → Stage 2 → Stage 3 in a single invocation (D-07). When `--stage` is provided, run only that stage (used for retries after fixing a failure). `--out-dir` default tests/smoke/.runs/&lt;utc_timestamp&gt;/ (D-09).
    Stage matrix: stage_config = {1:(1,1), 2:(20,1), 3:(20,20)} (D-01). Build the canonical request set from the same fixture tests/smoke/scripted_full_chain consumes (import, do not duplicate). Construct an OpenAICompatibleProvider configured for DeepSeek (read endpoint/api-key from env, max_retries=3 set on the provider only — D-03), wrap in RecordingProvider with a shared request_log list. Initialise delta_portfolio EMPTY at process start (D-18) — zero trials in Stage 1 / early Stage 2 is expected and never a fail-fast trigger. Construct an evolution events list. Inject the recording provider into the chain shape (the dependency-injection seam already exists in scripted_full_chain — use it; if it does not exist, surface a clear ImportError rather than monkey-patching).
    For each of N requests in a stage: stamp set_current_node_id(f"req_{i:04d}"), run the chain in a thread/asyncio task pool with the configured concurrency. On exception call classify(exc): if is_trial_failure(exc) the trial_runner hook already recorded it, host request continues (D-19 — trial outcomes are evidence, not stage-aborting infra failure); otherwise re-raise (fail-fast at request level — D-02). NO per-request retry wrapper (D-03 — provider owns max_retries=3 alone). NO token cap (D-06).
    Stage progression: run Stage 1 first; on success, automatically continue to Stage 2 with no human checkpoint (D-07); on Stage 2 success, automatically continue to Stage 3 (D-07). On any non-trial exception in any stage, fail-fast: stop the run, exit non-zero, do NOT advance to the next stage (D-02 + D-05). When invoked with explicit `--stage N`, run only stage N and exit (used to resume after fixing a failure).
    After each stage completes (success or fail-fast finally:), flush_evidence(request_log, out_dir / "evidence"), write_index(records=[...], out_dir, stage, batch_id=&lt;ts&gt;, started_at, finished_at, n, concurrency), write_batch_summary(out_dir/"index.json"), write_evolution_snapshot(events, out_dir/"evolution_snapshot.json"). Trial isolation: any code path that needs to swap deltas calls apply_delta_patch_temporarily — runner does not reimplement (D-21). Add `if __name__ == "__main__": sys.exit(main())`.
  </action>
  <acceptance_criteria>
    - test -f seers_harness/validation/runner.py returns 0
    - python -m seers_harness.validation.runner --help exits 0
    - python -m seers_harness.validation.runner --help output includes "--stage" and "{1,2,3}"
    - The `--stage` argument is OPTIONAL — verify by reading argparse setup and confirming `required=False` (or no `required=True`); default invocation must run all three stages
    - grep -nE "stage_config|\\(1, ?1\\)|\\(20, ?1\\)|\\(20, ?20\\)" seers_harness/validation/runner.py returns matches covering all three stages
    - grep -nE "apply_delta_patch_temporarily" seers_harness/validation/runner.py returns at least one line
    - grep -nE "classify\\(" seers_harness/validation/runner.py returns at least one line
    - grep -nE "max_retries|retry" seers_harness/validation/runner.py | grep -v '^[^:]*:[[:space:]]*#' returns 0 lines (no wrapper retry — comments allowed; max_retries=3 lives on provider construction only)
    - grep -nE "max_tokens" seers_harness/validation/runner.py | grep -v '^[^:]*:[[:space:]]*#' returns 0 lines (no token cap — D-06)
    - The module docstring contains the Stage 3 one-shot rationale referencing PROD-02 (grep -nE "PROD-02|one-shot|stepping" seers_harness/validation/runner.py returns at least one line)
    - The module docstring acknowledges D-04 rate-mask consequence (grep -nE "D-04|rate ceiling|rate-mask|60 retries" seers_harness/validation/runner.py returns at least one line)
    - The runner does NOT print a "Stage 1 complete — re-invoke with --stage 2" pause message — verify: grep -nE "re-invoke with --stage 2|review .runs|Stage 1 complete — review" seers_harness/validation/runner.py returns 0 lines (D-07 — no inter-stage human checkpoint)
    - The runner advances Stage 1 → Stage 2 → Stage 3 automatically on success — verify the default-invocation control flow by reading
    - The runner initialises delta_portfolio empty at process start — grep -nE "delta_portfolio|portfolio.*empty|empty.*portfolio" seers_harness/validation/runner.py returns at least one line, and a comment cites D-18
  </acceptance_criteria>
  <done>The CLI runner drives all three stages end-to-end in a single default invocation with the correct (N, c) matrices, reuses the smoke chain via injection, classifies trial failures per D-19, fails fast on infra/provider errors per D-02, advances stages automatically per D-07, and produces the full evidence artifact set under .runs/&lt;ts&gt;/ per D-09.</done>
</task>

</tasks>

<verification>
  - python -c "from seers_harness.validation.runner import main" exits 0
  - python -m seers_harness.validation.runner --help exits 0
  - The runner imports (does not duplicate) the tests/smoke/scripted_full_chain shape
  - The Stage 3 stepping decision (one-shot c=20) is documented in the runner module docstring with PROD-02 reference and D-04 rate-mask acknowledgement
  - autonomous: true is consistent with the absence of any inter-stage human checkpoint (D-07)
</verification>
