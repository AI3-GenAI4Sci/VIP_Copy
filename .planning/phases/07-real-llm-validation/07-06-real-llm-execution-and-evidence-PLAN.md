---
phase: 07-real-llm-validation
plan_id: 07-06
wave: 4
depends_on:
  - 07-04
files_modified:
  - tests/smoke/.runs/
  - .planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md
autonomous: false
requirements_addressed:
  - VAL-01
  - VAL-02
  - VAL-04
  - VAL-06
skills_used:
  - verification-before-completion
  - claude-api
  - error-analysis
  - eval-audit
  - systematic-debugging
  - gsd-verify-work
---

<objective>
Run the canonical evidence batch against real DeepSeek end-to-end. Invoke the stage runner from 07-04 in a single default invocation that drives Stage 1 → Stage 2 → Stage 3 (one-shot c=20 per the plan-04 rationale) automatically with no inter-stage human checkpoint (D-07), produce the canonical artifact set under `tests/smoke/.runs/<timestamp>/`, and confirm the machine-judged verdicts for VAL-01, VAL-02, and VAL-04 directly from the resulting `index.json` + `batch_summary.json`. A single human pre-flight checkpoint protects the API budget before the run starts (this is pre-stage, not inter-stage). Acknowledge that VAL-03 / VAL-05 / VAL-06 verdicts are downstream — they are recorded by the user in `case_analysis.md` (07-05) and live outside execute-phase. Implements the evidence side of VAL-01, VAL-02, VAL-04, and VAL-06; anchors D-01 (stage matrix), D-02 (fail-fast at request level), D-07 (no inter-stage human checkpoint), D-09 (.runs/&lt;ts&gt;/ git-ignored), D-12 (reflow attribution), D-13 (case-analysis ownership downstream), D-17/D-18 (evolution evidence — including portfolio-empty-at-start), D-19 (trial-failure routing).
</objective>

<must_haves>
  <truth>tests/smoke/.runs/&lt;timestamp&gt;/ exists with the full canonical artifact tree: evidence/&lt;node_id&gt;/{messages.jsonl, tool_calls.jsonl, artifact.json, usage.json}, index.json, batch_summary.json, evolution_snapshot.json (D-22a/b/c/d).</truth>
  <truth>The runner is invoked exactly once (default invocation, no `--stage` flag) and drives Stage 1 → Stage 2 → Stage 3 end-to-end with no inter-stage human pause (D-07).</truth>
  <truth>Each stage produces its own .runs/&lt;ts&gt;/ directory (or each stage writes into a stage-named subdir under one parent &lt;ts&gt;/, per the runner's chosen layout). index.json["stage"] is one of {1, 2, 3} per stage and index.json["requests"] has length matching the stage matrix from D-01.</truth>
  <truth>batch_summary.json totals reflect machine-judged VAL-01, VAL-02, VAL-04 pass counts; fail_lists enumerate the failing node_ids.</truth>
  <truth>evolution_snapshot.json contains delta_portfolio_before, delta_portfolio_after, and trials[] populated by the 07-01 hooks (D-17, D-18, VAL-06 evidence).</truth>
  <truth>Zero trials in Stage 1 / early Stage 2 is recorded as expected behaviour (D-18 — portfolio starts empty, deltas distill in-flight) and does NOT affect exit code or stage progression.</truth>
  <truth>If any stage fails-fast on a non-trial exception, the run stops there (no advance to the next stage), the partial artifact set still exists under tests/smoke/.runs/&lt;timestamp&gt;/, and the failure is logged to 07-EXECUTION-LOG.md with the exception class from D-19 routing. To resume after fixing the failure, the user manually invokes `--stage N` for the failed stage (re-run flag, not an inter-stage checkpoint).</truth>
  <truth>Case-analysis (VAL-03 / VAL-05 / VAL-06 verdicts) is explicitly NOT performed in this plan — it is a downstream manual user activity per D-13/D-14.</truth>
</must_haves>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1: Pre-flight environment check</name>
  <what-built>The full validation toolchain (07-01 through 07-04) and case_analysis skeleton (07-05) are on disk. About to invoke real DeepSeek for an end-to-end three-stage run.</what-built>
  <how-to-verify>
    1. Confirm DeepSeek API key is set: `echo "${DEEPSEEK_API_KEY:+set}"` prints "set" (do not print the key itself).
    2. Confirm the runner imports cleanly: `python -c "from seers_harness.validation.runner import main"` exits 0.
    3. Confirm the smoke chain shape is reachable: `python -c "import importlib; importlib.import_module('seers_harness.validation.runner')"` exits 0.
    4. Confirm tests/smoke/.runs is gitignored (D-09 — no canonical run artifact enters the repo).
    5. Confirm budget: a default invocation runs Stage 1 (1 request) → Stage 2 (20 sequential) → Stage 3 (20 concurrent) = ≈41 DeepSeek calls in one shot, no token cap (D-06), no inter-stage human pause (D-07). If a stage fails-fast, the run stops there.
  </how-to-verify>
  <resume-signal>Type "go" to launch the end-to-end three-stage run, or describe environment issues to fix first.</resume-signal>
</task>

<task type="auto">
  <name>Task 2: Execute the end-to-end three-stage run and finalise the execution log</name>
  <files>tests/smoke/.runs/, .planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md</files>
  <read_first>
    - seers_harness/validation/runner.py (07-04 — the CLI just built; note the module docstring rationale referencing PROD-02 and acknowledging D-04 rate-mask)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-01 stage matrix, D-02 fail-fast at request level, D-07 stages run end-to-end automatically with no inter-stage human checkpoint, D-09 .runs/ git-ignored, D-12 reflow flag, D-17/D-18 evolution wiring + portfolio-empty-at-start, D-19 trial-failure routing)
  </read_first>
  <action>
    Run `python -m seers_harness.validation.runner` with no `--stage` flag. The runner drives Stage 1 (N=1, c=1) → Stage 2 (N=20, c=1) → Stage 3 (N=20, c=20) end-to-end automatically (D-07 — no inter-stage human pause). Capture the timestamp directory path (or root path if the runner used one parent &lt;ts&gt;/ with stage subdirs).
    Append entries to .planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md (create if missing): for each stage that ran, record timestamp, stage, exit code, head of index.json (stage, batch_id, n, concurrency, len(requests)), and head of batch_summary.json totals (val01_pass, val02_pass, val04_pass, requests count, head of fail_lists, manual_review_queue length). For Stage 3 also record any provider-error / rate-limit observations (cross-reference Phase 6 PROD-02 if encountered) and observe — without acting on — the D-04 rate-mask consequence (per-request max_retries=3 × 20 concurrent = 60 retries of slack).
    Trial-failure exceptions (D-19) do NOT abort the run — they are recorded in evolution_snapshot.json and the host request continues. Non-trial fail-fast exceptions stop the run at that stage; document the classified exception class (provider_error / infra_error) and note that resume requires invoking `python -m seers_harness.validation.runner --stage N` for the failed stage after fixing the underlying issue.
    Zero trials in Stage 1 / early Stage 2 is expected behaviour (D-18 — portfolio starts empty; deltas distill in-flight). Record the trial counts in the log; do NOT treat zero trials in Stage 1 as a Stage-1 failure or a fail-fast trigger.
    Append a closing summary entry to 07-EXECUTION-LOG.md noting: total DeepSeek calls across stages, total cost (from sum of per-node usage.json total_tokens), trial counts per stage (with explicit "0 expected for Stage 1 / early Stage 2 per D-18" if observed), pointer to .planning/phases/07-real-llm-validation/case_analysis.md for the downstream manual VAL-03/05/06 verdicts (D-13/D-14 — case analysis is NOT done here).
  </action>
  <acceptance_criteria>
    - Most-recent tests/smoke/.runs/&lt;ts&gt;/ tree contains evidence/&lt;node_id&gt;/{messages.jsonl, tool_calls.jsonl, artifact.json, usage.json} for at least one node per stage, plus index.json, batch_summary.json, evolution_snapshot.json per stage
    - On full success: Stage 1 index.json has stage==1 and n==1 and concurrency==1 and len(requests)==1; Stage 2 has stage==2 and n==20 and concurrency==1; Stage 3 has stage==3 and n==20 and concurrency==20 (D-01)
    - evolution_snapshot.json["trials"] is present for each stage; Stage 1 / early Stage 2 may legitimately have empty trials[] (D-18) — this is logged, not flagged as failure, and does NOT affect exit code or stage progression
    - 07-EXECUTION-LOG.md contains entries for Stage 1, Stage 2, Stage 3 (or for the prefix that ran before fail-fast) plus a closing summary entry pointing to case_analysis.md for manual verdicts
    - The closing summary explicitly states VAL-03 / VAL-05 / VAL-06 verdicts are user-confirmed downstream activities (D-13, D-14)
    - On fail-fast: 07-EXECUTION-LOG.md captures the exception class via classify() routing (provider_error / infra_error), notes which stage stopped, and points the user at `--stage N` for re-run after fixing
    - Trial-failure exceptions did NOT cause the run to abort — verify by reading evolution_snapshot.json["trials"] for any "failed" entries with the host request still appearing in the corresponding stage's index.json (D-19)
    - The run was a single CLI invocation with no inter-stage human pause — verify by reading 07-EXECUTION-LOG.md and confirming no "checkpoint" or "human review" entries between stage entries (D-07)
  </acceptance_criteria>
  <done>The full three-stage canonical evidence batch is on disk from a single end-to-end invocation; machine VAL-01/02/04 verdicts are observable in batch_summary.json; Stage 1 / early Stage 2 zero-trial observations are logged as expected per D-18; the execution log hands off to case_analysis.md for the manual VAL-03/05/06 verdicts.</done>
</task>

</tasks>

<verification>
  - The newest tests/smoke/.runs/&lt;ts&gt;/ tree has index.json, batch_summary.json, evolution_snapshot.json, evidence/&lt;node_id&gt;/{messages.jsonl, tool_calls.jsonl, artifact.json, usage.json} for each stage that ran
  - 07-EXECUTION-LOG.md contains entries for Stage 1, Stage 2, Stage 3 (or the fail-fast prefix), and a closing summary; no "human review" / "checkpoint" entries appear between stage entries (D-07)
  - The plan does NOT pretend to deliver VAL-03 / VAL-05 / VAL-06 verdicts — it produces the evidence those verdicts will read; the verdicts themselves are the user's downstream case-analysis activity per D-13/D-14
  - autonomous: false reflects ONLY the single pre-flight environment checkpoint (Task 1, pre-stage); the run itself is autonomous per D-07
</verification>
