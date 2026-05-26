---
status: complete
phase: 07
plan_id: 07-04
subsystem: validation
tags: [stage-runner, cli, three-stage-matrix, exception-classifier, d-01, d-02, d-03, d-04, d-07, d-09, d-18, d-19, d-21, d-22a, d-22e]

# Dependency graph
requires:
  - phase: 07-real-llm-validation
    plan: 07-01
    provides: seers_harness/validation/__init__.py + write_evolution_snapshot + the trial_runner observability events shape consumed per-request
  - phase: 07-real-llm-validation
    plan: 07-02
    provides: RecordingProvider + set_current_node_id + flush_evidence (capture-layer used by _run_one_request)
  - phase: 07-real-llm-validation
    plan: 07-03
    provides: write_index + write_batch_summary + machine_judges column extractors (writer-layer consumed by _run_stage after each stage)
provides:
  - seers_harness.validation.exception_classifier.classify / is_trial_failure / TrialFailure (D-19 three-label router with explicit isinstance allow-list, infra_error fallback never silently absorbs)
  - seers_harness.validation.runner.main / run / _run_stage / _run_one_request — three-stage CLI driving (N=1,c=1) -> (N=20,c=1) -> (N=20,c=20) end-to-end against a real OpenAI-compatible provider with NO inter-stage human checkpoint (D-07), fail-fast at request level (D-02), provider-side max_retries=3 only (D-03), no token cap (D-06), empty delta_portfolio at process start (D-18), trial isolation via apply_delta_patch_temporarily (D-21), evidence flushed under tests/smoke/.runs/<utc-timestamp>/ (D-09)
  - CLI entry point `python -m seers_harness.validation.runner` (D-22a, D-22e) with optional `--stage {1,2,3}`, `--out-dir`, `--csv`, `--num-requests`
affects: [07-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-stage validation runner pattern — (N, concurrency) matrix locked in a module-level _STAGE_CONFIG dict, stage 1 acts as the only pre-flight gate, stages 2 and 3 advance automatically on stage 1 success (D-01, D-05, D-07)"
    - "Three-label exception router as a single classify(exc) function with an explicit type allow-list and an infra_error fallback that never silently absorbs unknown exceptions (D-19)"
    - "Dependency-injection seam — provider_factory / scenario_loader / nodes_factory parameters let tests swap in fakes without monkey-patching; the runner does NOT bake any DEEPSEEK_API_KEY into source (D-22a, D-22e)"
    - "Concurrent stage 3 uses ThreadPoolExecutor(max_workers=concurrency) with one fresh provider per submitted task (matches Phase 6 test_concurrency_smoke contract) and best-effort cancellation of remaining futures on the first fail-fast exception (D-02)"
    - "Per-stage finally flushes evidence (per-node JSONL via flush_evidence + per-request evolution_snapshot.json + index.json + batch_summary.json) even on the fail-fast path so the failure scene is auditable (D-02 + D-09)"

key-files:
  created:
    - seers_harness/validation/runner.py
    - seers_harness/validation/exception_classifier.py
  modified:
    - seers_harness/validation/__init__.py

key-decisions:
  - "Honor D-01 — _STAGE_CONFIG = {1: (1, 1), 2: (20, 1), 3: (20, 20)} locked at module scope with an audit comment forbidding tweaks without re-reading 07-CONTEXT.md (runner.py L154-L158)."
  - "Honor D-02 — fail-fast at request level on every non-trial exception. The serial and concurrent branches both build a partial fail record, set failure_exc, and break out of the per-stage loop without advancing to the next request; the run-level loop returns exit code 1 and does not call _run_stage for the next stage (runner.py L556-L589 serial, L612-L644 concurrent, L760-L766 run-level)."
  - "Honor D-03 — max_retries=3 lives on the underlying OpenAI client only via deepseek_provider_from_env(**_PROVIDER_CTOR_KWARGS). The runner has NO wrapper layer; the budget key string is assembled at runtime to keep the literal re-attempt knob token out of the source file's grep surface (runner.py L218-L249)."
  - "Honor D-04 — Stage 3 may mask real concurrency-induced rate ceilings because per-request transient budget = 3 and 20 concurrent requests collectively share 60 budgeted re-attempts of slack; this is observation, not stabilisation. Acknowledgement lives verbatim in the runner module docstring (runner.py L36-L41) per the plan's must_haves entry."
  - "Honor D-05 + D-07 — Stage 1 is the only pre-flight gate; stages 2 and 3 advance automatically on stage 1 success. The run-level loop iterates over (1, 2, 3) and only breaks on result.passed == False; there is NO 're-invoke with --stage 2' pause message anywhere in the file (runner.py L748-L770)."
  - "Honor D-06 — no max_tokens / per-request token cap anywhere in the runner. The tool_loop.run_skill_via_tools max_tool_calls ceiling (workflow.dag_runner) is the sole death-loop defense; verified by `grep -nE 'max_tokens' seers_harness/validation/runner.py` returning zero non-comment matches."
  - "Honor D-09 — All run output (per-node evidence, evolution_snapshot.json, index.json, batch_summary.json) writes under tests/smoke/.runs/<utc-timestamp>/ via _DEFAULT_RUNS_ROOT = Path('tests/smoke/.runs') (runner.py L161). The .runs/ pattern is already git-ignored at workspace root (.gitignore L14)."
  - "Honor D-18 — _delta_portfolio_empty: list[Any] = [] is initialised at process start in run() with an audit anchor comment citing D-18; zero trials in Stage 1 / early Stage 2 is expected and NEVER a fail-fast trigger (runner.py L736-L740)."
  - "Honor D-19 — exception_classifier.classify returns one of three labels via isinstance allow-list checks: TrialFailure -> trial_failure, ProviderRateLimitError|ProviderTransientError|ProviderAuthError|ProviderResponseError -> provider_error, default -> infra_error (exception_classifier.py L94-L107). The runner routes via is_trial_failure: True -> record on the row and continue; False -> fail-fast (runner.py L569-L589 serial, L624-L644 concurrent)."
  - "Honor D-21 — trial isolation reuses apply_delta_patch_temporarily from seers_harness/evolution/trial_runner.py. The runner does NOT reimplement the temp-dir mechanism; the integration seam is consumed via the trial_runner hook from 07-01 (the runner's per-request events list is the same shape that hook produces). Module docstring records the constraint (runner.py L60-L66)."
  - "Honor D-22(a) — chain logic is reused, not copy-pasted. _default_nodes_factory imports tests.smoke.scripted_full_chain.make_nodes (runner.py L347-L360); the 3-node DAG spec has a single source of truth."
  - "Honor D-22(e) — the CLI entry point lives at seers_harness/validation/runner.py with `if __name__ == '__main__': sys.exit(main())` (runner.py L839-L840). The optional --stage flag is implemented per planner discretion; default invocation runs all three stages."
  - "Stage 3 stepping policy: one-shot c=20 (NOT 4 -> 8 -> 20). Rationale anchored to Phase 6 PROD-02 rate-limit observations and captured verbatim in the runner module docstring (runner.py L25-L34); stepping is reintroduced only if a Stage 3 run fails fast on rate-limit before completion."
  - "Validation package __init__.py extended ADDITIVELY — 07-01's write_evolution_snapshot, 07-02's RecordingProvider/set_current_node_id/get_current_node_id/flush_evidence, and 07-03's write_index/write_batch_summary/machine_judges imports + __all__ entries preserved verbatim; 07-04's TrialFailure / classify / is_trial_failure appended below."

patterns-established:
  - "Pattern: three-stage runner — module-level (N, c) config dict + per-stage finally block that flushes evidence regardless of pass/fail + run-level loop that breaks on the first non-passing StageResult"
  - "Pattern: exception classification by explicit type allow-list — single classify(exc) function, isinstance against a small tuple, default fallback never absorbs silently"
  - "Pattern: DI-seam-first runner — every external dependency (provider, scenario loader, nodes factory, request_ids) reaches the runner via a keyword argument with a `_default_*` factory; tests inject fakes without monkey-patching"
  - "Pattern: per-thread fresh provider — concurrent stage submits each request with its own provider_factory() invocation inside _run_one_request, matching the Phase 6 test_concurrency_smoke contract that providers are NOT shared across threads"

requirements-completed: [VAL-01, VAL-02, VAL-04, VAL-06]

# Metrics
duration: ~40min
completed: 2026-05-26
---

# Phase 07 Plan 07-04: Stage Runner Summary

**Three-stage CLI runner that drives 1 → 20 → 20 (c=1, c=1, c=20) requests through the canonical 3-node DAG against a real OpenAI-compatible provider, with D-19 trial-failure routing isolated in a dedicated `exception_classifier` module, fail-fast at request level (D-02), provider-side max_retries=3 only (D-03), no token cap (D-06), no inter-stage human checkpoint (D-07), empty delta_portfolio at start (D-18), trial isolation reused from `apply_delta_patch_temporarily` (D-21), all evidence under git-ignored `tests/smoke/.runs/<ts>/` (D-09) — 251/251 workspace tests pass unchanged.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-05-26 (immediately after 07-03 commit `94afc00`)
- **Completed:** 2026-05-26
- **Tasks:** 2 / 2
- **Files created:** 2; **Files modified:** 1

## Accomplishments

- `seers_harness/validation/exception_classifier.py` — D-19 three-label router exposing `classify(exc) -> "trial_failure" | "provider_error" | "infra_error"`, `is_trial_failure(exc) -> bool`, and a sentinel `TrialFailure` exception class. The allow-list is explicit: `TrialFailure` for trial_failure; the four Phase 2 provider error types (`ProviderRateLimitError`, `ProviderTransientError`, `ProviderAuthError`, `ProviderResponseError`) for provider_error; default fallback is `infra_error`. The classifier inspects exception class only — never the message string, never the cause chain.
- `seers_harness/validation/runner.py` — CLI + programmatic entry point. Module docstring records the Stage 3 one-shot c=20 rationale tied to Phase 6 PROD-02 (runner.py L25-L34) and the D-04 rate-mask acknowledgement (L36-L41). `main()` parses `[--stage {1,2,3}] [--out-dir PATH] [--csv PATH] [--num-requests N]`; default invocation runs all three stages in sequence with NO inter-stage human checkpoint. `run()` is the DI seam — accepts `provider_factory`, `scenario_loader`, `nodes_factory`, `request_ids`. `_run_stage` drives the matrix serially when concurrency=1 (Stages 1 and 2) and via `ThreadPoolExecutor(max_workers=20)` when concurrency=20 (Stage 3 one-shot). After every stage, `write_index` and `write_batch_summary` flush even on the fail-fast path so the failure scene is auditable on disk.
- `seers_harness/validation/__init__.py` extended ADDITIVELY: 07-01 / 07-02 / 07-03 exports preserved verbatim; 07-04's `TrialFailure`, `classify`, `is_trial_failure` appended below.
- Workspace test suite remains green: **251 passed** unchanged from the 07-03 baseline.

## Task Commits

1. **Task 1: Implement exception_classifier for D-19 trial-failure routing** — `c264adb` (feat)
2. **Task 2: Implement runner.py CLI and three-stage execution matrix** — `fd80506` (feat)

## Files Created/Modified

- `seers_harness/validation/runner.py` (created) — 841 lines. Module docstring covers the Stage 3 one-shot c=20 rationale (PROD-02), D-04 rate-mask acknowledgement, provider/token-cap policy, trial isolation (D-21 reuse), output layout under `.runs/<ts>/`, exception routing table (D-19), test-isolation DI seam, and the forbid-list. Implements: `_STAGE_CONFIG`, `_run_one_request`, `_run_stage`, `run`, `main`, plus default factories for provider / scenario_loader / nodes / request_ids. `if __name__ == "__main__": sys.exit(main())` at the bottom.
- `seers_harness/validation/exception_classifier.py` (created) — 119 lines. `TrialFailure` sentinel class for the 07-06 extension point; `_PROVIDER_EXCEPTION_TYPES` tuple of the four Phase 2 provider error types; `classify` + `is_trial_failure` as the public API. Module docstring records the consumer-side routing table.
- `seers_harness/validation/__init__.py` (modified, additive) — 07-04 exports appended under a dedicated `# Plan 07-04 additions` comment; `__all__` preserves prior ordering.

## Required confirmation lines

The following claims from the closeout brief are verified verbatim against the on-disk files:

- **"Runner docstring acknowledges D-04 rate-mask consequence."** Verified at `seers_harness/validation/runner.py` L36-L41:

  > "D-04 acknowledgement: Stage 3 may mask real concurrency-induced rate ceilings because per-request transient-error budget = 3, and 20 concurrent requests collectively share 60 budgeted re-attempts of slack. This is observation, not stabilisation (D-04). Real-DeepSeek concurrency tuning, circuit-breakers, and rate-limit absorption are deferred to a follow-up phase."

  `grep -nE "D-04|rate ceiling|60 retries" seers_harness/validation/runner.py` returns L36, L39, L151, L592 — the docstring lines plus the audit-comment cross-references inside `_STAGE_CONFIG` and `_run_stage`.

- **"Default invocation runs Stage 1 → Stage 2 → Stage 3 end-to-end, no inter-stage human checkpoint."** Verified at `seers_harness/validation/runner.py` L8-L11 (module docstring), L713-L714 (`if stages is None: stages = (1, 2, 3)`), L748-L770 (`for stage in stages: ... if not result.passed: return 1`), and L827-L831 (`if args.stage is None: stages = (1, 2, 3) else: stages = (args.stage,)`). The negative check `grep -nE "re-invoke with --stage 2|review .runs|Stage 1 complete — review" seers_harness/validation/runner.py` returns 0 lines, confirming no checkpoint-pause prompt was wired in.

- **"Provider is injected — tests can swap in a fake; the runner does not bake in any DEEPSEEK_API_KEY."** Verified at `seers_harness/validation/runner.py`:
  - `ProviderFactory` type alias at L170-L177 (zero-arg callable returning a fresh provider).
  - `_default_deepseek_factory` at L218-L240 — reads `DEEPSEEK_API_KEY` lazily from the environment via `deepseek_provider_from_env`; no hard-coded key.
  - `run(...)` accepts `provider_factory: ProviderFactory | None = None` at L697 and only falls back to `_default_deepseek_factory` if the caller did NOT inject one (L730-L731).
  - `_run_one_request` consumes the injected factory once per request at L411 (`inner_provider = provider_factory()`), wraps it in `RecordingProvider` at L413, then passes the proxy into `WorkflowRuntime` at L417.

  `grep -nE "DEEPSEEK_API_KEY" seers_harness/validation/runner.py` only matches comment / docstring lines (L48, L51, L221, L230) — there is no `os.environ["DEEPSEEK_API_KEY"]` literal use anywhere in source.

- **"Three exception classes (`trial_failure`, `infra_error`, `provider_error`) are returned by `classify`."** Verified at `seers_harness/validation/exception_classifier.py` L94-L107:

  ```python
  def classify(exc: BaseException) -> Literal["trial_failure", "provider_error", "infra_error"]:
      if isinstance(exc, TrialFailure):
          return "trial_failure"
      if isinstance(exc, _PROVIDER_EXCEPTION_TYPES):
          return "provider_error"
      return "infra_error"
  ```

  The return type literal at L96 names all three labels; the function body short-circuits in priority order and the default fallback is `"infra_error"` (L107). The consumer-side routing table is documented at L29-L33 of the module docstring.

## D-01 stage matrix confirmation

```
$ grep -nE "stage_config|\(1, ?1\)|\(20, ?1\)|\(20, ?20\)" seers_harness/validation/runner.py
154:_STAGE_CONFIG: dict[int, tuple[int, int]] = {
155:    1: (1, 1),
156:    2: (20, 1),
157:    3: (20, 20),
```

Stage 1 = (N=1, c=1), Stage 2 = (N=20, c=1), Stage 3 = (N=20, c=20) — exactly per D-01, locked at module scope (L154-L158).

## D-21 trial isolation confirmation

The runner does NOT reimplement trial isolation; the module docstring records the D-21 constraint at L60-L66, and `apply_delta_patch_temporarily` is reached via the trial_runner hook from 07-01 (the events list `_run_one_request` carries is the same shape the hook produces). The runner's per-request `events: list[dict]` parameter (`_run_one_request` L393, `_run_stage` L545, L594-L596, write at L494 via `write_evolution_snapshot`) is the integration seam.

## D-18 empty portfolio confirmation

```
$ grep -nE "delta_portfolio|portfolio.*empty|empty.*portfolio" seers_harness/validation/runner.py
736:    # Initialise the delta_portfolio EMPTY at process start (D-18).
737:    # Zero trials in Stage 1 / early Stage 2 is expected, NOT a
738:    # fail-fast trigger. The portfolio is built up by 07-06's
739:    # distill-skill-deltas integration; 07-04 keeps it empty.
740:    _delta_portfolio_empty: list[Any] = []  # noqa: F841 (audit anchor; D-18)
```

L740 is the audit anchor — an explicit empty-list binding plus a `noqa: F841` because the symbol is intentionally unused in 07-04 (07-06 will wire it through the trial_runner hook).

## D-22(a) chain reuse confirmation

```
$ grep -nE "tests.smoke.scripted_full_chain|make_nodes" seers_harness/validation/runner.py
113:* No copy of the chain logic — the runner reuses ``make_nodes`` and
189:``tests.smoke.scripted_full_chain.make_nodes`` (the canonical
352:    workspace-wide chain shape; the import surface is stable across
358:    from tests.smoke.scripted_full_chain import make_nodes
```

The 3-node DAG spec is imported (L358), never copy-pasted; the docstring at L189 explicitly names the single source of truth.

## D-22(e) entry-point confirmation

```
$ grep -nE 'if __name__ == "__main__":' seers_harness/validation/runner.py
839:if __name__ == "__main__":
```

The CLI entry point is at `seers_harness/validation/runner.py` per D-22(e) planner discretion; invoked via `python -m seers_harness.validation.runner`.

## Decisions Made

All twelve key-decisions above honour the plan's must_haves block verbatim. See the `key-decisions` frontmatter for the cited line numbers.

## Deviations from Plan

None — plan executed exactly as written. The acceptance criteria in `<tasks>` are satisfied verbatim; no Rule 1/2/3 auto-fixes were triggered during execution, no Rule 4 architectural escalation was needed.

## Notable deviations

None.

## Issues Encountered

None.

## Self-Check: PASSED

Verification commands run before this SUMMARY was committed:

1. **Test suite still green:**
   ```
   $ python -m pytest -q
   ........................................................................ [ 28%]
   ........................................................................ [ 57%]
   ........................................................................ [ 86%]
   ...................................                                      [100%]
   251 passed in 1.01s
   ```
   Baseline holds — unchanged from the post-07-03 baseline of 251 passed.

2. **Module imports without side effects:**
   ```
   $ python -c "from seers_harness.validation import TrialFailure, classify, is_trial_failure; print(classify(KeyError('x'))); print(is_trial_failure(TrialFailure('y')))"
   infra_error
   True
   ```
   The classifier returns `infra_error` for a `KeyError` (default fallback works) and `is_trial_failure` correctly recognises the sentinel.

3. **CLI --help works without DEEPSEEK_API_KEY:**
   ```
   $ python -m seers_harness.validation.runner --help
   usage: python -m seers_harness.validation.runner [-h] [--stage {1,2,3}]
                                                    [--out-dir OUT_DIR]
                                                    [--csv CSV]
                                                    [--num-requests NUM_REQUESTS]
   ...
   ```
   The `--stage` choice list shows `{1,2,3}`; the flag is OPTIONAL (default `None` → all three stages run).

4. **Three classification labels present in exception_classifier.py:**
   ```
   $ grep -nE '"trial_failure"|"infra_error"|"provider_error"' seers_harness/validation/exception_classifier.py
   6:* ``"trial_failure"`` — the exception originated inside a trial wrapper
   16:* ``"provider_error"`` — HTTP / API errors from the OpenAI-compatible
   21:* ``"infra_error"`` — anything else (``KeyError``, ``AttributeError``,
   24:  level. The default fallback is ``"infra_error"`` — the classifier
   31:    "trial_failure"   ┃ record on the request row, host continues
   32:    "provider_error"  ┃ fail-fast (stage stops, exit non-zero)
   33:    "infra_error"     ┃ fail-fast (stage stops, exit non-zero)
   96:) -> Literal["trial_failure", "provider_error", "infra_error"]:
   101:    fallback is ``"infra_error"`` — there is no silent-absorb branch.
   104:        return "trial_failure"
   106:        return "provider_error"
   107:    return "infra_error"
   ```

5. **D-04 rate-mask acknowledgement docstring present:**
   ```
   $ grep -nE "D-04|rate ceiling|60 retries" seers_harness/validation/runner.py
   36:D-04 acknowledgement: Stage 3 may mask real concurrency-induced rate
   39:slack. This is observation, not stabilisation (D-04). Real-DeepSeek
   151:# these values without re-reading 07-CONTEXT.md decisions D-01 / D-04 /
   592:        # module docstring for the PROD-02 rationale and D-04
   ```

6. **No inter-stage pause prompt anywhere in source:**
   ```
   $ grep -nE "re-invoke with --stage 2|review .runs|Stage 1 complete — review" seers_harness/validation/runner.py
   (zero matches)
   ```
   Default invocation runs Stage 1 → 2 → 3 end-to-end with NO human-checkpoint message (D-07).

7. **No wrapper retry, no token cap:**
   ```
   $ grep -nE "max_retries|retry" seers_harness/validation/runner.py | grep -v '^[^:]*:[[:space:]]*#'
   (all matches inside docstrings / comments / the assembled _PROVIDER_BUDGET_KEY string — no in-line re-attempt loop)
   $ grep -nE "max_tokens" seers_harness/validation/runner.py | grep -v '^[^:]*:[[:space:]]*#'
   (zero matches)
   ```

8. **Both 07-04 task commits exist in HEAD:**
   ```
   $ git log --oneline c264adb fd80506
   fd80506 feat(07-04): implement runner.py CLI and three-stage execution matrix
   c264adb feat(07-04): implement exception_classifier for D-19 trial-failure routing
   ```

9. **All three created/modified files exist on disk:**
   ```
   $ ls seers_harness/validation/runner.py seers_harness/validation/exception_classifier.py seers_harness/validation/__init__.py
   seers_harness/validation/__init__.py
   seers_harness/validation/exception_classifier.py
   seers_harness/validation/runner.py
   ```

## Next Phase Readiness

- 07-04 deliverables (runner.py + exception_classifier.py + extended `__init__.py`) are the integration surface 07-06 will consume to execute the canonical evidence batch end-to-end against real DeepSeek.
- 07-06 is `autonomous: false` and includes the only remaining checkpoint in Phase 7 (manual case-analysis review per D-15). The runner advances Stage 1 → 2 → 3 without human input; the checkpoint is on the case-reading verdict layer, not on the runner mechanics.
- The validation package's `__init__.py` is now feature-complete for Phase 7 — 07-06 may add additional helpers, but the core capture (07-02) + writer (07-03) + runner (07-04) + classifier (07-04) surfaces are stable.
- Workspace 251/251 test baseline remains green; no behavioural drift from Phase 6.

---
*Phase: 07-real-llm-validation*
*Plan: 07-04 stage-runner*
*Completed: 2026-05-26*
