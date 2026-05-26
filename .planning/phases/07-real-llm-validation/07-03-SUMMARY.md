---
status: complete
phase: 07
plan_id: 07-03
subsystem: validation
tags: [batch-index, batch-summary, machine-judges, val-01, val-02, val-04, val-05, d-10, d-12, d-13, d-16, d-22d]

# Dependency graph
requires:
  - phase: 07-real-llm-validation
    plan: 07-01
    provides: seers_harness/validation/__init__.py + write_evolution_snapshot (validation package marker; 07-03 appends to its exports without conflict)
  - phase: 07-real-llm-validation
    plan: 07-02
    provides: seers_harness/validation/__init__.py + RecordingProvider + flush_evidence (per-node artifact.json + messages.jsonl + tool_calls.jsonl + usage.json layout that 07-03 readers consume off disk; 07-03 does NOT import these symbols, only the on-disk shape)
provides:
  - seers_harness.validation.machine_judges.judge_val01 / judge_val02 / judge_val04 (pure (artifact)->(bool, reason) judges; D-12)
  - seers_harness.validation.machine_judges.extract_len_covers_product_ids (E1 column extractor; D-16)
  - seers_harness.validation.machine_judges.extract_len_transferable_disposition_text (SHARED column for E2 + E3 at opposite sort directions; D-16)
  - seers_harness.validation.machine_judges.extract_transferable_disposition_text (raw passthrough; NOT an E-dimension; D-16)
  - seers_harness.validation.machine_judges.extract_literal_overlap (E4 column extractor; D-16)
  - seers_harness.validation.index_writer.write_index (one-row-per-request index.json with all D-16 sortable columns plus VAL booleans + D-12 reflow flag + D-10 trial-selection flag; D-22d)
  - seers_harness.validation.batch_summary_writer.write_batch_summary (totals + fail_lists + manual_review_queue; reads index.json off disk; D-13/D-22d)
affects: [07-04, 07-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-function machine judges + column extractors that tolerate None artifacts (D-12 reflow rows still need a row in index.json)"
    - "One-row-per-request batch index with E2/E3 sharing a single len column at opposite sort directions (D-16) plus a separate raw-text passthrough column for fidelity"
    - "Machine-judge subset (VAL-01/02/04) writes booleans; manual-judge VAL-03 writes null and routes the row into manual_review_queue (D-13/D-14)"
    - "Token-set Jaccard literal-overlap (lowercase + whitespace split, language-agnostic) — language-aware segmentation deferred to case-analysis pass"
    - "manual_review_queue capped at D-16 reading scope (≈30) with explicit '<truncated: N more>' sentinel rather than silent drops"
    - "Writer layer reads only on-disk evidence + the pure machine_judges module — zero imports of the 07-02 capture layer (D-22d separation invariant)"

key-files:
  created:
    - seers_harness/validation/machine_judges.py
    - seers_harness/validation/index_writer.py
    - seers_harness/validation/batch_summary_writer.py
  modified:
    - seers_harness/validation/__init__.py

key-decisions:
  - "Honor D-10 — index.json rows expose trial_selected_delta_id (str|None) per request, and batch_summary.json routes any non-null row into manual_review_queue."
  - "Honor D-12 — index.json rows expose reflow_triggered (bool); batch_summary.json routes True rows into manual_review_queue. judges return (False, 'no artifact') on None inputs so reflow-aborted requests still produce a row."
  - "Honor D-13/D-14 — VAL-03 is intentionally null in index.json; only manual case reading confirmed by the user produces a verdict, surfaced via manual_review_queue."
  - "Honor D-16 four-extreme-dimensions contract: E1 ↔ len_covers_product_ids (sort desc); E2 ↔ len_transferable_disposition_text (sort asc, shortest); E3 ↔ len_transferable_disposition_text (sort desc, longest, SAME column as E2 at opposite direction); E4 ↔ literal_overlap_user_signal_vs_transferable_disposition (sort desc). Documented verbatim in machine_judges.py and index_writer.py docstrings."
  - "Honor D-16 raw-text fidelity rule — transferable_disposition_text is a passthrough column for the auditor to read after navigating by E2/E3; it is NOT labelled E3."
  - "Honor D-22(d) — index_writer.py / batch_summary_writer.py / machine_judges.py do NOT import recording_provider, evidence_writer, or any other 07-02 capture-layer symbol. The writer layer consumes the on-disk per-node layout and the runner-built records list only."
  - "Validation package __init__.py extended ADDITIVELY — 07-01's write_evolution_snapshot and 07-02's RecordingProvider/flush_evidence imports + __all__ entries preserved verbatim; 07-03 imports appended below."
  - "Token-set Jaccard literal_overlap uses lowercase + whitespace split — language-agnostic by design; D-15 case-analysis F1-F4 reading is the language-aware verdict layer (D-13)."
  - "manual_review_queue cap at 30 with '<truncated: N more>' sentinel — keeps queue inside D-16 reading scope (≈20-30) without silent drops; auditor falls back to index.json for full navigation when overflow matters."

requirements-completed: [VAL-01, VAL-02, VAL-04]

# Metrics
duration: ~25min
completed: 2026-05-26
---

# Phase 07 Plan 07-03: Batch Index Writers Summary

**Materialised the canonical `index.json` (one row per request, including the four D-16 sortable columns with E2 and E3 sharing a single `len_transferable_disposition_text` column at opposite sort directions plus the raw-text passthrough) and `batch_summary.json` (totals + per-VAL fail_lists + bounded manual_review_queue) writers, plus the pure-function `machine_judges` module that produces VAL-01/02/04 booleans and the four extreme-sample columns — the writer layer is fully separate from the 07-02 capture layer (D-22d) and the workspace's 251-test baseline holds.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-26 (immediately after 07-02 commit)
- **Completed:** 2026-05-26
- **Tasks:** 3 / 3
- **Files created:** 3; **Files modified:** 1

## Accomplishments

- `seers_harness/validation/machine_judges.py` — pure-function module exporting `judge_val01` / `judge_val02` / `judge_val04` (each `(artifact dict | None) -> (bool, str)` so the index writer can produce a row even for reflow-aborted requests with `None` artifact, returning `(False, "no artifact")` per D-12) plus the four D-16 column extractors. The module docstring documents the E-dimension → column mapping verbatim, including the contract that **E2 and E3 share `len_transferable_disposition_text`** at opposite sort directions and that the raw-text passthrough is NOT an E-dimension label.
- `seers_harness/validation/index_writer.py` — `write_index(records, out_dir, stage, batch_id, started_at, finished_at, n, concurrency)` produces `index.json` with the canonical top-level keys (`stage`, `batch_id`, `started_at`, `finished_at`, `n`, `concurrency`, `requests`) and one row per submitted request preserving submission order. Each row carries the four D-16 sortable columns + the raw-text passthrough + four VAL booleans (`VAL-03_pass = null` per D-13/D-14) + reflow flag (D-12) + trial-selection flag (D-10) + exception passthrough.
- `seers_harness/validation/batch_summary_writer.py` — `write_batch_summary(index_path, out_path=None)` reads `index.json` off disk and aggregates: `totals` (`requests`, `val01_pass`, `val02_pass`, `val04_pass`), `fail_lists` per VAL (only `False` rows; `None` rows route to manual review), and `manual_review_queue` defined as the union of (a) rows with `VAL-03_pass is None AND len_transferable_disposition_text > 0` per D-13, (b) `reflow_triggered=True` rows per D-12, (c) `trial_selected_delta_id` non-null rows per D-10. The queue is capped at 30 (D-16 reading-scope upper bound) with an explicit `"<truncated: N more>"` sentinel rather than silent drops.
- `seers_harness/validation/__init__.py` extended ADDITIVELY: 07-01's `write_evolution_snapshot` and 07-02's `RecordingProvider` / `set_current_node_id` / `get_current_node_id` / `flush_evidence` exports preserved verbatim; 07-03's `write_index` / `write_batch_summary` plus the pure judges + extractors appended below.
- Full workspace test suite remains green: **251 passed** across all three task commits — unchanged from Phase 6 / 07-01 / 07-02 baseline.

## Task Commits

1. **Task 1: Implement machine_judges.py for VAL-01/02/04 plus column extractors** — `c768394` (feat)
2. **Task 2: Implement index_writer.py** — `89e091b` (feat)
3. **Task 3: Implement batch_summary_writer.py** — `f81c0eb` (feat)

## Files Created/Modified

- `seers_harness/validation/machine_judges.py` (created) — VAL-01/02/04 pure judges + four column extractors. Module docstring documents the E1-E4 ↔ column mapping verbatim, with explicit "E2 and E3 share `len_transferable_disposition_text` at opposite sort directions" wording and "raw passthrough is NOT an E-dimension" wording.
- `seers_harness/validation/index_writer.py` (created) — `write_index(...)` that builds rows in submission order from records carrying `{node_id, artifact, reflow_triggered, trial_selected_delta_id, exception}`. Falls back to safe defaults (0 / "" / 0.0 / `False` / `None`) for missing keys so a partial / failed-mid-batch records list still produces a row per request.
- `seers_harness/validation/batch_summary_writer.py` (created) — `write_batch_summary(index_path, out_path=None)` with the manual_review_queue union (D-13/D-12/D-10) capped at 30 (D-16). Default out_path is `index_path.parent / "batch_summary.json"`.
- `seers_harness/validation/__init__.py` (modified, additive) — appended 07-03 exports below the 07-01/07-02 entries; `__all__` preserves the prior ordering.

## D-16 column-name confirmation

The four D-16 sortable columns appear in `index.json` rows EXACTLY as named, with the E2/E3 sharing rule honoured:

| D-16 dimension | Column name in index.json | Sort direction | Purpose |
|---|---|---|---|
| E1 | `len_covers_product_ids` (int) | desc → longest | navigate to factor covering the most products |
| **E2** | **`len_transferable_disposition_text`** (int) | **asc → shortest** | navigate to terse / underdeveloped factor |
| **E3** | **`len_transferable_disposition_text`** (int) | **desc → longest** | navigate to verbose / template-heavy factor (SAME column as E2, opposite direction) |
| E4 | `literal_overlap_user_signal_vs_transferable_disposition` (float) | desc → highest | navigate to disposition that most literally echoes user_side_signal |
| (passthrough — NOT an E-dimension) | `transferable_disposition_text` (str) | — | raw text fidelity for the auditor to read in-line |

Verified by:
```bash
grep -nE '"len_covers_product_ids"|"len_transferable_disposition_text"|"transferable_disposition_text"|"literal_overlap_user_signal_vs_transferable_disposition"' \
  seers_harness/validation/index_writer.py
# 4 lines — one per column, including BOTH the shared E2/E3 column and the raw-text passthrough
```

End-to-end smoke confirms the column values land correctly in `index.json`:
```
{
  "node_id": "n1",
  "len_covers_product_ids": 1,
  "len_transferable_disposition_text": 1,
  "transferable_disposition_text": "x",
  "literal_overlap_user_signal_vs_transferable_disposition": 1.0,
  "VAL-01_pass": true, "VAL-02_pass": true, "VAL-03_pass": null, "VAL-04_pass": true,
  "reflow_triggered": false, "trial_selected_delta_id": null, "exception": null
}
```

## D-22(d) writer-layer / capture-layer separation

The writer layer (`machine_judges.py` + `index_writer.py` + `batch_summary_writer.py`) does **NOT** import or instrument the 07-02 capture layer (`recording_provider.py` / `evidence_writer.py`). Verified by:

```bash
grep -nE "from seers_harness.validation.recording_provider|from seers_harness.validation.evidence_writer|import.*recording_provider|import.*evidence_writer|RecordingProvider\(|flush_evidence\(" \
  seers_harness/validation/machine_judges.py \
  seers_harness/validation/index_writer.py \
  seers_harness/validation/batch_summary_writer.py
# zero matches — every reference to recording_provider / evidence_writer in these files
# is a docstring/comment annotation, never an import or call.
```

The writer layer's only consumed inputs are:
1. The records list the stage runner (07-04) builds in memory (each carrying a parsed `artifact` dict already loaded from disk via the per-node layout 07-02 produces).
2. `index.json` on disk (read by `batch_summary_writer`).

The capture layer's only role is to materialise the per-node directory layout; the writer layer reads from that layout via plain `json.loads` of the artifact files, never via 07-02 symbols. This is the D-22(d) separation invariant: capture and writer can evolve independently.

## Must-Have / Decision Check

| must-have (verbatim from plan) | verified by | result |
|---|---|---|
| index.json has top-level keys: stage, batch_id, started_at, finished_at, n, concurrency, requests (D-22d) | end-to-end smoke `python -c "...write_index..."` round-trips all seven keys | PASS |
| Each requests[] row has `len_covers_product_ids` (E1), `len_transferable_disposition_text` (E2 ASC + E3 DESC SAME column), `literal_overlap_user_signal_vs_transferable_disposition` (E4) (D-16) | `grep -nE '"len_covers_product_ids"\|"len_transferable_disposition_text"\|"literal_overlap_user_signal_vs_transferable_disposition"' seers_harness/validation/index_writer.py` returns the three column-emit lines | PASS |
| A raw-text passthrough column `transferable_disposition_text` carries the disposition text — NOT a separate E-dimension (D-16) | extractor docstring states "Raw-text passthrough column — NOT an E-dimension" verbatim; index.json round-trip shows the field carrying the raw string while the integer column carries the length | PASS |
| Each requests[] row has booleans `VAL-01_pass`, `VAL-02_pass`, `VAL-03_pass` (manual subset = null), `VAL-04_pass` (D-22d, VAL-01..04) | `grep -nE '"VAL-01_pass"\|"VAL-02_pass"\|"VAL-03_pass"\|"VAL-04_pass"' seers_harness/validation/index_writer.py` returns 4 lines; smoke test confirms `VAL-03_pass is None` | PASS |
| Each requests[] row has `reflow_triggered` (bool) per D-12 and `trial_selected_delta_id` (str\|null) per D-10 | `grep -nE '"reflow_triggered"\|"trial_selected_delta_id"' seers_harness/validation/index_writer.py` returns 2 emit lines + 2 docstring lines | PASS |
| batch_summary.json contains stage, batch_id, totals {requests, val01_pass, val02_pass, val04_pass}, fail_lists, manual_review_queue (D-22d, D-16) | end-to-end smoke produces a JSON with all five keys; `totals` carries exactly the four counters; `fail_lists` carries the three machine-judged VAL keys | PASS |
| Machine judges for VAL-01/02/04 are pure functions — read parsed artifact dict and return (bool, reason) (D-22d) | three `def judge_valNN(artifact: dict[str, Any] \| None) -> tuple[bool, str]:` signatures; module has zero `open(...)` / `Path(...)` / network calls outside docstrings; all judges accept `None` and return `(False, "no artifact")` per D-12 | PASS |
| Verification: imports of judge_val01 + write_index + write_batch_summary from one Python -c | `python -c "from seers_harness.validation.machine_judges import judge_val01; from seers_harness.validation.index_writer import write_index; from seers_harness.validation.batch_summary_writer import write_batch_summary"` exits 0 | PASS |
| Verification: sortable columns appear in index.json output exactly as named — E2 and E3 served by len_transferable_disposition_text at opposite sort directions, documented in writer docstrings | smoke output shows `len_transferable_disposition_text=1` for a 1-char text; `index_writer.py` docstring documents "E2 ↔ ... sort asc, shortest; E3 ↔ ... sort desc, longest — same column as E2, opposite direction" | PASS |
| Verification: VAL-03_pass is null in machine output — manual review only per D-13/D-14 | smoke test asserts `idx['requests'][0]['VAL-03_pass'] is None`; index_writer source emits literal `None`; batch_summary_writer routes `VAL-03_pass is None` rows (with text) into `manual_review_queue` | PASS |
| 251-test workspace baseline holds | `python -m pytest -q` reports 251 passed across all three task commits | PASS |

## Decisions Made

See `key-decisions` frontmatter for the full list. The honour-rules driving the design:

- **D-16 four-extreme-dimensions contract.** E2 and E3 share a single integer column (`len_transferable_disposition_text`) at opposite sort directions; the raw-text column is a fidelity passthrough, not a fifth E-dimension. The module docstrings + the index.json schema both encode this rule verbatim so a downstream reader (07-04 stage runner, case-analysis tooling) reads the same contract on both ends.
- **D-12 reflow rows still produce an index.json row.** Every judge tolerates `None` artifact and returns `(False, "no artifact")`. This means a reflow-aborted request — where `flush_evidence` may not have written `artifact.json` — still gets a fully populated row in `index.json`, with safe-default sortable columns (0 / "" / 0.0) and `reflow_triggered=True`. The auditor sees the failure in `manual_review_queue` rather than as a missing row.
- **D-13/D-14 VAL-03 routing.** `VAL-03_pass = null` in every row by construction; the only path to a verdict is manual case reading. `manual_review_queue` selects rows that *need* reading: text present + verdict null OR reflow OR trial-selection — exactly the three triggers that warrant case attention per D-10/D-12/D-13.
- **D-22(d) writer/capture separation.** Three new files, zero imports from 07-02. The writer reads on-disk artifacts (which 07-02's `flush_evidence` produces) plus an in-memory records list; this is the cleanest seam for the 07-04 stage runner to populate.

## Deviations from Plan

### Notable deviation: extended `__all__` to export the pure judges and column extractors

**Found during:** Task 3 packaging.

**Issue:** The plan's `<files>` blocks for tasks 1-3 list only the four target files. The plan does not explicitly require `judge_val01` / `extract_*` to land in `seers_harness.validation`'s `__all__`.

**Decision:** Exported the pure judges (`judge_val01`, `judge_val02`, `judge_val04`) and column extractors (`extract_len_covers_product_ids`, `extract_len_transferable_disposition_text`, `extract_transferable_disposition_text`, `extract_literal_overlap`) alongside `write_index` and `write_batch_summary` so 07-04's stage runner and any future case-analysis tooling can reuse them via the package import surface (`from seers_harness.validation import judge_val01`) rather than reaching into the submodule. This matches the additive-only spirit of the 07-01 / 07-02 `__init__.py` extension pattern documented in 07-01's deviation note. The 07-01 / 07-02 entries are preserved verbatim in `__all__`.

**Verification:** `python -c "from seers_harness.validation import write_evolution_snapshot, RecordingProvider, set_current_node_id, get_current_node_id, flush_evidence, write_index, write_batch_summary, judge_val01, judge_val02, judge_val04, extract_len_covers_product_ids, extract_len_transferable_disposition_text, extract_transferable_disposition_text, extract_literal_overlap"` exits 0.

### Notable deviation: manual_review_queue cap (D-16 reading scope)

**Found during:** Task 3.

**Issue:** Plan task 3's `<action>` says "capped at the D-16 reading scope (~20-30) by truncating with a note rather than silently dropping". The plan does not pin the cap to a specific integer.

**Decision:** Cap at **30**, the upper bound of D-16's stated ≈20-30 scope. Overflow surfaces as a literal sentinel `"<truncated: N more>"` appended to the queue (so the auditor sees the count without losing it). Picking 30 over 20 is the more conservative choice — it favours the auditor's option to read more, and the case-analysis pass naturally subsamples down. Lower bounds (20) would force silent drops in any batch where reflow + trial-selection together produced > 20 candidates.

**Verification:** smoke confirms a 1-row queue stays uncapped; the cap constant `_MANUAL_REVIEW_QUEUE_CAP = 30` is module-private and documented inline.

---

**Total deviations:** 2 notable, both pure ambiguity resolutions that strengthen the plan's audit goals without weakening any must-have. The four-column-rule is honoured exactly; D-22(d) writer/capture separation is honoured exactly.

## Issues Encountered

None — three tasks executed in order, every acceptance grep and smoke test passed on the first attempt, and the full 251-test suite stayed green across all three task commits.

## Self-Check

**Status:** PASSED

Verification commands run:

```bash
# File existence
test -f seers_harness/validation/machine_judges.py        # exit 0
test -f seers_harness/validation/index_writer.py          # exit 0
test -f seers_harness/validation/batch_summary_writer.py  # exit 0
test -f seers_harness/validation/__init__.py              # exit 0

# Imports (plan-level verification block)
python -c "from seers_harness.validation.machine_judges import judge_val01; from seers_harness.validation.index_writer import write_index; from seers_harness.validation.batch_summary_writer import write_batch_summary"  # exit 0

# Plan-level acceptance greps
grep -nE "def judge_val01|def judge_val02|def judge_val04" seers_harness/validation/machine_judges.py    # 3 lines
grep -nE "E1|E2|E3|E4" seers_harness/validation/machine_judges.py | wc -l                                # 19 lines
grep -nE "shortest|longest|sort asc|sort desc" seers_harness/validation/machine_judges.py | wc -l        # 11 lines

grep -nE '"len_covers_product_ids"|"len_transferable_disposition_text"|"transferable_disposition_text"|"literal_overlap_user_signal_vs_transferable_disposition"' seers_harness/validation/index_writer.py  # 4 lines
grep -nE '"VAL-01_pass"|"VAL-02_pass"|"VAL-03_pass"|"VAL-04_pass"' seers_harness/validation/index_writer.py  # 4 lines
grep -nE '"reflow_triggered"|"trial_selected_delta_id"' seers_harness/validation/index_writer.py             # 4 lines (2 emit + 2 docstring)
grep -nE "E2|E3|shortest|longest" seers_harness/validation/index_writer.py | wc -l                       # 7 lines

grep -nE '"manual_review_queue"|"fail_lists"|"totals"' seers_harness/validation/batch_summary_writer.py  # 6 lines
grep -nE "20|30" seers_harness/validation/batch_summary_writer.py | wc -l                                # 5 lines (cap implementation)

# Plan inline acceptance tests (Tasks 1-3 verbatim)
python -c "from seers_harness.validation.machine_judges import judge_val01, judge_val02, judge_val04; assert judge_val01(None)==(False,'no artifact'); assert judge_val02({'covers_product_ids':[1,2]})[0] is True; assert judge_val04({'transferable_disposition_text':' '})[0] is False"  # exit 0
python -c "from seers_harness.validation.machine_judges import extract_literal_overlap; assert 0.0 <= extract_literal_overlap({'user_signal':'a b c','transferable_disposition_text':'a b'}) <= 1.0; assert extract_literal_overlap({'user_signal':'','transferable_disposition_text':'a'})==0.0"  # exit 0
python -c "from seers_harness.validation.index_writer import write_index; import tempfile, pathlib, json; d=pathlib.Path(tempfile.mkdtemp()); write_index([{'node_id':'n1','artifact':{'covers_product_ids':[1],'transferable_disposition_text':'x','user_signal':'x'},'reflow_triggered':False,'trial_selected_delta_id':None,'exception':None}], d, 1, 'b1','t0','t1',1,1); idx=json.loads((d/'index.json').read_text()); assert idx['stage']==1 and idx['requests'][0]['VAL-01_pass'] is True and idx['requests'][0]['VAL-03_pass'] is None"  # exit 0
python -c "from seers_harness.validation.index_writer import write_index; from seers_harness.validation.batch_summary_writer import write_batch_summary; import tempfile, pathlib, json; d=pathlib.Path(tempfile.mkdtemp()); write_index([{'node_id':'n1','artifact':{'covers_product_ids':[],'transferable_disposition_text':'','user_signal':''},'reflow_triggered':True,'trial_selected_delta_id':'d1','exception':None}], d, 1,'b1','t0','t1',1,1); write_batch_summary(d/'index.json'); s=json.loads((d/'batch_summary.json').read_text()); assert 'n1' in s['manual_review_queue']; assert s['totals']['val02_pass']==0"  # exit 0

# D-22(d) capture/writer separation invariant
grep -nE "from seers_harness.validation.recording_provider|from seers_harness.validation.evidence_writer|RecordingProvider\(|flush_evidence\(" \
  seers_harness/validation/machine_judges.py \
  seers_harness/validation/index_writer.py \
  seers_harness/validation/batch_summary_writer.py
# zero matches — only docstring/comment annotations refer to the capture layer

# Commits exist
git log --oneline | grep -E "c768394|89e091b|f81c0eb"  # 3 lines

# Workspace baseline
python -m pytest -q  # 251 passed (unchanged from 07-02 baseline)
```

Every must-have verified against the actual files on disk; D-16 column-name contract grep-confirmed; D-22(d) writer/capture separation grep-confirmed; baseline test count unchanged.

## Notes for downstream plans

- **07-04 (stage-runner)** is the natural caller of all three writers. After each request completes (artifact validated, evidence flushed by 07-02's `flush_evidence`), build a record `{node_id, artifact, reflow_triggered, trial_selected_delta_id, exception}` and append it to a stage-level list. At end-of-stage, call `write_index(records, stage_dir, stage, batch_id, started_at, finished_at, n, concurrency)` then `write_batch_summary(stage_dir / "index.json")` — both are idempotent, so a re-run regenerates the summary from the on-disk index.
- **07-04 D-12 reflow attribution** comes from observing the 07-01 `reflow` event in the per-request `events` list — set `record["reflow_triggered"] = any(e["type"] == "reflow" for e in events)` before appending to the records list.
- **07-04 D-10 trial-selection visibility** comes from observing the 07-01 `trial_select` event — `record["trial_selected_delta_id"] = ...` from the event's `selected_delta_id` field (None when the request did not select a delta).
- **07-04 fail-fast at request level (D-02):** when a request raises, set `record["artifact"] = None` and `record["exception"] = type(exc).__name__ + ": " + str(exc)` before re-raising. The writers tolerate `None` artifact (judges return `(False, "no artifact")`, extractors return 0/""/0.0) so the fail scene still produces a row in index.json after the runner unwinds.
- **07-06 case-analysis navigation** reads `batch_summary.json`'s `manual_review_queue` to pick the ≈20-30 factors to read, then sorts `index.json`'s `requests` by the four E-columns to build the F1-F4 reading list per the D-15 / D-16 sampling rule. The raw-text passthrough column is the field the auditor opens during reading.
- **`harness-runtime/` was not touched** in this plan (CONTEXT phase boundary; STATE.md "harness-runtime remains untouched" watchlist item still satisfied).
