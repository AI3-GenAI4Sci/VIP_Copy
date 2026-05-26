---
phase: 07-real-llm-validation
plan_id: 07-03
wave: 2
depends_on:
  - 07-01
  - 07-02
files_modified:
  - seers_harness/validation/__init__.py
  - seers_harness/validation/index_writer.py
  - seers_harness/validation/batch_summary_writer.py
  - seers_harness/validation/machine_judges.py
autonomous: true
requirements_addressed:
  - VAL-01
  - VAL-02
  - VAL-03
  - VAL-04
  - VAL-05
skills_used:
  - verification-before-completion
  - eval-audit
  - gsd-verify-work
  - error-analysis
---

<objective>
Define the canonical schemas for `index.json` (one row per request) and `batch_summary.json` (one object per stage run), and ship the writers that materialise them after a stage finishes. The index row exposes the sortable navigation columns required by D-16's four extreme dimensions: E1 = longest `covers_product_ids` (sort `len_covers_product_ids` descending), E2 = shortest `transferable_disposition` text (sort `len_transferable_disposition_text` ascending), E3 = longest `transferable_disposition` text (sort `len_transferable_disposition_text` descending — same column as E2, opposite direction), E4 = highest literal overlap between `user_side_signal` and `transferable_disposition` (sort `literal_overlap_user_signal_vs_transferable_disposition` descending). The raw `transferable_disposition_text` passthrough column carries the text itself for inspection — it is NOT labelled E3. Plus per-request booleans for VAL-01..VAL-04, plus the reflow flag (D-12) and the trial-selection flag (D-10). batch_summary aggregates pass/fail counts and surfaces the manual-review queue. Implements D-10 (trial-selection visibility), D-12 (reflow attribution), D-16 (sortable columns scope ≈20-30 with E2/E3 sharing one column at opposite sort directions), and D-22(d) (writer layer separate from capture layer).
</objective>

<must_haves>
  <truth>index.json has top-level keys: stage (1|2|3), batch_id, started_at, finished_at, n, concurrency, requests (list) (D-22d).</truth>
  <truth>Each requests[] row has node_id and the sortable columns for D-16's four extreme dimensions: len_covers_product_ids (int) covers E1 (longest covers_product_ids — sort desc); len_transferable_disposition_text (int) covers BOTH E2 (shortest transferable_disposition_text — sort asc) AND E3 (longest transferable_disposition_text — sort desc, same column, opposite direction); literal_overlap_user_signal_vs_transferable_disposition (float in [0,1]) covers E4 (highest overlap — sort desc) (D-16).</truth>
  <truth>A raw text passthrough column transferable_disposition_text (str) carries the disposition text itself for inspection. This column is NOT a separate E-dimension — it is a fidelity passthrough so the user can read the text after navigating by E2/E3 (D-16).</truth>
  <truth>Each requests[] row has booleans: VAL-01_pass, VAL-02_pass, VAL-03_pass (machine-judged subset only — manual review fields default null), VAL-04_pass (D-22d, VAL-01..04).</truth>
  <truth>Each requests[] row has reflow_triggered (bool) per D-12 and trial_selected_delta_id (str|null) per D-10.</truth>
  <truth>batch_summary.json contains stage, batch_id, totals {requests, val01_pass, val02_pass, val04_pass}, fail_lists (per-VAL list of node_ids), and manual_review_queue (list of node_ids that machine-judging cannot resolve, e.g. VAL-03 prose-judgement and VAL-05 case-analysis triggers) (D-22d, D-16).</truth>
  <truth>Machine judges for VAL-01/02/04 are pure functions in machine_judges.py — they read per-node artifact.json and return bool with a one-line reason (D-22d).</truth>
</must_haves>

<tasks>

<task type="auto">
  <name>Task 1: Implement machine_judges.py for VAL-01/02/04 plus column extractors</name>
  <files>seers_harness/validation/machine_judges.py</files>
  <read_first>
    - seers_harness/validation/evidence_writer.py (artifact.json shape from 07-02)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-16 four extreme dimensions E1-E4, mapping E2/E3 onto a single shared column at opposite sort directions; VAL-01..VAL-04 definitions)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (machine-judge function signatures)
    - .planning/REQUIREMENTS.md (VAL-XX wording — must match the source of truth)
  </read_first>
  <action>
    Create machine_judges.py exporting these pure functions, each taking a parsed artifact dict and returning (bool, str) where str is a one-line reason:
    - judge_val01(artifact): structural shape — required keys present (covers_product_ids, transferable_disposition_text, user_signal). Missing key → False with the missing key in the reason.
    - judge_val02(artifact): covers_product_ids is a non-empty list of ints/strs (no nulls, no empty strings).
    - judge_val04(artifact): transferable_disposition_text is a non-empty trimmed string.
    Also export column extractors. Per D-16, E2 and E3 share a single column (len_transferable_disposition_text) — sort ascending for E2 (shortest), sort descending for E3 (longest). The raw-text column is a passthrough for inspection, not an E-dimension label:
    - extract_len_covers_product_ids(artifact) -> int                      # serves E1 (sort desc = longest covers_product_ids)
    - extract_len_transferable_disposition_text(artifact) -> int           # serves BOTH E2 (sort asc) AND E3 (sort desc) — character count of stripped string
    - extract_transferable_disposition_text(artifact) -> str               # raw, untrimmed for fidelity — passthrough, NOT an E-dimension
    - extract_literal_overlap(artifact) -> float                           # serves E4 (sort desc = highest overlap) — token-set Jaccard between artifact["user_signal"] and artifact["transferable_disposition_text"] after whitespace tokenisation and lowercasing; 0.0 when either side is empty (D-16).
    Add a module-level docstring documenting the E-dimension → column mapping verbatim: "E1 ↔ len_covers_product_ids (sort desc); E2 ↔ len_transferable_disposition_text (sort asc, shortest); E3 ↔ len_transferable_disposition_text (sort desc, longest — same column as E2, opposite direction); E4 ↔ literal_overlap_user_signal_vs_transferable_disposition (sort desc)." This is the contract the batch_summary writer's manual_review_queue selector reads.
    No I/O — these are pure. Each judge tolerates an artifact of None by returning (False, "no artifact") so the index writer can still produce a row for the failed request (D-12 reflow rows still need a row).
  </action>
  <acceptance_criteria>
    - python -c "from seers_harness.validation.machine_judges import judge_val01, judge_val02, judge_val04, extract_len_covers_product_ids, extract_len_transferable_disposition_text, extract_transferable_disposition_text, extract_literal_overlap" exits 0
    - python -c "from seers_harness.validation.machine_judges import judge_val01, judge_val02, judge_val04; assert judge_val01(None)==(False,'no artifact'); assert judge_val02({'covers_product_ids':[1,2]})[0] is True; assert judge_val04({'transferable_disposition_text':' '})[0] is False" exits 0
    - python -c "from seers_harness.validation.machine_judges import extract_literal_overlap; assert 0.0 <= extract_literal_overlap({'user_signal':'a b c','transferable_disposition_text':'a b'}) <= 1.0; assert extract_literal_overlap({'user_signal':'','transferable_disposition_text':'a'})==0.0" exits 0
    - grep -nE "def judge_val01|def judge_val02|def judge_val04" seers_harness/validation/machine_judges.py returns three lines
    - The module docstring documents the E1/E2/E3/E4 → column mapping (grep -nE "E1|E2|E3|E4" seers_harness/validation/machine_judges.py returns at least four lines across docstring and comments)
    - The docstring states explicitly that E2 and E3 SHARE the len_transferable_disposition_text column at opposite sort directions (grep -nE "shortest|longest|sort asc|sort desc" seers_harness/validation/machine_judges.py returns multiple lines)
  </acceptance_criteria>
  <done>Machine judges and column extractors are pure, importable, produce deterministic outputs for the three canonical numeric columns plus the raw-text passthrough column. The module docstring documents D-16's E1-E4 → column mapping with E2/E3 sharing the len column at opposite sort directions.</done>
</task>

<task type="auto">
  <name>Task 2: Implement index_writer.py</name>
  <files>seers_harness/validation/index_writer.py</files>
  <read_first>
    - seers_harness/validation/machine_judges.py (Task 1 — note the E1-E4 → column mapping in the docstring)
    - seers_harness/validation/evidence_writer.py (per-node directory layout)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-10 trial-selection flag, D-12 reflow flag, D-16 columns — E2/E3 share len_transferable_disposition_text at opposite sort directions)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (index.json schema)
  </read_first>
  <action>
    Create index_writer.py exporting write_index(records: list[dict], out_dir: Path, stage: int, batch_id: str, started_at: str, finished_at: str, n: int, concurrency: int) -> None. Each record in records is the dict produced by the stage runner — at minimum {node_id, artifact (parsed dict or None), reflow_triggered (bool), trial_selected_delta_id (str|None), exception (str|None)}. For each record, build a row with: node_id; the sortable columns from machine_judges extractors (with None-artifact fallback to 0/0/""/0.0) — len_covers_product_ids (serves E1), len_transferable_disposition_text (serves BOTH E2 ascending sort and E3 descending sort — same column), transferable_disposition_text (raw text passthrough, NOT an E-dimension), literal_overlap_user_signal_vs_transferable_disposition (serves E4); VAL-01_pass / VAL-02_pass / VAL-04_pass booleans from judges; VAL-03_pass = null (manual per D-13/D-14); reflow_triggered; trial_selected_delta_id; exception (passthrough). The top-level index dict has keys stage, batch_id, started_at, finished_at, n, concurrency, requests (the row list, in the order the runner submitted them — preserve list order). Write to out_dir / "index.json" with indent=2. Add a module-level docstring noting "Sort len_transferable_disposition_text ascending for E2 (shortest), descending for E3 (longest); same column, opposite direction (D-16)."
  </action>
  <acceptance_criteria>
    - test -f seers_harness/validation/index_writer.py returns 0
    - python -c "from seers_harness.validation.index_writer import write_index" exits 0
    - grep -nE '"len_covers_product_ids"|"len_transferable_disposition_text"|"transferable_disposition_text"|"literal_overlap_user_signal_vs_transferable_disposition"' seers_harness/validation/index_writer.py returns four or more lines
    - grep -nE '"VAL-01_pass"|"VAL-02_pass"|"VAL-03_pass"|"VAL-04_pass"' seers_harness/validation/index_writer.py returns four lines
    - grep -nE '"reflow_triggered"|"trial_selected_delta_id"' seers_harness/validation/index_writer.py returns two lines
    - The module docstring documents E2/E3 column sharing (grep -nE "E2|E3|shortest|longest" seers_harness/validation/index_writer.py returns at least two lines)
    - python -c "from seers_harness.validation.index_writer import write_index; import tempfile, pathlib, json; d=pathlib.Path(tempfile.mkdtemp()); write_index([{'node_id':'n1','artifact':{'covers_product_ids':[1],'transferable_disposition_text':'x','user_signal':'x'},'reflow_triggered':False,'trial_selected_delta_id':None,'exception':None}], d, 1, 'b1','t0','t1',1,1); idx=json.loads((d/'index.json').read_text()); assert idx['stage']==1 and idx['requests'][0]['VAL-01_pass'] is True and idx['requests'][0]['VAL-03_pass'] is None" exits 0
  </acceptance_criteria>
  <done>index.json contains exactly the schema D-16 prescribes — three numeric sortable columns (len_covers_product_ids for E1, len_transferable_disposition_text serving both E2 and E3 at opposite sort directions, literal_overlap_user_signal_vs_transferable_disposition for E4) plus the raw-text passthrough, four VAL booleans (VAL-03 null), reflow + trial-selection flags — for every request the runner submitted.</done>
</task>

<task type="auto">
  <name>Task 3: Implement batch_summary_writer.py</name>
  <files>seers_harness/validation/batch_summary_writer.py</files>
  <read_first>
    - seers_harness/validation/index_writer.py (Task 2 row schema — note E2/E3 share len_transferable_disposition_text)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-13 case-analysis ownership, D-14 user-confirmed-only, D-16 sortable scope — E1 longest covers, E2 shortest text, E3 longest text, E4 highest overlap)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (batch_summary aggregation rules)
  </read_first>
  <action>
    Create batch_summary_writer.py exporting write_batch_summary(index_path: Path, out_path: Path | None = None) -> None. Default out_path is index_path.parent / "batch_summary.json". Read index.json, then aggregate: stage, batch_id (passthrough), totals = {requests: len(rows), val01_pass: count of rows with VAL-01_pass True, val02_pass, val04_pass}; fail_lists = {VAL-01: [node_id...], VAL-02: [...], VAL-04: [...]} (only failures, not nulls); manual_review_queue = list of node_ids that need human reading — defined as the union of (a) any row with VAL-03_pass is None AND len_transferable_disposition_text > 0 (i.e. there is prose to judge per D-13), (b) rows flagged reflow_triggered (D-12), (c) rows where trial_selected_delta_id is non-null (D-10) — capped at the D-16 reading scope (~20-30) by truncating with a note rather than silently dropping. Write JSON with indent=2.
  </action>
  <acceptance_criteria>
    - test -f seers_harness/validation/batch_summary_writer.py returns 0
    - python -c "from seers_harness.validation.batch_summary_writer import write_batch_summary" exits 0
    - grep -nE '"manual_review_queue"|"fail_lists"|"totals"' seers_harness/validation/batch_summary_writer.py returns three or more lines
    - End-to-end smoke: python -c "from seers_harness.validation.index_writer import write_index; from seers_harness.validation.batch_summary_writer import write_batch_summary; import tempfile, pathlib, json; d=pathlib.Path(tempfile.mkdtemp()); write_index([{'node_id':'n1','artifact':{'covers_product_ids':[],'transferable_disposition_text':'','user_signal':''},'reflow_triggered':True,'trial_selected_delta_id':'d1','exception':None}], d, 1,'b1','t0','t1',1,1); write_batch_summary(d/'index.json'); s=json.loads((d/'batch_summary.json').read_text()); assert 'n1' in s['manual_review_queue']; assert s['totals']['val02_pass']==0" exits 0
    - grep -nE "20|30" seers_harness/validation/batch_summary_writer.py returns at least one line (cap implementation)
  </acceptance_criteria>
  <done>batch_summary.json aggregates per-VAL machine pass/fail counts and surfaces a bounded manual-review queue covering D-10, D-12, D-13 triggers, capped at the D-16 reading scope.</done>
</task>

</tasks>

<verification>
  - python -c "from seers_harness.validation.machine_judges import judge_val01; from seers_harness.validation.index_writer import write_index; from seers_harness.validation.batch_summary_writer import write_batch_summary" exits 0
  - The sortable columns appear in index.json output exactly as named (verify via the smoke commands above); E2 and E3 are both served by len_transferable_disposition_text at opposite sort directions, documented in the writer docstrings
  - VAL-03_pass is null in machine output — manual review by user is the only path to a verdict per D-13/D-14
</verification>
