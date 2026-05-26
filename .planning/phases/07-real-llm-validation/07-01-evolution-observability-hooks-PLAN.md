---
phase: 07-real-llm-validation
plan_id: 07-01
wave: 1
depends_on: []
files_modified:
  - seers_harness/evolution/delta_portfolio.py
  - seers_harness/evolution/trial_runner.py
  - seers_harness/validation/__init__.py
  - seers_harness/validation/evolution_snapshot.py
autonomous: true
requirements_addressed:
  - VAL-06
skills_used:
  - verification-before-completion
  - gsd-verify-work
  - systematic-debugging
---

<objective>
Add a non-invasive observability seam to the existing evolution machinery so that delta-portfolio assembly and per-trial outcomes can be recorded without altering business logic. The hooks accept an optional `List[dict] | None` event sink — when None, behaviour is identical to today; when provided, the runner appends event records that a downstream writer flushes to `evolution_snapshot.json` for VAL-06 evidence. This plan implements D-11 (observability hook surface + the no-business-logic-change rule), D-19 (trial-failure routing — the trial event taxonomy that classification reads), and D-22(c) (planner discretion: hooks live in evolution/ rather than a wrapper module).
</objective>

<must_haves>
  <truth>delta_portfolio.py exposes an optional event-sink parameter; when None, current behaviour is byte-identical (D-11 no-business-logic-change rule).</truth>
  <truth>trial_runner.py emits a "trial_started" event before each trial and either a "trial_succeeded" or "trial_failed" event after, including trial_id, delta_id(s), and exception class on failure (D-19 trial-failure routing depends on this taxonomy).</truth>
  <truth>delta_portfolio.py emits a "portfolio_assembled" event recording delta_portfolio_before / delta_portfolio_after counts and ids when the sink is provided (D-11).</truth>
  <truth>seers_harness/validation/evolution_snapshot.py provides write_evolution_snapshot(events, out_path) that emits a JSON object with top-level keys delta_portfolio_before, delta_portfolio_after, trials[] (each with trial_id, status, exception_class on failure) (D-11, VAL-06).</truth>
  <truth>The hook surface is List[dict] | None per the locked decision — no callbacks, no observer classes (D-22c).</truth>
  <truth>No existing call site of delta_portfolio or trial_runner needs to change — the new parameter has a default of None (D-11 no-business-logic-change rule).</truth>
  <truth>D-20: Trial trigger uses Phase 6's portfolio-adaptive logic UNMODIFIED — this plan adds observability only, no cadence boost or trigger override; zero observed trials in 20 requests is a legitimate observation, not a defect of these hooks.</truth>
</must_haves>

<tasks>

<task type="auto">
  <name>Task 1: Add event-sink seam to delta_portfolio.py</name>
  <files>seers_harness/evolution/delta_portfolio.py</files>
  <read_first>
    - seers_harness/evolution/delta_portfolio.py (current implementation)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-11 hook surface + no-business-logic-change rule, D-19 trial event taxonomy, D-22c hook placement discretion)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (evolution observability section)
  </read_first>
  <action>
    Locate the public assembly entrypoint in delta_portfolio.py (the function that produces the post-evolution portfolio from a pre-evolution one). Add a keyword-only parameter `events: list[dict] | None = None` per D-22(c). After the portfolio is fully assembled, if events is not None, append a single dict with keys: type="portfolio_assembled", delta_portfolio_before (list of delta ids before evolution), delta_portfolio_after (list of delta ids after), counts {before, after}. Do not mutate any other behaviour. Do not log, do not raise, do not gate on events. Per D-11's no-business-logic-change rule, when events is None the function must be byte-equivalent to today.
  </action>
  <acceptance_criteria>
    - grep -nE "events: list\[dict\] \| None" seers_harness/evolution/delta_portfolio.py returns at least one line
    - grep -nE '"portfolio_assembled"' seers_harness/evolution/delta_portfolio.py returns one line
    - grep -nE '"delta_portfolio_before"|"delta_portfolio_after"' seers_harness/evolution/delta_portfolio.py returns two lines
    - python -c "import seers_harness.evolution.delta_portfolio" exits 0
    - All existing call sites of the assembly function still type-check (no required-argument added)
  </acceptance_criteria>
  <done>delta_portfolio.py has a non-breaking events sink that records portfolio_assembled when provided, and continues to behave identically when not.</done>
</task>

<task type="auto">
  <name>Task 2: Add per-trial event emission to trial_runner.py</name>
  <files>seers_harness/evolution/trial_runner.py</files>
  <read_first>
    - seers_harness/evolution/trial_runner.py (current implementation)
    - seers_harness/evolution/delta_portfolio.py (Task 1 result for parameter shape consistency)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-19 trial-failure routing — schema/protocol vs rate-limit/transient classification depends on emitted exception_class)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (trial event schema)
  </read_first>
  <action>
    In trial_runner.py, locate the per-trial loop. Add a keyword-only parameter `events: list[dict] | None = None`. Before invoking each trial, append (when events is not None) a dict {type: "trial_started", trial_id, delta_id (or delta_ids list)}. On successful completion, append {type: "trial_succeeded", trial_id, delta_id(s)} (D-19 success branch — host request continues on the unmodified main path). On exception, append {type: "trial_failed", trial_id, delta_id(s), exception_class: type(exc).__name__, exception_message: str(exc)} (D-19 — exception_class is what the runner's classifier reads to route schema/protocol failures fail-fast vs transient failures recorded against belief), then re-raise (do not swallow). The events list is the only side effect added; preserve fail-fast semantics. Per D-11's no-business-logic-change rule, with events=None the runner is unchanged. Constraint per D-20: do NOT modify trial trigger cadence or selection logic — Phase 6's portfolio-adaptive trigger stays untouched, this task adds observation only. Zero observed trials in 20 requests is a legitimate VAL-06 outcome and must not be hidden by an artificial cadence boost (D-20).
  </action>
  <acceptance_criteria>
    - grep -nE '"trial_started"|"trial_succeeded"|"trial_failed"' seers_harness/evolution/trial_runner.py returns three or more lines
    - grep -nE "exception_class" seers_harness/evolution/trial_runner.py returns at least one line
    - grep -nE "events: list\[dict\] \| None" seers_harness/evolution/trial_runner.py returns at least one line
    - python -c "import seers_harness.evolution.trial_runner" exits 0
    - The except handler that records trial_failed re-raises (no `pass` swallowing — verify by reading)
  </acceptance_criteria>
  <done>trial_runner emits trial_started / trial_succeeded / trial_failed events with classified exceptions while preserving fail-fast.</done>
</task>

<task type="auto">
  <name>Task 3: Implement evolution_snapshot.py writer</name>
  <files>seers_harness/validation/__init__.py, seers_harness/validation/evolution_snapshot.py</files>
  <read_first>
    - seers_harness/evolution/delta_portfolio.py (event shape from Task 1)
    - seers_harness/evolution/trial_runner.py (event shape from Task 2)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-11 snapshot schema, VAL-06 evidence)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (snapshot writer pattern)
  </read_first>
  <action>
    Create the seers_harness/validation/ package with an empty __init__.py if it does not already exist. Create evolution_snapshot.py exporting write_evolution_snapshot(events: list[dict], out_path: str | Path) -> None. The function reduces the events list into a single JSON object with keys: delta_portfolio_before (from the portfolio_assembled event, [] if absent), delta_portfolio_after (likewise), trials (list, each entry {trial_id, status: "succeeded"|"failed", exception_class (only when failed), exception_message (only when failed)}). Write JSON with indent=2 and a trailing newline. Create parent directories with Path(out_path).parent.mkdir(parents=True, exist_ok=True). Do not crash on a missing portfolio_assembled event — emit empty lists per D-11 (degrade gracefully, no business-logic change).
  </action>
  <acceptance_criteria>
    - test -f seers_harness/validation/__init__.py returns 0
    - test -f seers_harness/validation/evolution_snapshot.py returns 0
    - python -c "from seers_harness.validation.evolution_snapshot import write_evolution_snapshot" exits 0
    - grep -nE "delta_portfolio_before|delta_portfolio_after|trials" seers_harness/validation/evolution_snapshot.py returns three or more lines
    - python -c "from seers_harness.validation.evolution_snapshot import write_evolution_snapshot; import tempfile, json, pathlib; p=pathlib.Path(tempfile.mkdtemp())/'s.json'; write_evolution_snapshot([{'type':'portfolio_assembled','delta_portfolio_before':['a'],'delta_portfolio_after':['a','b'],'counts':{'before':1,'after':2}},{'type':'trial_succeeded','trial_id':'t1','delta_id':'b'}], p); d=json.loads(p.read_text()); assert d['delta_portfolio_after']==['a','b']; assert d['trials'][0]['status']=='succeeded'" exits 0
  </acceptance_criteria>
  <done>The snapshot writer transforms hook events into the canonical evolution_snapshot.json shape required for VAL-06 evidence.</done>
</task>

</tasks>

<verification>
  - python -c "import seers_harness.evolution.delta_portfolio, seers_harness.evolution.trial_runner, seers_harness.validation.evolution_snapshot" exits 0
  - grep -rnE "events: list\[dict\] \| None" seers_harness/evolution/ returns two files (delta_portfolio.py, trial_runner.py)
  - Manual read-through confirms NO existing call sites of delta_portfolio or trial_runner needed updates (default None preserves behaviour) — required by D-11 no-business-logic-change rule
  - The whole package is importable with no top-level side effects (no I/O, no network)
</verification>
