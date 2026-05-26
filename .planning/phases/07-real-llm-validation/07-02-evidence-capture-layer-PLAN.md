---
phase: 07-real-llm-validation
plan_id: 07-02
wave: 1
depends_on: []
files_modified:
  - seers_harness/validation/__init__.py
  - seers_harness/validation/recording_provider.py
  - seers_harness/validation/evidence_writer.py
autonomous: true
requirements_addressed:
  - VAL-02
  - VAL-03
  - VAL-04
  - VAL-05
skills_used:
  - verification-before-completion
  - claude-api
  - eval-audit
  - gsd-verify-work
---

<objective>
Implement the evidence capture layer: a thin proxy provider that wraps `OpenAICompatibleProvider` and records each invocation's messages, tool_calls, last_usage, and final artifact, plus a per-node JSONL writer that flushes those records to disk in the canonical layout. This is the foundation of every machine-judged and human-judged VAL-XX check — every downstream validator reads from these files. The proxy is content-neutral (it does not interpret messages) and does not alter provider behaviour. Implements D-08 (provider-proxy capture strategy) and D-22(b) (evidence layer is the single source of truth for per-request artifacts).
</objective>

<must_haves>
  <truth>RecordingProvider wraps OpenAICompatibleProvider via composition (not inheritance) and forwards every public method unchanged (D-08).</truth>
  <truth>Every chat-completion call is captured: messages (request), choices/tool_calls (response), and last_usage (token counts) (D-22b).</truth>
  <truth>Per-node JSONL layout is produced under a per-request directory: messages.jsonl, tool_calls.jsonl, artifact.json, usage.json (D-22b).</truth>
  <truth>messages.jsonl contains one JSON object per message in the conversation (role, content); tool_calls.jsonl contains one object per tool_call observed in any assistant response (D-22b).</truth>
  <truth>artifact.json contains the final structured output (the parsed transferable_disposition / signal payload) for downstream machine columns (D-22b).</truth>
  <truth>usage.json records prompt_tokens, completion_tokens, total_tokens, model name (D-22b).</truth>
  <truth>The proxy does not retry, does not classify errors, and does not silently swallow exceptions — those are upstream concerns (D-08).</truth>
</must_haves>

<tasks>

<task type="auto">
  <name>Task 1: Implement RecordingProvider proxy</name>
  <files>seers_harness/validation/__init__.py, seers_harness/validation/recording_provider.py</files>
  <read_first>
    - seers_harness/providers/openai_compatible.py (or equivalent — locate OpenAICompatibleProvider; treat as immutable)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-08 capture strategy, D-22b evidence layout)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (provider proxy pattern, captured-record shape)
  </read_first>
  <action>
    Create seers_harness/validation/recording_provider.py exporting class RecordingProvider. The constructor accepts (inner: OpenAICompatibleProvider, request_log: list[dict]). Implement the public methods of the inner provider by delegation — most importantly chat / chat_completion (whichever the provider exposes). The override wraps the call: capture the outgoing messages list (deep-copied to avoid downstream mutation), invoke inner, then append to request_log a dict with keys: node_id (read from a contextvar or a setter — see Task 2), messages (request copy), response (the raw provider return as a serializable dict), tool_calls (list extracted from response.choices[].message.tool_calls — empty list if absent), last_usage ({prompt_tokens, completion_tokens, total_tokens, model}), final_artifact (the parsed structured output if the provider returns it on a known field, else None — leave None and let the writer fill from response). Exceptions from inner propagate unchanged (no try/except) per D-08. Add a module-level helper set_current_node_id(node_id) backed by contextvars.ContextVar so the stage runner can stamp records without threading an arg through every call.
  </action>
  <acceptance_criteria>
    - test -f seers_harness/validation/recording_provider.py returns 0
    - python -c "from seers_harness.validation.recording_provider import RecordingProvider, set_current_node_id" exits 0
    - grep -nE "ContextVar" seers_harness/validation/recording_provider.py returns at least one line
    - grep -nE "tool_calls" seers_harness/validation/recording_provider.py returns at least one line
    - grep -nE "last_usage|prompt_tokens" seers_harness/validation/recording_provider.py returns at least one line
    - There is NO try/except around the inner provider call — verify by manual read-through and grep -nE "except" seers_harness/validation/recording_provider.py returns 0 within the chat-completion override block
  </acceptance_criteria>
  <done>RecordingProvider transparently proxies the inner provider, appending one fully populated record to request_log per call, without altering provider behaviour or error semantics.</done>
</task>

<task type="auto">
  <name>Task 2: Implement per-node JSONL evidence writer</name>
  <files>seers_harness/validation/evidence_writer.py</files>
  <read_first>
    - seers_harness/validation/recording_provider.py (captured-record shape from Task 1)
    - .planning/phases/07-real-llm-validation/07-CONTEXT.md (D-22b layout)
    - .planning/phases/07-real-llm-validation/07-PATTERNS.md (per-node JSONL layout)
  </read_first>
  <action>
    Create seers_harness/validation/evidence_writer.py exporting flush_evidence(request_log: list[dict], out_dir: str | Path) -> None. For each record in request_log, derive a per-node subdirectory: out_dir / records[i].node_id (fallback to f"req_{i:04d}" if node_id missing). Inside that directory write four files: messages.jsonl (one JSON object per message in record["messages"]); tool_calls.jsonl (one object per tool_call across all assistant messages in the response, or empty file if none); artifact.json (record["final_artifact"] if non-None, else extracted from the last assistant tool_call arguments / message content as best-effort JSON parse, else the raw last assistant message dict); usage.json (record["last_usage"]). Create parent directories with mkdir(parents=True, exist_ok=True). All JSON writes use indent=2 for *.json and newline-delimited compact JSON for *.jsonl. Append-mode is not needed — files are written once per flush. Do not raise on a single malformed record; log to stderr and continue (the runner already failed-fast at request level, so flush is best-effort post-mortem).
  </action>
  <acceptance_criteria>
    - test -f seers_harness/validation/evidence_writer.py returns 0
    - python -c "from seers_harness.validation.evidence_writer import flush_evidence" exits 0
    - grep -nE "messages\.jsonl|tool_calls\.jsonl|artifact\.json|usage\.json" seers_harness/validation/evidence_writer.py returns four or more lines
    - python -c "from seers_harness.validation.evidence_writer import flush_evidence; import tempfile, pathlib, json; d=pathlib.Path(tempfile.mkdtemp()); flush_evidence([{'node_id':'n1','messages':[{'role':'user','content':'hi'}],'response':{},'tool_calls':[],'last_usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2,'model':'x'},'final_artifact':{'ok':True}}], d); assert (d/'n1'/'messages.jsonl').exists(); assert json.loads((d/'n1'/'artifact.json').read_text())['ok'] is True; assert json.loads((d/'n1'/'usage.json').read_text())['total_tokens']==2" exits 0
  </acceptance_criteria>
  <done>flush_evidence produces the exact per-node JSONL/JSON layout required by every downstream validator and case-analysis read.</done>
</task>

</tasks>

<verification>
  - python -c "from seers_harness.validation.recording_provider import RecordingProvider, set_current_node_id; from seers_harness.validation.evidence_writer import flush_evidence" exits 0
  - The proxy passes through unknown attributes/methods via __getattr__ so callers see the inner provider's full surface (verify by grep -nE "__getattr__" seers_harness/validation/recording_provider.py returning at least one line)
  - No top-level I/O or network on import
</verification>
