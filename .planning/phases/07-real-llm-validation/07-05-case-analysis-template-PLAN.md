---
phase: 07-real-llm-validation
plan_id: 07-05
wave: 1
depends_on: []
files_modified:
  - .planning/phases/07-real-llm-validation/case_analysis.md
autonomous: true
requirements_addressed:
  - VAL-03
  - VAL-05
  - VAL-06
skills_used:
  - verification-before-completion
  - eval-audit
  - gsd-verify-work
---

<objective>
Create the empty `case_analysis.md` audit artifact, seeded with the exact section structure D-13/D-14/D-15/D-16 require. The body is intentionally empty — case analysis is a manual, user-driven activity performed AFTER the canonical evidence batch runs; only user-confirmed conclusions are admitted (D-14). This file is the single in-tree audit document where VAL-03, VAL-05, and VAL-06 verdicts are recorded, anchored to the per-node evidence under tests/smoke/.runs/<ts>/. Implements D-13 (case-analysis ownership), D-14 (only user-confirmed conclusions), D-15 (the four fixed VAL-05 sub-headings F1..F4 quoted verbatim from CONTEXT), and D-16 (≈20-30 factors reading scope).
</objective>

<must_haves>
  <truth>The file .planning/phases/07-real-llm-validation/case_analysis.md exists (D-13).</truth>
  <truth>The file's header notes "only user-confirmed conclusions admitted (D-14)" (D-14).</truth>
  <truth>The file has one section per VAL-03, VAL-05, VAL-06 (D-13).</truth>
  <truth>Under VAL-05 the four fixed sub-headings F1, F2, F3, F4 appear in order with their D-15 descriptions verbatim — F1 = "Specific case wrapped in generic-sounding language", F2 = "Causal chain broken between `user_side_signal` and `bridge_to_product`", F3 = "Boilerplate-template `transferable_disposition` text untethered to a real signal", F4 = "`covers_product_ids` claims multi-product reach but `transferable_disposition` only explains one" (D-15).</truth>
  <truth>A reading-scope note states the manual review scope is approximately 20-30 factors per batch, anchored to D-16 (D-16).</truth>
  <truth>Section bodies are empty placeholders — no inferred conclusions, no auto-generated summaries (D-14).</truth>
</must_haves>

<tasks>

<task type="auto">
  <name>Task 1: Write the case_analysis.md skeleton</name>
  <files>.planning/phases/07-real-llm-validation/case_analysis.md</files>
  <read_first>
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-13, D-14, D-15 — quote F1-F4 names and descriptions verbatim from this file, D-16)
    - .planning/REQUIREMENTS.md (VAL-03, VAL-05, VAL-06 wording)
  </read_first>
  <action>
    Write a markdown file with this exact skeleton:
    - Top-level H1 "Case Analysis — Phase 07 Real-LLM Validation".
    - A header note paragraph stating: "Only user-confirmed conclusions are admitted here (D-14). Statistics from index.json / batch_summary.json navigate; this file is the verdict. Reading scope per batch is approximately 20-30 factors (D-16)."
    - H2 "VAL-03 — Transferable Disposition Prose Judgement" — empty body with a single italic placeholder line "_To be filled by the user after reading the manual-review queue._"
    - H2 "VAL-05 — Failure Mode Taxonomy" with four H3 sub-headings in order, each using the D-15 description verbatim — DO NOT invent shorter labels:
      * "### F1: Specific case wrapped in generic-sounding language"
      * "### F2: Causal chain broken between `user_side_signal` and `bridge_to_product`"
      * "### F3: Boilerplate-template `transferable_disposition` text untethered to a real signal"
      * "### F4: `covers_product_ids` claims multi-product reach but `transferable_disposition` only explains one"
      Each sub-heading has the same italic placeholder line.
    - H2 "VAL-06 — Evolution Behaviour" — empty body with the placeholder line.
    - Closing H2 "Reading Scope Note" reiterating D-16: "Cap per-batch manual review at ≈20-30 factors. If batch_summary.manual_review_queue exceeds this, prioritise reflow_triggered and trial_selected_delta_id rows first."
    Do not include any pre-filled conclusions. Do not number cases. Do not paraphrase D-15 — the four F-names and their text come straight from 07-CONTEXT.md.
  </action>
  <acceptance_criteria>
    - test -f .planning/phases/07-real-llm-validation/case_analysis.md returns 0
    - grep -c "^# Case Analysis" .planning/phases/07-real-llm-validation/case_analysis.md returns 1
    - grep -c "D-14" .planning/phases/07-real-llm-validation/case_analysis.md returns at least 1
    - grep -c "^## VAL-03" .planning/phases/07-real-llm-validation/case_analysis.md returns 1
    - grep -c "^## VAL-05" .planning/phases/07-real-llm-validation/case_analysis.md returns 1
    - grep -c "^## VAL-06" .planning/phases/07-real-llm-validation/case_analysis.md returns 1
    - grep -cE "^### F1:" .planning/phases/07-real-llm-validation/case_analysis.md returns 1
    - grep -cE "^### F2:" .planning/phases/07-real-llm-validation/case_analysis.md returns 1
    - grep -cE "^### F3:" .planning/phases/07-real-llm-validation/case_analysis.md returns 1
    - grep -cE "^### F4:" .planning/phases/07-real-llm-validation/case_analysis.md returns 1
    - The F1 heading contains the distinguishing phrase "generic-sounding language" — grep -c "generic-sounding language" .planning/phases/07-real-llm-validation/case_analysis.md returns at least 1
    - The F2 heading contains "user_side_signal" AND "bridge_to_product" — grep -c "user_side_signal" returns ≥1 AND grep -c "bridge_to_product" returns ≥1
    - The F3 heading contains "Boilerplate" AND "transferable_disposition" AND "untethered" — grep -c "Boilerplate" returns ≥1; grep -c "untethered" returns ≥1
    - The F4 heading contains "covers_product_ids" AND "multi-product" — grep -c "covers_product_ids" returns ≥1; grep -c "multi-product" returns ≥1
    - The invented labels "Misroute", "Hallucinated Coverage", "Reflow Trigger", "Trial-Selection Anomaly" do NOT appear in the file — grep -cE "Misroute|Hallucinated Coverage|Reflow Trigger|Trial-Selection Anomaly" .planning/phases/07-real-llm-validation/case_analysis.md returns 0
    - grep -cE "20.?30|20-30|20 to 30" .planning/phases/07-real-llm-validation/case_analysis.md returns at least 1
  </acceptance_criteria>
  <done>The case_analysis.md skeleton is on disk with the D-14 admittance rule, the three VAL sections, the four D-15 sub-headings using their verbatim CONTEXT.md descriptions (F1: generic-sounding language; F2: user_side_signal/bridge_to_product causal break; F3: boilerplate transferable_disposition untethered; F4: covers_product_ids multi-product overclaim), and the D-16 reading-scope note — ready for the user to fill in post-execution.</done>
</task>

</tasks>

<verification>
  - The file passes all the grep checks above
  - No section body contains pre-filled prose (every body is one italic placeholder line)
  - The four D-15 sub-headings appear in the order F1, F2, F3, F4 with the verbatim CONTEXT.md descriptions
  - The four invented labels (Misroute / Hallucinated Coverage / Reflow Trigger / Trial-Selection Anomaly) do not appear anywhere
</verification>
