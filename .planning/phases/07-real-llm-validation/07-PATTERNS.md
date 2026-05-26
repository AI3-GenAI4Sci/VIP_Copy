# Phase 7: Real-LLM Validation - Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 8 (6 new code/data files + 2 modified)
**Analogs found:** 7 / 8

Pattern mapping is read-only. The only file produced by this agent is this
PATTERNS.md. Source code under `seers_harness/` and `tests/` was not
modified.

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| Stage runner (entry point — D-22(e); planner picks `tests/smoke/test_real_llm_validation.py` OR `seers_harness/validation/real_llm_runner.py` + `__main__.py`) | runner / CLI | batch + request-response | `tests/smoke/test_e2e_smoke.py` (Stages 1+2) **and** `tests/smoke/test_concurrency_smoke.py` (Stage 3) | exact (Stage 1+2), exact (Stage 3) |
| Real-DeepSeek provider construction call site (no new module — call into existing helper) | config / wiring | request-response | `seers_harness/provider_runtime/openai_compatible.py::deepseek_provider_from_env` | exact |
| Evidence-capture wrapper around `_run_node` / `run_skill_via_tools` (writes `messages.jsonl`, `tool_calls.jsonl`, `artifact.json`, `usage.json` per node per request) | runtime decorator / observer | event-driven (per-turn / per-call hook) | `seers_harness/workflow/dag_runner.py::_run_node` (records + trace) **and** `seers_harness/agentic/tool_loop.py::run_skill_via_tools` (messages list + raw_tool_calls echo); persistence shape from `seers_harness/evolution/delta_portfolio.py::write_portfolio_jsonl` | role-match (no existing per-node JSONL writer) |
| `index.json` + `batch_summary.json` writers (machine-readable batch index; D-10) | output emitter / writer | batch transform → file | `seers_harness/evolution/promotion_smoke.py::build_promotion_smoke_report` (canonical JSON dry-run report) | role-match |
| Observability hooks in `seers_harness/evolution/delta_portfolio.py` and `seers_harness/evolution/trial_runner.py` (trial-select event / reflow event / portfolio before-after) | instrumentation hook | event-driven (callback emit) | `seers_harness/workflow/dag_runner.py::WorkflowRuntime.trace` event-append pattern; `seers_harness/evolution/trial_runner.py::run_request_trial` (TrialOutcome construction) | role-match (no existing event-emit hook surface in evolution modules) |
| `evolution_snapshot.json` per-request writer | output emitter / writer | request → file | `seers_harness/evolution/promotion_smoke.py` (single-call build-and-write JSON report) | role-match |
| `case_analysis.md` template (VAL section + F1-F4 sub-headings; only user-confirmed conclusions) | docs / audit artifact | static template | `.planning/phases/06-evolution-chain-production-hardening/06-CONTEXT.md` (sectioned planning doc with locked decision blocks) | partial (no `case_analysis.md` precedent in repo) |
| Stage 3 concurrency=20 runner block | runner | concurrent request fan-out | `tests/smoke/test_concurrency_smoke.py::test_concurrent_fake_provider_requests_do_not_cross_contaminate` | exact |

## Pattern Assignments

### Stage runner — 3-stage real-LLM driver

**Analogs:**
- `tests/smoke/test_e2e_smoke.py` (Stages 1 + 2 — serial scratch-CSV pattern)
- `tests/smoke/test_concurrency_smoke.py` (Stage 3 — concurrency=20 fan-out)
- `tests/smoke/scripted_full_chain.py::make_nodes` (3-node DAG factory; reuse as-is)

**Scratch-CSV scenario selection** (test_e2e_smoke.py L43-L98):
- Constants: `_CSV_PATH = Path(__file__).parents[2] / "data_100k.csv"`,
  `_NUM_REQUESTS = 20`, `_HEADER_SCAN_LIMIT = 1000`.
- One pass over the first ~1000 rows of `data_100k.csv` via
  `csv.reader([line], delimiter=delimiter)`; collect first 20 unique
  `request_id`s in file order plus all rows belonging to those ids; write
  scratch CSV (header + relevant rows) into `tmp_path / "scratch.csv"`.
- Phase 7 stage runner MUST reuse `_select_requests_and_build_scratch`
  (or copy its body) — no parallel selection path (CONTEXT Reusable
  Assets bullet 1).

**Per-request loop shape (Stage 1 N=1, Stage 2 N=20 serial)**
(test_e2e_smoke.py L116-L149):
```python
for i, request_id in enumerate(request_ids):
    print(f"smoke {i + 1}/{_NUM_REQUESTS}: {request_id}")
    scenario = preprocess_request_from_csv(scratch_csv, request_id=request_id)
    provider = build_full_chain_script()                 # SWAP for real DeepSeek in Phase 7
    safe = request_id.replace("/", "_").replace(":", "_")
    request_output_dir = tmp_path / safe
    runtime = make_runtime(request_output_dir, provider) # WRAP runtime with evidence layer in Phase 7
    result = runtime.run_request(scenario=scenario, nodes=make_nodes())
    for node_id, model in [
        ("factor_discovery", FactorDiscoveryArtifact),
        ("copy_generation", CopyGenerationArtifact),
        ("personalized_copy_rubric", PersonalizedCopyRubricArtifact),
    ]:
        path = result[node_id]
        raw = json.loads(path.read_text(encoding="utf-8"))
        model.model_validate(raw)                        # extra="forbid" backstop = VAL-04
```

**Phase 7 swap map for the body above:**
1. Replace `build_full_chain_script()` with
   `deepseek_provider_from_env(max_retries=3)` (D-03).
2. Replace `make_runtime(...)` with a runtime wrapped by the
   evidence-capture layer; output dir is `tests/smoke/.runs/<timestamp>/<safe_request_id>/` (D-09 — `.runs/` is in `.gitignore` line 14).
3. After artifact validation, write per-node `messages.jsonl` /
   `tool_calls.jsonl` / `artifact.json` / `usage.json` and per-request
   `evolution_snapshot.json` (D-08).
4. **Fail-fast at request level (D-02):** any exception or schema
   validation failure terminates the loop immediately; partial
   artifacts already on disk are kept as failure-scene evidence. Do
   NOT wrap the body in a continue-on-error try/except.

**Stage 3 concurrent fan-out** (test_concurrency_smoke.py L163-L179):
```python
request_ids = [f"R-{i:02d}" for i in range(_NUM_REQUESTS)]
results: dict[str, _RequestResult] = {}
with ThreadPoolExecutor(max_workers=_NUM_REQUESTS) as pool:
    futures = {
        pool.submit(_run_one_request, rid, tmp_path): rid for rid in request_ids
    }
    for fut in as_completed(futures):
        rid = futures[fut]
        results[rid] = fut.result()
```

**Phase 7 swap map for Stage 3:**
1. `request_ids` come from the same scratch-CSV pass as Stage 2 (do NOT
   use synthetic `R-00`..`R-19`; the test_concurrency_smoke synthetic
   ids are a fake-provider artifact).
2. Per-thread provider construction: each thread builds its own
   `deepseek_provider_from_env(max_retries=3)` instance; **do not share
   one provider across threads** (test_concurrency_smoke.py L131-138
   contract — fresh `DelayedScriptedProvider` per thread; the same rule
   applies to real provider for harness concurrency safety).
3. `_PER_CALL_DELAY_SECONDS = 0.005` (test_concurrency_smoke.py L71)
   does NOT apply — real DeepSeek provides its own latency.
4. Stage 3 writes evidence into the same per-request layout as
   Stage 2 (one dir per `request_id`); cross-contamination assertions
   (test_concurrency_smoke.py L211-L267) are NOT executed in Stage 3
   (those guard the harness, which Phase 6 already validated; Phase 7
   Stage 3 is real-LLM observation, D-04).
5. Stepping policy is planner discretion (D-22(a)) — one shot at c=20 vs
   stepped 4→8→20.

**Required imports (Stage runner):**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed   # Stage 3 only
from pathlib import Path
import csv, json
from seers_harness.intake.request_preprocessor import (
    detect_delimiter, preprocess_request_from_csv,
)
from seers_harness.provider_runtime.openai_compatible import deepseek_provider_from_env
from seers_harness.workflow.dag_runner import WorkflowRuntime
from seers_harness.domain.models import (
    CopyGenerationArtifact, FactorDiscoveryArtifact, PersonalizedCopyRubricArtifact,
)
from tests.smoke.scripted_full_chain import make_nodes   # only make_nodes; NOT build_full_chain_script
```

**Forbid list for Stage runner:**
- No `ScriptedProvider` / `DelayedScriptedProvider` import (Phase 7 is
  real LLM only — CONTEXT canonical_refs `tests/fakes/scripted_provider.py`
  is "out of Phase 7's runtime path").
- No mutation of `workflow-skills/current/*/SKILL.md` (Phase 4 lock — D-17
  applies via evolution chain only).
- No `harness-runtime/` import (CONTEXT phase boundary).
- No second wrapper retry on top of `max_retries=3` (D-03).
- No single-request token cap (D-06).

---

### Real-DeepSeek provider construction

**Analog:** `seers_harness/provider_runtime/openai_compatible.py::deepseek_provider_from_env` (L148-165).

**Reuse as-is — do not write a new constructor:**
```python
def deepseek_provider_from_env(
    *,
    model: str | None = None,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> OpenAICompatibleProvider:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required for DeepSeek provider")
    timeout = timeout_seconds if timeout_seconds is not None else float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "60"))
    retries = max_retries if max_retries is not None else int(os.environ.get("DEEPSEEK_SDK_MAX_RETRIES", "0"))
    return OpenAICompatibleProvider(
        model=model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        api_key=api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BETA_BASE_URL),
        timeout_seconds=timeout,
        max_retries=retries,
    )
```

**Phase 7 call site:**
```python
# Override env defaults: max_retries=3 per D-03.
provider = deepseek_provider_from_env(max_retries=3)
```

**Locked params on every call** (openai_compatible.py L62-69 — DO NOT
override these in Phase 7 wiring; ADR-PROBE-7.1.1):
```python
params: dict[str, Any] = {
    "model": self.model,
    "messages": messages,
    "tools": tools,
    "tool_choice": "auto",
    "reasoning_effort": "max",
    "extra_body": {"thinking": {"type": "enabled"}},
}
```

**`last_usage` snapshot source** (openai_compatible.py L82, L119-130):
- `provider.last_usage` is set after every `generate_with_tools` call.
- `extract_usage(response)` returns
  `{"prompt_tokens", "completion_tokens", "total_tokens", ...}`.
- Phase 7 evidence-capture reads `provider.last_usage` after each
  tool-loop turn (or once per node on completion) and writes
  `usage.json` per node. Pattern:
```python
# After each tool-loop turn (or once per node, planner discretion D-22(b)):
usage_snapshot = dict(provider.last_usage)  # copy to detach from next turn
```

---

### Evidence-capture wrapper — per-node JSONL persistence

**Analogs:**
- `seers_harness/workflow/dag_runner.py::_run_node` (L60-124) — the
  boundary that owns one tool-loop call per node attempt; trace +
  records pattern.
- `seers_harness/agentic/tool_loop.py::run_skill_via_tools` (L31-98) —
  the multi-turn loop that owns `messages: list[dict]` and the
  `reasoning_content` + `raw_tool_calls` wire-format echo.
- `seers_harness/evolution/delta_portfolio.py::write_portfolio_jsonl`
  (L164-173) — JSONL persistence shape.

**Pattern to copy — runtime trace shape** (dag_runner.py L74-98):
```python
self.trace.append(
    {"type": "provider_call", "node_id": node.id, "session_id": session_id, "attempt": attempt}
)
# ... tool-loop runs ...
self.trace.append(
    {
        "type": "tool_loop_summary", "node_id": node.id, "session_id": session_id,
        "turns_used": result.turns_used,
        "tool_calls_made": result.tool_calls_made,
        "last_reasoning_content": result.last_reasoning_content,
    }
)
```

**Pattern to copy — wire-format echo (full messages trajectory)**
(tool_loop.py L67-88):
```python
# Subsequent turns require BOTH reasoning_content AND original SDK tool_calls shape.
messages.append({
    "role": "assistant",
    "content": result.raw_response_text or None,
    "tool_calls": result.raw_tool_calls,
    "reasoning_content": result.reasoning_content,   # <-- this is the trajectory the auditor reads
})
# ...
for tc in result.tool_calls:
    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": msg})
```
Phase 7 needs the FULL `messages[]` list at end-of-node; the simplest
capture is a wrapper provider whose `generate_with_tools` records a
deep copy of `messages` argument plus the returned `ProviderResult`
fields per call. The `tool_loop` itself is a pure function — a wrapping
provider is the lowest-impact instrumentation point.

**Pattern to copy — JSONL writer** (delta_portfolio.py L164-173):
```python
def write_portfolio_jsonl(path: Path | str, rows: Iterable[DeltaPortfolioRow]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(row.model_dump_json())
            f.write("\n")
```

**Per-request directory layout (D-10):**
```
tests/smoke/.runs/<timestamp>/<safe_request_id>/
├── factor_discovery/
│   ├── messages.jsonl       # one line per turn — full assistant/tool/user dict
│   ├── tool_calls.jsonl     # one line per tool_call — {id, name, arguments}
│   ├── artifact.json        # the validated FactorDiscoveryArtifact
│   └── usage.json           # provider.last_usage snapshot at end-of-node
├── copy_generation/         # same four files
├── personalized_copy_rubric/  # same four files
└── evolution_snapshot.json  # per-request — see next section
```

**Wrapper-shape recommendation (planner discretion D-22(c)/(b)):**
A thin proxy class that takes the real `OpenAICompatibleProvider`,
forwards `generate_with_tools(...)`, and on the way out appends to
in-memory per-call buffers keyed by `node_id`. At end-of-node (after
`runtime.run_request` returns the artifact path), flush buffers to
disk. This avoids any change to `dag_runner.py` and `tool_loop.py`
(CONTEXT integration-points note: "without changing the runner contract").

**Phase 7 wrapper minimum surface (sketch — planner finalizes):**
```python
class EvidenceCapturingProvider:
    def __init__(self, inner: OpenAICompatibleProvider, request_evidence_dir: Path):
        self.inner = inner
        self.request_evidence_dir = request_evidence_dir
        self._per_node_messages: dict[str, list[list[dict]]] = {}  # node_id -> [turn_messages, ...]
        self._per_node_tool_calls: dict[str, list[dict]] = {}
        self._per_node_usage: dict[str, dict] = {}
    @property
    def last_usage(self) -> dict[str, Any]:
        return self.inner.last_usage
    def generate_with_tools(self, *, node_id, skill_bundle, messages, tools):
        result = self.inner.generate_with_tools(
            node_id=node_id, skill_bundle=skill_bundle, messages=messages, tools=tools,
        )
        self._per_node_messages.setdefault(node_id, []).append([dict(m) for m in messages])
        self._per_node_tool_calls.setdefault(node_id, []).extend(result.tool_calls)
        self._per_node_usage[node_id] = dict(self.inner.last_usage)
        return result
    def flush_node(self, node_id: str, artifact_path: Path) -> None:
        # Write messages.jsonl / tool_calls.jsonl / artifact.json / usage.json
        ...
```

**Forbid list for the wrapper:**
- No edit of `dag_runner.py::_run_node` body (CONTEXT integration
  point: "without changing the runner contract").
- No edit of `tool_loop.run_skill_via_tools` (Phase 6 lock; D-06's sole
  death-loop defense).
- No new param to `provider.generate_with_tools` signature
  (provider_runtime/base.py contract).
- No swallowing of `ProviderRateLimitError` / `ProviderTransientError`
  / `ProviderAuthError` — bubble them to Stage runner so D-02
  fail-fast triggers correctly.

---

### `index.json` + `batch_summary.json` writers

**Analog:** `seers_harness/evolution/promotion_smoke.py::build_promotion_smoke_report`
(L89-160).

**Pattern to copy — single-call canonical JSON write** (promotion_smoke.py L132-160):
```python
report: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "run_id": run_id_value,
    "skill_files": skill_files,
    ...
}
output_path_p.parent.mkdir(parents=True, exist_ok=True)
output_path_p.write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
```

**Phase 7 `index.json` shape** (per D-10):
```json
{
  "schema_version": "real-llm-validation.v1",
  "run_id": "...",
  "stage": 1 | 2 | 3,
  "concurrency": 1 | 20,
  "n_requests": 1 | 20,
  "started_at": "...",
  "ended_at": "...",
  "pass_count": 20,
  "fail_count": 0,
  "batch_summary_path": "batch_summary.json"
}
```

**`batch_summary.json` row shape** (per D-10 + D-16 — the four E1-E4
sortable columns are MANDATORY):
```json
{
  "request_id": "...",
  "scenario_id": "...",
  "factor_discovery": {"status": "pass|fail", "tool_call_count": N, "token_usage": {...}},
  "copy_generation":  {"status": "pass|fail", "tool_call_count": N, "token_usage": {...}},
  "personalized_copy_rubric": {"status": "pass|fail", "tool_call_count": N, "token_usage": {...}},
  "reflow_triggered": false,
  "trial_selected": null,
  "trial_delta_id": null,
  "covers_product_ids_len": 0,           // E1 sortable column
  "transferable_disposition_len_min": 0, // E2 sortable column (shortest across factors)
  "transferable_disposition_len_max": 0, // E3 sortable column (longest across factors)
  "literal_overlap_signal_disposition": 0.0  // E4 sortable column
}
```

**Build-on-the-fly vs post-batch:** D-22(d) leaves this to the
planner. Pattern recommendation — append per-request rows to a JSONL
file as each request completes (fail-fast safe; partial batch survives
a Stage 3 mid-run failure), then build the final `batch_summary.json`
by reading the JSONL once at the end. This mirrors
`write_portfolio_jsonl` JSONL-then-load pattern.

---

### Observability hooks in `evolution/delta_portfolio.py` and `evolution/trial_runner.py`

**Match quality:** role-match (no existing event-emit hook surface
inside evolution modules — confirmed by grep across `seers_harness/`).

**Analog for the trace-event-append shape:**
`seers_harness/workflow/dag_runner.py::WorkflowRuntime.trace`
(L57, L74-98) — an in-memory list of dicts that callers can later
serialize. Phase 7 hooks should adopt the same shape.

**Analog for the structural insertion point inside trial_runner.py:**
`seers_harness/evolution/trial_runner.py::run_request_trial`
(L155-203) — the existing function already constructs a `TrialOutcome`
and applies a patch; the hook layer's job is to emit one event per
selection-attempt and one event per outcome.

**Phase 7 hook contract (lightweight, no business-logic change — D-11):**

A single optional `event_sink` parameter accepted by:

1. `select_trial_delta(...)` — emit one
   `{"type": "trial_select", "request_id": ..., "scenario_id": ..., "selected_delta_id": delta_id_or_None, "applicable_surface": [...], "no_trial_reason": "...|None"}` per call.
2. `run_request_trial(...)` — emit one
   `{"type": "trial_outcome", "request_id": ..., "trial_delta_id": ..., "success": bool, "failure_category": "...|None"}` per call.
3. New `delta_portfolio.snapshot_portfolio(rows)` helper — return
   the list as `[row.model_dump() for row in rows]` (no new schema
   field; uses the existing `DeltaPortfolioRow.model_dump()` which is
   already pydantic-v2 + `extra="forbid"`).
4. Reflow event hook: planner identifies the reflow trigger site (per
   Phase 6 cadence; CONTEXT canonical_refs Phase 6 D-22 promotion smoke
   anchor). Emit
   `{"type": "reflow", "request_id": ..., "before_count": ..., "after_count": ...}`.

**Hook implementation pattern (copy from dag_runner trace
append-shape):**
```python
# Inside select_trial_delta — at every return point:
if event_sink is not None:
    event_sink.append(
        {"type": "trial_select", "request_id": ..., "selected_delta_id": ..., ...}
    )
return delta_id
```

**`event_sink` typing:** `list[dict[str, Any]] | None` — matches
`WorkflowRuntime.trace` exactly.

**Forbid list for hook layer:**
- No new pydantic schema for the events (keep them as dicts; consumer
  is `evolution_snapshot.json` writer which serializes via
  `json.dumps`).
- No change to selection logic (`belief_mean`, weights, eligibility
  filter — all unchanged per D-20: trial trigger uses Phase 6's
  portfolio-adaptive logic unmodified).
- No change to `update_after_trial` semantics (pure function — D-26).
- No persistence inside the hooks themselves; persistence lives in
  the per-request `evolution_snapshot.json` writer (next section).

---

### `evolution_snapshot.json` per-request writer

**Analog:** `seers_harness/evolution/promotion_smoke.py::build_promotion_smoke_report`
(L89-160) — same single-call build-and-write JSON pattern.

**Per-request shape** (D-08 + D-11):
```json
{
  "schema_version": "evolution-snapshot.v1",
  "request_id": "...",
  "scenario_id": "...",
  "trial_select_events": [ {"type":"trial_select", ...}, ... ],
  "trial_outcome_events": [ {"type":"trial_outcome", ...}, ... ],
  "reflow_events": [ {"type":"reflow", ...}, ... ],
  "portfolio_before": [ {DeltaPortfolioRow.model_dump()}, ... ],
  "portfolio_after":  [ {DeltaPortfolioRow.model_dump()}, ... ]
}
```

**Construction pattern — copy from `build_promotion_smoke_report`:**
```python
snapshot = {
    "schema_version": "evolution-snapshot.v1",
    "request_id": request_id,
    ...
    "portfolio_before": [r.model_dump() for r in portfolio_before],
    "portfolio_after":  [r.model_dump() for r in portfolio_after],
}
output_path = request_evidence_dir / "evolution_snapshot.json"
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
```

**Important — D-18 expectation:** Stage 1 (N=1) and the early requests of
Stage 2 will almost certainly produce ZERO trials. The snapshot for
those requests has empty `trial_select_events` /
`trial_outcome_events` and identical `portfolio_before` /
`portfolio_after`. This is expected; the writer must NOT skip writing
when the events list is empty.

---

### `case_analysis.md` template

**Match quality:** partial (no existing `case_analysis.md` in the
repo — `grep -r "case_analysis" .` returns nothing).

**Closest structural analog** (sectioned planning doc with locked
decision blocks):
- `.planning/phases/06-evolution-chain-production-hardening/06-CONTEXT.md`
  — `<domain>` / `<decisions>` / `<canonical_refs>` / `<deferred>` blocks.
- `.planning/phases/07-real-llm-validation/07-CONTEXT.md` — current
  phase's CONTEXT (the file the planner is reading right now).

**Phase 7 `case_analysis.md` template skeleton (per D-14 + D-15 + D-16):**
```markdown
# Phase 7 Case Analysis

**Run id:** <to fill in>
**Stage:** 2 (principal evidence) / 3 (concurrency)
**Status:** Draft / User-confirmed

> Only user-confirmed conclusions enter this file. Agent observations
> live in working notes ("待你确认的观察") and migrate here only after
> the user agrees explicitly. (D-14)

## VAL-01 — N=20 stage-2 + N=20 stage-3 accounted for
[Auto-extract from index.json — no case reading needed; D-12 machine-judged.]

## VAL-02 — tool-call count >= 1 per request
[Auto-extract from batch_summary.json — D-12 machine-judged.]

## VAL-03 — reflect_on_coverage / reflect_on_diversity invocation
[Statistics-then-case-analysis. D-13.]

### Stratified sample
- (one factor read per request — covers all 20)

## VAL-04 — Pydantic extra="forbid" + grep gate
[Auto — zero exceptions = pass; D-12 machine-judged.]

## VAL-05 — fake-transferable failure shapes
[Stratified case reading per D-16: at least one factor per request
plus extreme samples by E1-E4.]

### F1: Specific case wrapped in generic-sounding language
- (user-confirmed cases here)

### F2: Causal chain broken between user_side_signal and bridge_to_product
- (user-confirmed cases here)

### F3: Boilerplate-template transferable_disposition text untethered to a real signal
- (user-confirmed cases here)

### F4: covers_product_ids claims multi-product reach but transferable_disposition only explains one
- (user-confirmed cases here)

### Extreme samples read
- E1 (longest covers_product_ids):
- E2 (shortest transferable_disposition):
- E3 (longest transferable_disposition):
- E4 (highest literal overlap signal/disposition):

## VAL-06 — evolution chain reachability under real LLM
[D-13 + D-18 — zero trials in 20 requests is a legitimate observation.]

### Trial selection observations
### Reflow events observed
### Portfolio before/after deltas
```

**Forbid list:**
- No agent-written verdicts (D-14 — anti-sycophancy ADR-01-PRINCIPLE-04).
- No fabricated pass-rate thresholds (D-13 — ADR-01-PRINCIPLE-06).
- No internal-meme examples / numeric thresholds inside the F1-F4
  bodies (ADR-01-PRINCIPLE-03).
- No new failure-shape buckets beyond F1-F4 unless the user adds them
  explicitly (D-15: "Additional shapes may be appended at the user's
  discretion").

---

## Shared Patterns

### Output-directory shape (`.runs/`)

**Source:** D-09 + `.gitignore` line 14 (`.runs/`).

**Apply to:** Stage runner, evidence-capture wrapper,
`index.json` / `batch_summary.json` writers, `evolution_snapshot.json`
writer.

```
tests/smoke/.runs/<UTC-timestamp>/
├── stage1/<safe_request_id>/...   # N=1
├── stage2/<safe_request_id>/...   # N=20 serial
├── stage3/<safe_request_id>/...   # N=20 concurrent
├── index.json                     # one per stage OR one combining all 3 (planner D-22(b))
└── batch_summary.json             # one per stage OR combined
```

**Sanitization (test_e2e_smoke.py L124):**
```python
safe = request_id.replace("/", "_").replace(":", "_")
```

### JSON serialization defaults

**Source:** `seers_harness/evolution/promotion_smoke.py` L156-158.

**Apply to:** all JSON writers in Phase 7 (per-node `artifact.json`,
`usage.json`, `evolution_snapshot.json`, `index.json`,
`batch_summary.json`).

```python
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n",  # sort_keys for diff-friendliness
    encoding="utf-8",
)
```

**Note:** for JSONL streams (`messages.jsonl`, `tool_calls.jsonl`),
follow `delta_portfolio.write_portfolio_jsonl` shape — one
`json.dumps(record)` (not indented) per line.

### Error classification — fail-fast vs trial-isolated

**Source:** `seers_harness/core/errors.py::classify_exception` +
`seers_harness/workflow/dag_runner.py::_run_node` retry-decision branch
(L109-123).

**Apply to:** Stage runner (D-02 + D-19 routing).

```python
from seers_harness.core.errors import classify_exception
info = classify_exception(exc)
# info["category"] in {"rate_limit", "transient_provider", "provider_response",
#                      "auth", "schema_validation", "tool_validation", ...}
```

**D-19 routing decision (Phase 7 specific):**
- `category in {"schema_validation", "tool_validation"}` inside a trial
  ⇒ that trial's host request fails ⇒ stage stops (fail-fast).
- `category in {"rate_limit", "transient_provider"}` inside a trial
  ⇒ recorded against that delta's `belief` / `failure_history`; host
  request continues on the unmodified main path.
- Same categories on the **main** path (not inside a trial) ⇒ Stage runner
  fails the request (D-02). The OpenAI SDK's `max_retries=3` already
  absorbed transient cases below this surface — by the time the
  exception bubbles up, the budget is exhausted.

### Pydantic `extra="forbid"` artifact validation

**Source:** `seers_harness/domain/models.py` (every artifact model has
`model_config = {"extra": "forbid"}`).

**Apply to:** Stage runner artifact-validation block. Pattern (copy
from test_e2e_smoke.py L137-148):
```python
for node_id, model in [
    ("factor_discovery", FactorDiscoveryArtifact),
    ("copy_generation", CopyGenerationArtifact),
    ("personalized_copy_rubric", PersonalizedCopyRubricArtifact),
]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    model.model_validate(raw)   # raises ValidationError on any unknown field — VAL-04 backstop
```

### Single provider path

**Source:** `seers_harness/provider_runtime/openai_compatible.py`
(Phase 2 lock). Phase 6 PATTERNS.md anti-pattern: "No `generate_json`,
`response_format`, polling path".

**Apply to:** evidence-capture wrapper. The wrapper wraps
`OpenAICompatibleProvider`; it does not introduce a second provider
path or call any other API surface.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `case_analysis.md` (in-tree audit artifact) | docs | static template | No `case_analysis.md` precedent in repo. Use the markdown skeleton above (derived from the VAL-01..VAL-06 acceptance shape in CONTEXT D-12..D-16). |
| Observability hook surfaces inside `evolution/delta_portfolio.py` and `evolution/trial_runner.py` | hook | event-driven | No event-emit instrumentation in `seers_harness/evolution/`. Closest pattern is `WorkflowRuntime.trace` (in `workflow/dag_runner.py`); adopt the same `list[dict] | None` shape. |

---

## Metadata

**Analog search scope:**
- `tests/smoke/`
- `seers_harness/{workflow,agentic,provider_runtime,evolution,intake,domain,core,tools}/`
- `.planning/phases/06-*/`
- `.gitignore`

**Files scanned (read in this session):**
- `tests/smoke/test_e2e_smoke.py`
- `tests/smoke/test_concurrency_smoke.py`
- `tests/smoke/scripted_full_chain.py`
- `seers_harness/workflow/dag_runner.py`
- `seers_harness/workflow/progress.py`
- `seers_harness/agentic/tool_loop.py`
- `seers_harness/provider_runtime/openai_compatible.py`
- `seers_harness/evolution/delta_portfolio.py`
- `seers_harness/evolution/trial_runner.py`
- `seers_harness/evolution/promotion_smoke.py`
- `seers_harness/intake/__main__.py`
- `seers_harness/intake/request_preprocessor.py`
- `seers_harness/domain/models.py` (head)
- `seers_harness/core/errors.py`
- `.planning/phases/06-evolution-chain-production-hardening/06-PATTERNS.md`
- `.planning/phases/07-real-llm-validation/07-CONTEXT.md`

**Pattern extraction date:** 2026-05-26
