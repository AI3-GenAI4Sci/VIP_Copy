---
phase: 02-single-provider-path
plan: 02
slug: openai-compatible-rewrite
status: complete
wave: 2
completed: 2026-05-25
requirements_satisfied:
  - PROV-01
  - PROV-02
  - PROV-03
  - PROV-04
  - PROV-05
  - PROV-06
must_haves_verified: 6
tests_green: 19
key_files:
  created:
    - project/seers_harness/provider_runtime/openai_compatible.py
    - project/tests/test_provider_openai_compatible.py
    - project/tests/test_provider_line_budget.py
  modified:
    - project/tests/conftest.py
---

# Plan 02-02 — OpenAI-Compatible Provider Rewrite (Wave 2) — SUMMARY

## Goal

Collapse the c16 dual-path provider (246 lines, two entry points, per-node
policy machinery, JSON-mode branching) into a single tool-use adapter exposing
ONLY `generate_with_tools(*, node_id, skill_bundle, messages, tools) ->
ProviderResult`. Hard-code the four ADR-PROBE-7.1 runtime params, route
exceptions via `classify_exception`, parse tool-call arguments to dicts at
the adapter boundary, and come in under the 150-line PROV-06 budget. Real LLM
calls deferred to Phase 7; Phase 2 tests use a `FakeOpenAIClient` injected by
monkeypatching the LOCAL module symbol before construction.

## Tasks executed

| Task | Status | Tests | Notes |
|------|--------|-------|-------|
| 1 — RED: write 13 behavior + 6 static tests; extend conftest with `fake_openai_client` + `fake_openai_response` fixtures | done | both new files RED (ModuleNotFoundError + FileNotFoundError); 80 prior tests still green (zero regression from conftest extension) | Fixtures use stdlib `types.SimpleNamespace` only — no `openai` SDK import in the test layer. `_FakeOpenAIClient.queue_response` / `queue_exception` give ergonomic per-test setup. Usage SimpleNamespace deliberately omits `model_dump` so `extract_usage`'s attribute-fallback branch is exercised. |
| 2 — GREEN: write `openai_compatible.py` (142 visible lines, 8 under the 150 budget) | done | 19/19 new green; 99/99 full suite green | One class + three module-level helpers (`_parse_args`, `extract_usage`, `deepseek_provider_from_env`). Three anchoring comments (`# PROV-03`, `# PROV-04`, `# PROV-05`). c16's 246-line file reduced by ~42%. |

## PROV-* coverage matrix

| Requirement | Test file(s) | Key tests | Static evidence |
|---|---|---|---|
| **PROV-01** Single entry point — `generate_with_tools` only, `generate_json` deleted | `test_provider_openai_compatible.py`, `test_provider_line_budget.py` | All 13 behavior tests call `generate_with_tools`; `test_openai_compatible_defines_generate_with_tools` + `test_openai_compatible_does_not_define_generate_json` | `grep -c 'def generate_with_tools' = 1`; `grep -c 'def generate_json' = 0` |
| **PROV-02** No `response_format` parameter — schema enforcement lives in `tools` arg layer | `test_provider_openai_compatible.py`, `test_provider_line_budget.py` | `test_generate_with_tools_does_not_pass_response_format` (kwargs assertion); `test_openai_compatible_does_not_reference_response_format` (source text) | `grep -c 'response_format' = 0` |
| **PROV-03** Runtime params locked — no per-turn / per-node branching | `test_provider_openai_compatible.py`, `test_provider_line_budget.py` | `test_generate_with_tools_passes_locked_runtime_params_every_call` (2 distinct calls, same kwargs); `test_deepseek_provider_from_env_uses_beta_base_url` (base_url default); `test_openai_compatible_does_not_define_node_generation_policy_class` + `test_openai_compatible_locked_runtime_strings_in_source` | Superseded by Phase 2.1: literals are now `tool_choice="auto"`, `reasoning_effort="max"`, `"thinking": {"type": "enabled"}` |
| **PROV-04** Exception classification → typed errors; unknown re-raises | `test_provider_openai_compatible.py` | `test_rate_limit_error_routes_to_provider_rate_limit_error` (with `__cause__` chain), `test_transient_error_routes_to_provider_transient_error`, `test_auth_error_routes_to_provider_auth_error`, `test_unknown_error_reraises_original` | `classify_exception` invoked verbatim in the try/except block; typed errors raise `from exc` to preserve `__cause__` |
| **PROV-05** `tool_calls` populated with parsed-argument dicts; empty list on stop; bad JSON → `ProviderResponseError` | `test_provider_openai_compatible.py` | `test_generate_with_tools_returns_provider_result_with_tool_calls`, `test_generate_with_tools_returns_empty_tool_calls_on_stop`, `test_arguments_are_parsed_to_dict_not_raw_string`, `test_arguments_parse_failure_raises_provider_response_error`, `test_last_usage_extracted_after_call` | `_parse_args` parses at the adapter boundary; `payload={}` is the back-compat slot; tool_calls is the channel |
| **PROV-06** Line budget ≤ 150 visible lines | `test_provider_line_budget.py` | `test_openai_compatible_line_count_at_most_150` | `awk 'NF && !/^[[:space:]]*#/' | wc -l = 142` — 8 lines under budget |

## c16 symbols deleted (zero-occurrence in c17 source)

| Symbol | Reason for deletion | PROV |
|---|---|---|
| `def generate_json` (and its ~80-line body) | Two entry points violate single-path invariant | PROV-01 |
| `response_format` (kwarg, literal string) | Schema enforcement lives in `tools` arg layer with `strict: True` | PROV-02 |
| `class NodeGenerationPolicy` (import + usage) | No per-node branching; runtime params identical every turn | PROV-03 |
| `def policy_for_node` (method) | Same | PROV-03 |
| `DEFAULT_DEEPSEEK_NODE_POLICIES` (module-level constant) | Same | PROV-03 |
| `def parse_node_policies_json` | Same | PROV-03 |
| `def load_node_policies_from_env` | Same | PROV-03 |
| `def normalize_reasoning_effort` | `reasoning_effort` is hard-coded to `"high"` per probe | PROV-03 |
| `DEEPSEEK_NODE_POLICIES_JSON` env var | No per-node config | PROV-03 |
| `DEEPSEEK_NODE_POLICIES_PATH` env var | Same | PROV-03 |
| `thinking` kwarg on `__init__` (and `self.thinking`) | Always enabled inside `generate_with_tools` | PROV-03 |
| `reasoning_effort` kwarg on `__init__` (and `self.reasoning_effort`) | Always `"high"` inside `generate_with_tools` | PROV-03 |
| `max_tokens` kwarg on `__init__` (and `self.max_tokens`) | No longer used — tool-mode supersedes | PROV-03 |
| `node_policies` kwarg on `__init__` (and `self.node_policies`) | No per-node branching | PROV-03 |
| `temperature` parameter anywhere | Tool-mode does not consume `temperature` | PROV-02/03 |
| `self.timeout_seconds` / `self.max_retries` instance attrs | Stored only on the constructed `client`, not re-exposed | (housekeeping) |

c16 file: 246 lines → c17 file: 142 visible lines = **42% reduction**.

## Architectural notes / deviations

1. **`from openai import OpenAI` at module top, not lazy inside `__init__`.** c16 had `from openai import OpenAI` inside `__init__` (line 41) to keep the SDK import lazy. c17 hoists it to module top so the monkeypatch-on-local-symbol pattern works (`monkeypatch.setattr("seers_harness.provider_runtime.openai_compatible.OpenAI", ...)`). This is the canonical injection pattern for `from x import Y` imports — the only one that actually rebinds the symbol the impl uses. Patching `openai.OpenAI` would not work because the impl's local binding is set at import time and never re-read from the `openai` module. Trade-off: the SDK is imported at process start even when no provider is constructed. Acceptable — `openai` is a hard dependency of the package anyway.

2. **`node_id` is referenced only in the `ProviderResponseError` message; `skill_bundle` is accepted but never read in this layer.** Both are kept on the signature per the Plan 01 Protocol contract. `node_id` powers a traceability string when `_parse_args` rejects truncated JSON; `skill_bundle` is reserved for future logging hooks. Neither is dropped via `del` or `_unused` rename — both are honest signature parameters. A one-line comment marks this intent.

3. **`__init__.py` was NOT modified.** PLAN line 251 acceptance criterion: "No edits to any file outside `project/seers_harness/provider_runtime/openai_compatible.py`." The orchestrator prompt mentioned "append `OpenAICompatibleProvider` + `deepseek_provider_from_env` to re-exports" as guidance, but the PLAN body is the contract — and all Plan 02-02 tests already import directly from the submodule (`from seers_harness.provider_runtime.openai_compatible import ...`), not via the package surface. Re-export can be added in a Phase 3 housekeeping commit if `tool_loop` benefits from a shorter import — flagging as deferred (see Open questions #3 below).

4. **`extract_usage` is module-level, not a method.** Same reasoning as Plan 01 SUMMARY's Open question #1: the function's signature depends on the openai SDK's `ChatCompletion.usage` shape and would force a soft SDK import at the `base.py` Protocol layer if pulled up. Lives in `openai_compatible.py` as a public helper for callers that want raw usage extraction.

5. **`_parse_args` raises `ProviderResponseError` with the first 200 chars of the malformed JSON.** Truncation prevents log-flooding when DeepSeek emits a giant garbled tool-call arguments string. The 200-char cap matches c16's choice for `generate_json`'s body-truncation policy (c16 line 130 used 500 chars; c17 uses 200 because `tool_call.arguments` is per-call, not per-response, so more frequent and shorter signal is preferable).

6. **Line budget: 142/150 = 8 lines slack.** Under budget by 5.3%. Slack is reserved for future Phase-3 traceability comments (e.g., per-call structured log lines, or one extra comment if PROV-04 routing becomes more nuanced when LOOP-03's retry budget lands). Three anchoring comments retained: `# PROV-03: ...`, `# PROV-04: ...`, `# PROV-05: ...`. No further compression attempted — budget met without obfuscation.

## Principle 14 four-question self-audit

Per `master_plan.md` Principle 14:

1. **Is every line load-bearing?** Yes. The class body contains `__init__` (constructor) + `generate_with_tools` (the sole entry). Helpers (`_parse_args`, `extract_usage`, `deepseek_provider_from_env`) are each consumed: `_parse_args` by `generate_with_tools`; `extract_usage` by `generate_with_tools`; `deepseek_provider_from_env` by future Phase-3 `dag_runner` wiring and one Plan 02-02 test (`test_deepseek_provider_from_env_uses_beta_base_url`). Three comments anchor PROV-03/04/05 in source for code review traceability. Module docstring is 6 lines — minimum for explaining ADR-PROBE-7.1 lock + Phase 7 deferral.

2. **Could I delete this line and still satisfy PROV-01..06?** No, except for the three PROV comments — which I keep for code review traceability. Removing `_parse_args` would force `generate_with_tools` to inline JSON parse + error mapping (~6 lines saved on the helper but ~5 added inline = net 1 line saved, at the cost of testability isolation). Removing `extract_usage` would force inline `getattr` chain (~5 lines saved on the helper but ~5 added inline = neutral, at the cost of `last_usage` being harder to override). Removing `deepseek_provider_from_env` would push env-wiring to Phase 3's `dag_runner` (PROV-03 base_url default would still need to be enforced somewhere — net wash). Kept as-is.

3. **Is any decision split across multiple places?** No. The 4 locked runtime params live in exactly ONE dict literal (`params: dict[str, Any] = {...}` in `generate_with_tools`). The base_url default lives in exactly ONE constant (`DEEPSEEK_BETA_BASE_URL`) referenced by both `__init__` (fallback) and `deepseek_provider_from_env` (env fallback). Exception classification routing lives in exactly ONE try/except block, with the unknown branch as a bare `raise` (not duplicated in the helpers). Field order of `ProviderResult` is owned by `base.py` (Plan 01); this file consumes it via keyword-construction.

4. **Did I add abstraction beyond what the tests demand?** No. Five module-level symbols (one class + four functions/constants): `DEEPSEEK_BETA_BASE_URL`, `OpenAICompatibleProvider`, `_parse_args`, `extract_usage`, `deepseek_provider_from_env`. Each is referenced by at least one test directly or transitively. No interface/protocol wrappers, no factory factories, no policy layers. The deletion of `NodeGenerationPolicy` is itself an abstraction REDUCTION (c16's premature generality).

## Phase 7 confirmation points

When Phase 7 wires this to real DeepSeek, confirm:

1. **Model default `deepseek-chat`** (not c16's `deepseek-v4-pro`). The probe (`research/probe_reasoning_with_tools_result.md`) targets `deepseek-chat`; the default in `deepseek_provider_from_env` was switched to match. If DeepSeek announces a `deepseek-v4-pro` GA later, update via `DEEPSEEK_MODEL` env var first, then bump the default in this file.

2. **Base URL `https://api.deepseek.com/beta`**. The `/beta` path is strict mode (probe §9 Q6). Phase 7 must verify the key has `/beta` access — if not, set `DEEPSEEK_BASE_URL=https://api.deepseek.com` via env, and confirm reasoning + tools still coexist on the non-beta endpoint (the probe row "standard + reasoning" shows it does).

3. **Superseded by Phase 2.1:** runtime now uses `reasoning_effort="max"` with `deepseek-v4-pro` per ADR-PROBE-7.1.1.

4. **`extra_body={"thinking":{"type":"enabled"}}`.** This is a DeepSeek-specific extra; OpenAI's own SDK ignores extras but DeepSeek's `/beta` requires this dict to actually enable thinking. Phase 7 should assert `response.choices[0].message.reasoning_content` is non-empty after a real call — if empty, the `thinking` dict was dropped somewhere in the SDK / proxy chain.

5. **No `temperature` in params.** Runtime omits it entirely — `tool_choice="auto"` + `reasoning_effort="max"` are the only generation knobs. A future temperature change is a separate design delta.

6. **`max_tokens` is absent.** c16 carried `max_tokens` for both paths. c17 omits it — Phase 3's `tool_loop` per-turn token accounting via `last_usage` is the budget mechanism. Phase 7 should confirm no DeepSeek default-cap surprises (e.g., 4096-token default cutoffs) by inspecting `finish_reason` — if `finish_reason == "length"` appears in production, reconsider re-adding `max_tokens`.

## Open questions for Phase 3 (tool_loop)

1. **`tool_loop` retry policy for typed errors.** When `generate_with_tools` raises `ProviderRateLimitError` / `ProviderTransientError`, does the tool_loop apply LOOP-03's `max_transient_retries_per_turn=2` budget and re-call the provider, or does it surface the error to `dag_runner` immediately? Recommendation: retry in-loop only for those two retryable categories; surface `ProviderAuthError` (non-retryable) and unknown re-raises directly. The `provider.last_usage` dict is set on every successful call only — retries should NOT accumulate `last_usage` (Phase 3 must accumulate at the tool_loop layer, not rely on adapter mutation).

2. **`finish_reason == "stop"` with empty `tool_calls`.** Plan 01-derived contract says this is the "loop terminates" signal. The adapter returns `ProviderResult(tool_calls=[], finish_reason="stop", ...)` cleanly — does the tool_loop raise `ToolLoopError` per LOOP-03 in this case, or does it accept a stop without a final-submit tool call as a degenerate-but-valid terminal? Plan 03 PLAN.md must lock the semantics.

3. **Add `OpenAICompatibleProvider` + `deepseek_provider_from_env` to `provider_runtime/__init__.py`?** Currently `tool_loop.py` would need `from seers_harness.provider_runtime.openai_compatible import OpenAICompatibleProvider` (full path). Phase 3 may prefer `from seers_harness.provider_runtime import OpenAICompatibleProvider`. Decision deferred to Phase 3 PLAN.md — Plan 02-02 deliberately did NOT modify `__init__.py` per the PLAN's "no edits outside" criterion.

4. **`extract_usage` exposure.** Currently public (`extract_usage` not `_extract_usage`). Phase 3 may want to call it directly for streaming-response variants. If it stays public, document it on the package surface; if not, rename to `_extract_usage` and inline-call from `generate_with_tools`.

5. **`raw_response_text` semantics on tool-only response.** When DeepSeek emits `tool_calls` only, `message.content is None`. The adapter coerces this to `""` for `ProviderResult.raw_response_text` (per the inline `message.content or ""`). Phase 3 should confirm: is empty string the right sentinel, or should `raw_response_text=None` propagate? Currently the dataclass default is `None` — adapter uses `""` to keep type stable (`str` not `str | None` at the call site).

## Test command

```bash
# Plan 02-02 surface (19 tests):
cd project && PYTHONPATH=. python -m pytest tests/test_provider_openai_compatible.py tests/test_provider_line_budget.py -x -q
# 19 passed in ~0.15s

# Full Phase 1 + 2 suite (99 tests):
cd project && PYTHONPATH=. python -m pytest tests/ -q
# 99 passed in ~0.17s

# Line budget assertion:
awk 'NF && !/^[[:space:]]*#/' project/seers_harness/provider_runtime/openai_compatible.py | wc -l
# 142  (≤ 150 ✓)
```

## Gate

All 9 success criteria from PLAN.md met:

- 19/19 new tests green (13 behavior + 6 static).
- 80/80 prior tests still green (12 Plan 02-01 + 68 Phase 1) — zero regression.
- `openai_compatible.py` exposes ONLY `generate_with_tools`; `generate_json` literally absent.
- Source contains the locked runtime literals after Phase 2.1: `tool_choice="auto"`, `reasoning_effort="max"`, `"thinking": {"type": "enabled"}`.
- Source has zero references to `response_format`, `NodeGenerationPolicy`, `policy_for_node`, `normalize_reasoning_effort`, `DEFAULT_DEEPSEEK_NODE_POLICIES`, `parse_node_policies_json`, `load_node_policies_from_env`.
- File line count (blank + comment lines stripped): **142 ≤ 150** ✓ (5.3% under budget).
- `deepseek_provider_from_env` defaults `base_url` to `https://api.deepseek.com/beta` and `model` to `deepseek-chat`.
- `ProviderResult` returned from `generate_with_tools` has `tool_calls` populated with parsed-arguments dicts when DeepSeek emits `tool_calls`, and an empty list with `finish_reason == "stop"` otherwise.
- Exception classification: `rate_limit` → `ProviderRateLimitError`; `transient_provider` → `ProviderTransientError`; `auth` → `ProviderAuthError`; unknown → original exception re-raised unchanged; `__cause__` chain preserved for the typed-error cases.

Phase 3 (Plan 03 — `agentic/tool_loop.py`) is now unblocked. The provider contract is fully testable in isolation; the loop layer can drive it with mocked providers via the same `monkeypatch`-on-local-symbol pattern.
