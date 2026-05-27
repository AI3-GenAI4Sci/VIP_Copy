---
template_for: case_analysis.md
template_version: 1.0
created: 2026-05-27T03:55:00Z
audience: user (D-13/D-14 — only user-authored verdicts admitted to case_analysis.md)
purpose: |
  Reading guide for trajectory-level case analysis on real-LLM evidence.
  This template instructs the analyst to READ INPUT/OUTPUT CONTENT
  per request, NOT count statistics. The frontmatter columns in
  index.json (val01_pass, len_*, literal_overlap_*) are NAVIGATION
  AIDS — they tell you WHICH cases to read first; they are NOT the
  verdict. The verdict comes from reading messages.jsonl /
  tool_calls.jsonl / artifact.json content directly.
non_goals:
  - Do not write percentages ("12/20 = 60% pass") as a finding.
  - Do not write "all rows have val01_pass=true" as a finding.
  - Do not summarise rows by aggregating index.json columns.
goals:
  - For each F1..F4 sub-heading, quote 1-3 concrete factor texts from the
    real artifact.json on disk, then explain what made that factor
    transferable / non-transferable / borderline.
  - For each VAL-03 reflection check, read the messages.jsonl trajectory
    of `personalized_copy_rubric` and judge whether reflection tools
    were actually called (not just whether the column says null).
  - For each VAL-06 evolution observation, open evolution_snapshot.json
    and read the trials[] array contents, not just check whether it is
    empty — empty is only meaningful if you can explain WHY (D-18 vs.
    distill-skill nominated nothing vs. wiring missing).
---

# Case Analysis Template — Trajectory-Level Reading

**This is not a stats summary.** Per user direction 2026-05-27:
"case分析是真的看输入输出具体内容进行轨迹级别的case分析，而不是依旧统计数值。"

If you find yourself counting `val01_pass=true` rows or quoting an
`index.json` column, stop and re-read this header. The columns are a
**navigation tool**, not a verdict. The verdict comes from opening the
JSONL files and reading trajectories.

---

## Part 0 — Setup (do this once before reading any case)

1. Identify the run directory: `tests/smoke/.runs/<timestamp>/`. There
   should be `stage1/`, `stage2/`, and (after phase 8) `stage3/`.

2. Open the per-stage `index.json` and **use it only for navigation**.
   Pick reading order:
   - Sort by `len_covers_product_ids` desc → top 3 (E1: most
     multi-product factors). Suspicious if many products are claimed.
   - Sort by `len_transferable_disposition_text` asc → top 3 (E2: shortest
     dispositions). Suspicious if too short to be transferable.
   - Sort by `len_transferable_disposition_text` desc → top 3 (E3:
     longest dispositions). Suspicious if drifted into copy-prose.
   - Sort by `literal_overlap_user_signal_vs_transferable_disposition` desc
     → top 3 (E4: highest overlap). Suspicious if disposition is just a
     paraphrase of the user signal (no transformation).

3. For each picked request, you'll read this directory:
   ```
   stage{N}/<request_id>/
     ├── _artifacts/              # local copy of any synthesised artifacts
     ├── evidence/
     │   ├── factor_discovery/
     │   │   ├── messages.jsonl   # full conversation → factor_discovery
     │   │   ├── tool_calls.jsonl # what the model decided to call
     │   │   ├── artifact.json    # the resulting factors[] structure
     │   │   └── usage.json       # tokens, model, cache hit rate
     │   ├── copy_generation/     # same quartet
     │   └── personalized_copy_rubric/   # same quartet
     └── evolution_snapshot.json  # delta_portfolio_before/after + trials[]
   ```

---

## Part 1 — VAL-05 F1..F4 (the 60% of phase-7 verdict)

For each of F1..F4, read AT LEAST 3 cases from the navigation queue
above. For each case, follow this reading protocol:

### Reading protocol (per case)

1. Open `evidence/factor_discovery/artifact.json`. Skim the
   `factors[]` array — usually 5-8 factors per request.

2. For each factor, look at three fields in this order:
   - `user_side_signal` — what the user did (the input).
   - `transferable_disposition` — the prose claim about user character.
   - `evidence_refs` — the ground-truth tether (which user-signal events).
   - `covers_product_ids` — which catalog products this disposition covers.

3. Now turn to the F-question. Pick the factor (or one factor in the
   array) that best illustrates the F-question, and quote it inline.

### F1 — Generic-sounding language

A transferable disposition is **generic** when its prose would apply to
50%+ of any user base ("注重个人形象", "追求生活品质") rather than this
specific user's signal pattern.

For each case read, quote the factor's `transferable_disposition` and
say:
- WHY you picked this case (which `index.json` column flagged it, or
  what stood out when you opened the artifact).
- Whether the disposition prose is generic or specific. If specific,
  what makes it specific (a phrase tied to evidence_refs, a behavioural
  pattern not visible in a marketing template).
- If borderline, name the borderline. (e.g. "注重护理" is generic;
  "在每月固定补货周期里优先考虑高端护肤" is specific to a cadence
  visible in evidence_refs.)

```yaml
case_F1_example_1:
  request_id:           # from stage{N}/<id>
  factor_index:         # which factor in factors[]
  user_side_signal:     # quoted verbatim
  transferable_disposition:  # quoted verbatim
  evidence_refs_count:  # how many evidence_refs back the claim
  verdict: generic | specific | borderline
  reasoning: |
    ...one paragraph explaining the verdict against F1...
```

Repeat for F1_example_2 and F1_example_3 (different requests).

### F2 — Broken causal chain

A causal chain is **broken** when the factor cannot trace back through
`evidence_refs` to the user_side_signal. Or when the disposition prose
asserts a claim that does not follow from the user's actions.

Reading protocol same as F1 but the focus is the *link*:
- Quote `user_side_signal`.
- Quote `transferable_disposition`.
- Open `evidence_refs[]`. Each ref should point at a real user-signal
  event ID. Verify the link by skimming `messages.jsonl` (system
  message likely carries the user_signal block — check that the cited
  IDs are present).
- Verdict: chain holds | chain broken | chain partial.

### F3 — Boilerplate-untethered

A factor is **boilerplate-untethered** when the prose feels like it was
written from a personalisation playbook (e.g. "用户重视品质生活") rather
than emerging from THIS user's evidence.

Watch for:
- Phrases that recur across multiple users' artifact.json files (cross-
  request cluster — but you don't need full clustering, just a smell test).
- Disposition prose with no evidence_refs at all, or with refs that
  don't materially constrain the prose.
- Disposition prose that would be identical if the user_side_signal
  were swapped for any other plausible behaviour pattern.

### F4 — Multi-product overclaim

A factor **overclaims** when `covers_product_ids` lists more products
than the underlying disposition can plausibly support. The
`len_covers_product_ids` column (E1) navigates here — the highest-N
factors are the most likely overclaimers.

For each case:
- Quote the factor and its `covers_product_ids` count.
- Read the catalog products that ID list points at (from the
  scenario's input — usually in `messages.jsonl` system block). Are
  they actually a coherent group that this disposition could cover?
- Verdict: coverage justified | coverage overclaim | coverage borderline.

---

## Part 2 — VAL-03 reachable reflection (real trajectory check)

VAL-03 is null in `index.json` by D-13 design. Your verdict comes from
reading `evidence/personalized_copy_rubric/messages.jsonl` and
`tool_calls.jsonl`:

1. Open the `messages.jsonl` for `personalized_copy_rubric`. The trajectory
   is the chronological turn-by-turn between system / user / assistant.

2. Was the rubric skill given a candidate copy and asked to grade it?
   (System prompt should set up that frame; user message should carry
   the candidate copy.)

3. Did the assistant respond with a tool call to a reflection tool
   (the rubric's own self-critique mechanism), OR did it produce a
   one-shot grade without reflecting? Open `tool_calls.jsonl` to see
   exactly which tools fired and in what order.

4. **Verdict (per user verbatim):**
   ```yaml
   reflection_observed:
     case_1:
       request_id:
       answered_in_one_shot: true | false
       tool_call_sequence:    # quoted from tool_calls.jsonl
       reasoning: |
         ...what the trajectory shows...
   ```

5. Read AT LEAST 2 cases. Reflection should be observable in the
   trajectory; if you cannot find it in 2 cases, that is itself a
   verdict ("reflection mechanism not reached on these inputs").

---

## Part 3 — VAL-06 evolution mechanism observation

Open `evolution_snapshot.json` for each request. Three top-level keys:

- `delta_portfolio_before` — the portfolio state at request start.
- `delta_portfolio_after` — the portfolio state at request end.
- `trials[]` — what trials fired during this request.

Reading protocol:

1. **Currently (pre-phase-8): `trials[]` is structurally empty on every
   request.** The phase-8 charter Group F lands the runner ↔
   evolution wiring. Until then, the verdict for this section is
   "wiring missing — no observation possible". Note this in the
   `case_analysis.md` and move on.

2. **After phase 8 lands:** `trials[]` should carry at least one entry
   per request that hit a trial. For each such entry:
   - Read `selected_delta_id` — what test delta was applied?
   - Read `runtime.trace[]` — the per-node activity under the trial.
   - Read `outcome` — `succeeded` / `failed` / `noop`.
   - Read `events[]` (if present in the snapshot) — what
     observability events fired?

3. **Verdict (per user verbatim):**
   ```yaml
   evolution_observation:
     case_1:
       request_id:
       trials_fired: <int>
       selected_delta:
       outcome:
       reasoning: |
         ...what the snapshot shows about reflow cadence...
   ```

---

## Part 4 — synthesis

After all F1..F4 case readings + VAL-03 + VAL-06, write 1-3 paragraphs
of synthesis:

- What pattern did the real-LLM evidence reveal that the machine columns
  in `index.json` did not? (This is the heart of why case analysis is
  trajectory-level — the columns navigate, the prose verdicts.)
- Are the factors transferable in the project's sense, or is the model
  drifting toward generic personalisation playbooks?
- Where does the evidence chain hold tightest, and where does it fray?
- What changes (if any) to the upstream skill prompts would improve the
  next batch?

---

## Anti-pattern checklist (catch yourself if you do these)

- [ ] Did I quote any concrete user_side_signal / transferable_disposition
  text? If no → I am still in stats mode.
- [ ] Did I count rows or compute percentages? If yes → these go in
  `07-EXECUTION-LOG.md`, not `case_analysis.md`.
- [ ] Did I read `messages.jsonl` for any case? If no → I have not
  done trajectory analysis yet.
- [ ] Did I open `tool_calls.jsonl` for the VAL-03 cases? If no → my
  VAL-03 verdict is unsupported.
- [ ] Did I quote at least 3 cases per F-question? If no → the verdict
  is not yet sufficiently grounded.
