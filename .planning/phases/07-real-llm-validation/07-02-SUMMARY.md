---
status: complete
phase: 07
plan_id: 07-02
subsystem: validation
tags: [evidence-capture, recording-provider, jsonl, val-02, val-03, val-04, val-05, d-08, d-22b]

# Dependency graph
requires:
  - phase: 07-real-llm-validation
    plan: 07-01
    provides: seers_harness/validation/__init__.py + write_evolution_snapshot (validation package marker; 07-02 appends to its exports without conflict)
  - phase: 02-single-provider-path
    provides: OpenAICompatibleProvider + ProviderResult (the proxy wraps these unchanged)
provides:
  - seers_harness.validation.recording_provider.RecordingProvider (content-neutral proxy around OpenAICompatibleProvider; appends one captured record per generate_with_tools call)
  - seers_harness.validation.recording_provider.set_current_node_id / get_current_node_id (ContextVar-backed node_id stamping seam for the stage runner)
  - seers_harness.validation.evidence_writer.flush_evidence (per-node JSONL/JSON writer for messages.jsonl / tool_calls.jsonl / artifact.json / usage.json)
affects: [07-03, 07-04, 07-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Composition-over-inheritance proxy provider that forwards unknown attributes via __getattr__ and explicitly overrides only generate_with_tools"
    - "Deep-copy of outgoing messages BEFORE the inner call to defeat tool_loop's post-call mutations (the loop appends assistant + tool turns to the same list)"
    - "ContextVar-backed per-call stamping (node_id) — kwarg wins over contextvar; same shape as 07-01's events: list[dict] | None seam family (sink-style observability, no callbacks)"
    - "Per-node directory layout (one dir per node, four files per concern) — follows promotion_smoke.py for *.json (indent=2) and delta_portfolio.write_portfolio_jsonl for *.jsonl (compact newline-delimited)"
    - "Best-effort post-mortem JSON serialisation via _jsonable() that handles dict/list/Pydantic-model_dump/__dict__/repr, so the writer never explodes on stray SDK objects"

key-files:
  created:
    - seers_harness/validation/recording_provider.py
    - seers_harness/validation/evidence_writer.py
  modified:
    - seers_harness/validation/__init__.py

key-decisions:
  - "Honor D-08 — RecordingProvider wraps OpenAICompatibleProvider via composition, not inheritance; no try/except around the inner call (exceptions propagate unchanged); no retry, no error classification, no message interpretation."
  - "Honor D-22(b) — every chat-completion call captures messages (request, deep-copied), response (serialised ProviderResult), tool_calls (parsed shape), last_usage (prompt_tokens/completion_tokens/total_tokens/model), final_artifact (writer falls back to last tool_call arguments when None)."
  - "Per-node layout: messages.jsonl (one JSON object per request message), tool_calls.jsonl (one object per parsed tool_call across the response, empty file when none), artifact.json (final structured output), usage.json (last_usage snapshot)."
  - "ContextVar fallback for node_id stamping — the kwarg passed to generate_with_tools wins; contextvars.ContextVar is the fallback so the stage runner can scope a node without threading node_id through every wrapper layer."
  - "JSON style follows the workspace pattern from seers_harness/evolution/promotion_smoke.py: *.json uses indent=2 + trailing newline; *.jsonl uses compact one-record-per-line (matches delta_portfolio.write_portfolio_jsonl)."
  - "ensure_ascii=False on JSON writes so Chinese reasoning_content / message bodies survive a downstream case-analysis read intact (Phase 7 evidence is read by humans for VAL-05)."
  - "Validation package __init__.py extended ADDITIVELY — 07-01's write_evolution_snapshot import + __all__ entry are preserved verbatim; 07-02 imports are appended below 07-01's, and __all__ keeps the 07-01 entry first."

patterns-established:
  - "Recording-proxy idiom: composition + explicit override of one method + __getattr__ forwarding for everything else; mutate-in-place request_log list (mirrors the events: list[dict] | None sink shape from 07-01)"
  - "Best-effort post-mortem writer idiom: per-record try/except inside the loop body, traceback to stderr, continue; never raise out of flush_evidence so partial evidence on disk survives a malformed record"
  - "Artifact fallback chain idiom: final_artifact -> last tool_call.arguments -> raw_response_text-as-JSON -> raw response dict — keeps the writer informative even when the proxy did not have a chance to record final_artifact explicitly"

requirements-completed: [VAL-02, VAL-03, VAL-04, VAL-05]

# Metrics
duration: 20min
completed: 2026-05-26
---

# Phase 07 Plan 07-02: Evidence Capture Layer Summary

**Added `RecordingProvider` (a content-neutral proxy around `OpenAICompatibleProvider` that captures every `generate_with_tools` call into a per-request log) plus `flush_evidence` (the per-node JSONL/JSON writer producing the canonical `messages.jsonl` / `tool_calls.jsonl` / `artifact.json` / `usage.json` layout); the wrapped provider's outputs are passed through unchanged, exceptions propagate unchanged, and the workspace's 251-test baseline holds.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-26 (immediately after 07-01 commit)
- **Completed:** 2026-05-26
- **Tasks:** 2 / 2
- **Files created:** 2; **Files modified:** 1

## Accomplishments

- `seers_harness/validation/recording_provider.py` — `RecordingProvider(inner, request_log)` proxy. Composition over inheritance; explicit override of `generate_with_tools` only; `__getattr__` forwards every other attribute (including `last_usage`, `model`, `client`) to the inner provider. The override deep-copies outgoing `messages` BEFORE the inner call (because `tool_loop` appends to the same list after the call returns), then appends one fully populated record to `request_log`: `{node_id, messages, response, tool_calls, last_usage, final_artifact}`. **No try/except around the inner call** (D-08): exceptions propagate unchanged.
- `set_current_node_id(node_id)` / `get_current_node_id()` — `contextvars.ContextVar`-backed seam so the stage runner can stamp records without threading `node_id` through every wrapper layer. The kwarg passed to `generate_with_tools` wins; the contextvar is the fallback when the kwarg is `None`.
- `seers_harness/validation/evidence_writer.py` — `flush_evidence(request_log, out_dir)` writes the canonical per-node layout: for each record, a directory named after `node_id` (or `req_<index:04d>` when missing) containing `messages.jsonl` (one JSON object per request message), `tool_calls.jsonl` (one object per parsed tool_call, empty file when none), `artifact.json` (with a fallback chain: `final_artifact` → last tool_call's `arguments` → `raw_response_text` parsed as JSON → raw response dict), and `usage.json` (last_usage snapshot carrying prompt/completion/total_tokens + model). `*.json` uses `indent=2`; `*.jsonl` is compact newline-delimited; `ensure_ascii=False` throughout so Chinese reasoning_content survives.
- Best-effort post-mortem: a single malformed record logs the traceback to `stderr` and continues; the stage runner already failed-fast at request level (D-02), so a flush-time error must not eclipse the genuine evidence on disk.
- `_jsonable()` helper coerces dict / list / Pydantic / dataclass / `__dict__` / fallback-`repr` into JSON-friendly types — the writer never explodes on a stray SDK object.
- `seers_harness/validation/__init__.py` extended ADDITIVELY: 07-01's `write_evolution_snapshot` import + `__all__` entry preserved verbatim; 07-02 imports (`RecordingProvider`, `set_current_node_id`, `get_current_node_id`, `flush_evidence`) appended below.
- Full workspace test suite continues green: **251 passed** (unchanged from Phase 6 / 07-01 baseline).

## Task Commits

1. **Task 1: Implement RecordingProvider proxy** — `914022b` (feat)
2. **Task 2: Implement per-node JSONL evidence writer** — `a286f16` (feat)

## Files Created/Modified

- `seers_harness/validation/recording_provider.py` (created) — `RecordingProvider` class + `set_current_node_id` / `get_current_node_id` ContextVar seam + `_result_to_dict` helper that drops `raw_tool_calls` (SDK objects, not JSON-serialisable) while preserving every other `ProviderResult` field.
- `seers_harness/validation/evidence_writer.py` (created) — `flush_evidence` + `_flush_one` per-record writer + `_resolve_artifact` fallback chain + `_write_jsonl` / `_write_json` low-level writers + `_jsonable` recursive coercer.
- `seers_harness/validation/__init__.py` (modified, additive) — appended 07-02 imports; preserved 07-01's `write_evolution_snapshot` first in `__all__`.

## Must-Have / Decision Check

| must-have (verbatim from plan) | verified by | result |
|---|---|---|
| RecordingProvider wraps OpenAICompatibleProvider via composition (not inheritance) and forwards every public method unchanged (D-08) | `__init__(self, inner, request_log)` stores `inner` directly; `__getattr__` forwards unknown attrs; `generate_with_tools` is the only explicit override and calls `self.inner.generate_with_tools(...)` then returns `result` unchanged. End-to-end smoke confirmed `proxy.last_usage`, `proxy.model`, `proxy.client` all forward to `inner` | PASS |
| Every chat-completion call captures messages (request), choices/tool_calls (response), and last_usage (token counts) (D-22b) | Captured record carries `messages` (deep-copied request), `response` (serialised ProviderResult including tool_calls/finish_reason/reasoning_content), `tool_calls` (parsed shape), `last_usage` ({prompt_tokens, completion_tokens, total_tokens, model}). Smoke test asserted all four keys present with expected values | PASS |
| Per-node JSONL layout produced under a per-request directory: messages.jsonl, tool_calls.jsonl, artifact.json, usage.json (D-22b) | `_flush_one` writes exactly these four filenames into `out_dir / node_id / `; smoke test created two named nodes + one fallback `req_0002` and asserted all four files exist for each | PASS |
| messages.jsonl contains one JSON object per message in the conversation (role, content) | `_write_jsonl(node_dir / "messages.jsonl", messages)` writes one `json.dumps(msg)` line per message; smoke test parsed it back and got the original message list | PASS |
| tool_calls.jsonl contains one object per tool_call observed in any assistant response (D-22b) | Smoke test with two tool_calls produced two newline-delimited JSON objects in the file, names preserved | PASS |
| artifact.json contains the final structured output | Plan inline test (`final_artifact={'ok': True}`) read back `ok: True`. Smoke test with `final_artifact=None` and tool_calls with `submit_factors_final` arguments fell back to those arguments | PASS |
| usage.json records prompt_tokens, completion_tokens, total_tokens, model name (D-22b) | Plan inline test read back `total_tokens == 2` and `model == 'x'`. RecordingProvider also injects `model` from `inner.model` when the SDK didn't echo it back, so `usage.json` always carries the model name | PASS |
| The proxy does not retry, does not classify errors, and does not silently swallow exceptions (D-08) | `grep -nE "^\s*except\b\|^\s*try\s*:"` returns no matches at code level. Smoke test confirmed a `Boom` exception raised by the inner provider propagates unchanged AND the request_log stays empty (record built post-call, never appended on the failure path) | PASS |
| Verification: import RecordingProvider, set_current_node_id, flush_evidence in one Python -c | `python -c "from seers_harness.validation.recording_provider import RecordingProvider, set_current_node_id; from seers_harness.validation.evidence_writer import flush_evidence"` exited 0 | PASS |
| Verification: __getattr__ forwards unknown attributes/methods | `grep -nE "__getattr__" seers_harness/validation/recording_provider.py` returns line 89 (the method definition); smoke test asserted `proxy.last_usage`, `proxy.model`, `proxy.client` all forward | PASS |
| Verification: no top-level I/O or network on import | Import succeeded with zero side effects in repeated tests; no `open()`, `Path(...).write_*`, or network calls at module top level — all `write_text`/`write` calls live inside function bodies (lines 74/147/148/153 in evidence_writer.py; recording_provider.py has none) | PASS |
| Plan inline acceptance test passes verbatim (Task 2) | `python -c "from seers_harness.validation.evidence_writer import flush_evidence; import tempfile, pathlib, json; d = pathlib.Path(tempfile.mkdtemp()); flush_evidence([{...}], d); assert (d/'n1'/'messages.jsonl').exists(); assert json.loads((d/'n1'/'artifact.json').read_text())['ok'] is True; assert json.loads((d/'n1'/'usage.json').read_text())['total_tokens']==2"` exits 0 | PASS |
| 251-test workspace baseline holds | `python -m pytest -q` reports 251 passed across both task commits | PASS |

## Confirmation: wrapped provider behaviour is unchanged

The plan's central D-08 invariant is "the wrapped provider's outputs are passed through unchanged." Concretely verified:

- **Return value identity:** `generate_with_tools` ends with `return result`; `result` is the exact `ProviderResult` instance the inner provider returned. The proxy never constructs a new `ProviderResult` and never copies fields out of one. Smoke tests confirmed `result.finish_reason`, `result.tool_calls`, `result.reasoning_content` are all the inner provider's values.
- **Exception identity:** No `try`/`except` exists in `generate_with_tools`. A `Boom` raised by the inner provider arrives at the caller unchanged (smoke test asserted `str(exc) == "upstream"`).
- **Side-effect identity:** The proxy deep-copies the `messages` list **before** passing it to `inner.generate_with_tools`, but passes the **original** `messages` (not the copy) to the inner. This means the inner provider sees and mutates the same list the harness's `tool_loop` is using — preserving Phase 3's wire-format echo contract. (The deep-copy is the proxy's *own* snapshot, used only for the captured record.)
- **`last_usage` identity:** The proxy never writes to `inner.last_usage`. It reads `inner.last_usage` after the call to build the captured `usage` dict; the inner provider's attribute is unchanged.
- **Surface identity:** `__getattr__` forwards every non-overridden attribute to `inner`, so callers can inspect `proxy.last_usage`, `proxy.model`, `proxy.client`, etc., and see the inner provider's values directly.

No retry, no error classification, no message interpretation, no silent exception swallowing — exactly per D-08.

## Decisions Made

See `key-decisions` frontmatter for the full list. The two honour-rules drove the design:

- **D-08 content-neutrality.** RecordingProvider is a *recorder*, not a *transformer*. The override appends one record per call and otherwise stays out of the way: no exception handling around the inner call, no message inspection, no retry, no field mutation. The downstream stage runner (07-04) is the right layer for fail-fast / D-19 routing decisions; the proxy hands it a complete captured record and a propagated exception.
- **D-22(b) evidence layout as single source of truth.** The per-node `messages.jsonl` / `tool_calls.jsonl` / `artifact.json` / `usage.json` quartet is the layout every downstream validator (07-03 batch index, 07-04 stage runner, case-analysis read for VAL-05) reads from. The writer's job is to materialise that layout deterministically from the captured `request_log`. The artifact fallback chain (`final_artifact` → last tool_call `arguments` → `raw_response_text` JSON → raw response dict) ensures auditors always see *something* useful even when the stage runner did not have a chance to set `final_artifact` explicitly.

## Deviations from Plan

### Notable deviation: artifact.json fallback when final_artifact is None

**Found during:** Task 2 / Task 1 boundary.

**Issue:** Task 1's `<action>` says: "final_artifact (the parsed structured output if the provider returns it on a known field, else None — leave None and let the writer fill from response)." Task 2's `<action>` says: "artifact.json (record["final_artifact"] if non-None, else extracted from the last assistant tool_call arguments / message content as best-effort JSON parse, else the raw last assistant message dict)."

The two clauses are consistent — Task 1 leaves `final_artifact` as `None`, Task 2 fills it. The plan-level inline acceptance test (`final_artifact={'ok': True}`) only exercises the explicit-final-artifact path, not the fallback.

**Resolution (no plan conflict; documenting for downstream readers):** Implemented the fallback chain `final_artifact → last tool_call.arguments → raw_response_text parsed as JSON → raw response dict`. The chain prefers structured (parsed) data over raw text, and the proxy already pre-parses `tool_call.arguments` via the inner provider's `_parse_args`, so the typical path produces a clean dict for the auditor. Smoke-tested with `final_artifact=None` and two tool_calls (`record_factor`, `submit_factors_final`); `artifact.json` correctly contained `{"factors": [{"id": "f1"}]}` (the last tool_call's arguments).

### Notable deviation: ensure_ascii=False on all JSON writes

**Found during:** Task 2 implementation.

**Issue:** The plan does not pin a Unicode policy for the JSON writer. `seers_harness/evolution/promotion_smoke.py` (the JSON-defaults pattern source) uses `json.dumps(report, indent=2, sort_keys=True)` without `ensure_ascii=False`, which would escape non-ASCII to `\uXXXX`.

**Why this conflicts with Phase 7 audit needs:** Phase 7's evidence is read by **humans** for VAL-05 (fake-transferable case analysis). The evidence captures `reasoning_content` and `messages[]` content from real DeepSeek calls — these are Chinese-heavy. Escaped Unicode (`你好`) is unreadable in a case-analysis pass and forces the auditor to re-decode every line. This contradicts D-14 (case-analysis is the audit verdict for VAL-03/05/06) and D-22b (the evidence layer is the single source of truth for per-request artifacts).

**Decision (per orchestrator's "closest to existing code style + plan ambiguity → record the call" guidance):** Use `ensure_ascii=False` on every JSON write inside `evidence_writer.py`. Also dropped `sort_keys=True` because the per-node layout is read sequentially (messages.jsonl in turn order, tool_calls.jsonl in invocation order); preserving the natural key order from the captured record is more useful than alphabetical sort, and the auditor diffs files within a single run rather than across runs.

**Verification:** Smoke test wrote a record with Chinese-content message and round-tripped it back through `json.loads` correctly. `usage.json` and `artifact.json` are deterministic by record content (no dict-ordering instability has been observed in CPython 3.11+).

---

**Total deviations:** 2 notable, both pure ambiguity resolutions that strengthen the plan's audit goals without weakening any must-have. Down-stream consumers (07-03 / 07-04) read fully deterministic per-node layouts whose Unicode is human-legible.

## Issues Encountered

None — both tasks executed in order, every acceptance grep and inline test passed on the first attempt, and the full 251-test suite stayed green across both task commits.

## Self-Check

**Status:** PASSED

Verification commands run:

```bash
# File existence
test -f seers_harness/validation/recording_provider.py  # exit 0
test -f seers_harness/validation/evidence_writer.py     # exit 0
test -f seers_harness/validation/__init__.py            # exit 0

# Imports
python -c "from seers_harness.validation.recording_provider import RecordingProvider, set_current_node_id"  # exit 0
python -c "from seers_harness.validation.evidence_writer import flush_evidence"                            # exit 0
python -c "from seers_harness.validation import RecordingProvider, set_current_node_id, get_current_node_id, flush_evidence, write_evolution_snapshot"  # exit 0

# Plan-level acceptance greps
grep -nE "ContextVar" seers_harness/validation/recording_provider.py                # 5 lines (incl. import + usage)
grep -nE "tool_calls" seers_harness/validation/recording_provider.py                # 9 lines
grep -nE "last_usage|prompt_tokens" seers_harness/validation/recording_provider.py  # 7 lines
grep -nE "^\s*except\b|^\s*try\s*:" seers_harness/validation/recording_provider.py  # 0 (no try/except in code)
grep -nE "__getattr__" seers_harness/validation/recording_provider.py               # 5 lines (incl. method def at line 89)
grep -nE "messages\.jsonl|tool_calls\.jsonl|artifact\.json|usage\.json" seers_harness/validation/evidence_writer.py  # 14 lines (>= 4 required)

# Plan inline acceptance test (Task 2 verbatim)
python -c "from seers_harness.validation.evidence_writer import flush_evidence; import tempfile, pathlib, json; d=pathlib.Path(tempfile.mkdtemp()); flush_evidence([{'node_id':'n1','messages':[{'role':'user','content':'hi'}],'response':{},'tool_calls':[],'last_usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2,'model':'x'},'final_artifact':{'ok':True}}], d); assert (d/'n1'/'messages.jsonl').exists(); assert json.loads((d/'n1'/'artifact.json').read_text())['ok'] is True; assert json.loads((d/'n1'/'usage.json').read_text())['total_tokens']==2"
# exit 0

# E2E proxy → flush_evidence smoke (RecordingProvider with FakeInner, two named nodes + one fallback req_0002)
python <inline-script>  # PASS — all 12 expected files written, contents match expectations

# Commits exist
git log --oneline | grep -E "914022b|a286f16"  # 2 lines

# Workspace baseline
python -m pytest -q  # 251 passed (unchanged from 07-01 baseline)
```

All must-haves verified against the actual files on disk; baseline test count unchanged across both task commits.

## Notes for downstream plans

- **07-03 (batch-index-writers)** consumes the per-node directories produced by `flush_evidence`. Each request's per-node `usage.json` carries `prompt_tokens` / `completion_tokens` / `total_tokens` / `model`; aggregate by reading these files. `tool_calls.jsonl` line count gives the per-node tool-call count for VAL-02 and the four E1-E4 sortable columns can be derived from `artifact.json` (`covers_product_ids` length, `transferable_disposition` length, literal-overlap with `user_side_signal`).
- **07-04 (stage-runner)** is the natural caller of `RecordingProvider`: build the inner provider via `deepseek_provider_from_env(max_retries=3)`, wrap with `RecordingProvider(inner, request_log)`, drive the harness with the wrapped provider for one request, then call `flush_evidence(request_log, request_evidence_dir)` at end-of-request. Use `set_current_node_id` to scope each node's records — restore via `ContextVar.reset(token)` once the node boundary closes.
- **07-04 D-19 routing** integrates with the proxy's exception-pass-through: a `ProviderRateLimitError` / `ProviderTransientError` from the inner provider arrives at the stage runner unchanged; the runner reads `request_log` (already populated for prior successful calls in the same request) before deciding to fail-fast (schema/protocol) or record-against-belief (transient/rate-limit).
- **07-04 final_artifact stamping (optional):** if the runner has the validated artifact dict in hand after `runtime.run_request` returns, it can set `request_log[-1]["final_artifact"] = artifact_dict` *before* calling `flush_evidence` — `_resolve_artifact` will use the explicit value instead of the tool_call-arguments fallback. The fallback path keeps the writer informative when this stamping step is skipped.
- **`harness-runtime/` was not touched** in this plan (CONTEXT phase boundary; STATE.md "harness-runtime remains untouched" watchlist item still satisfied).
