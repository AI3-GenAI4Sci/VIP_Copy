---
phase: 03-tool-loop-dag-integration
plan: 01
slug: tool-loop-core
status: complete
wave: 1
requirements_satisfied: [LOOP-01, LOOP-02, LOOP-03, LOOP-04]
must_haves_verified: true
tests_green: 114
tests_skipped: 3
key_files:
  created:
    - project/seers_harness/agentic/__init__.py
    - project/seers_harness/agentic/tool_loop.py
    - project/tests/fakes/__init__.py
    - project/tests/fakes/scripted_provider.py
    - project/tests/test_provider_raw_tool_calls.py
    - project/tests/test_tool_loop_happy_path.py
    - project/tests/test_tool_loop_failure_routing.py
    - project/tests/test_tool_loop_wire_format.py
    - project/tests/test_tool_loop_line_budget.py
  modified:
    - project/seers_harness/provider_runtime/base.py
    - project/seers_harness/provider_runtime/openai_compatible.py
metrics:
  tool_loop_visible_lines: 78
  openai_compatible_visible_lines: 145
  new_tests: 13
  full_suite_tests_green: 114
---

# Phase 3 Plan 01: tool-loop-core Summary

One-liner: c17's true-tool-use multi-turn loop landed — `run_skill_via_tools` drives every SKILL via DeepSeek `/beta` reasoning+tools, echoes reasoning_content + raw SDK tool_calls on subsequent turns (RESEARCH §2), routes the five failure modes deterministically, and fits in 78 visible lines.

## Goal

Lock the c17 LLM loop contract — `agentic/tool_loop.py` exporting `run_skill_via_tools(...) -> ToolLoopResult` — so factor / copy / rubric SKILLs share one mechanism. Includes the Phase 2.2 patch adding `raw_tool_calls: list | None` to `ProviderResult` (the SDK passthrough required by the wire-format echo). Build a hermetic `ScriptedProvider` test double so 11 behavior tests + 2 raw_tool_calls tests drive the impl without any openai SDK or network.

## Tasks Executed

| # | Task                                                          | Mode  | Outcome                                                                                                                  |
| - | ------------------------------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------------ |
| 1 | RED — ScriptedProvider scaffold + 13 failing tests            | TDD-R | 7 new files; all 13 RED with the correct error class (ImportError / AssertionError / FileNotFoundError); 101 prior tests green |
| 2 | GREEN partial — `raw_tool_calls` field + adapter wiring (5 LOC patch) | TDD-G | base.py +2 lines, openai_compatible.py +1 line; 2 raw_tool_calls tests GREEN; PROV-06 budget 145/150; 103 tests green        |
| 3 | GREEN full — write `agentic/tool_loop.py` + `agentic/__init__.py` | TDD-G | 78-line impl; all 11 tool_loop tests GREEN on first run; one-line retry-block compaction trimmed 80 → 78 for headroom; full suite 114/114 |

## LOOP-* Coverage Matrix

| Requirement | Verified by                                                            | Static evidence                                                              |
| ----------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| LOOP-01     | `test_happy_path_single_turn_factor_skill`, `test_happy_path_many_turns_with_reflect_between`, signature grep | `def run_skill_via_tools` with the exact 9-param keyword-only signature; returns ToolLoopResult(artifact, turns_used, tool_calls_made, last_reasoning_content) |
| LOOP-02     | `test_dispatch_order_preserved_within_single_turn` + happy-path tests   | initial messages = `[system(skill_bundle), user(payload_json)]`; tool_calls dispatched in emit order; `role:tool` appended each iteration; termination on `state["final_artifact"]` |
| LOOP-03     | 6 failure-routing tests                                                 | invalid args → `f"ERROR: {exc}"`; unknown tool → `"ERROR: unknown tool 'X'"`; cap → `ToolLoopError("exceeded max_tool_calls=N")`; stop → `ToolLoopError("model stopped without submit_final")`; transient → 1 initial + 2 retries; propagate on 3rd |
| LOOP-04     | `test_tool_loop_visible_line_count_in_50_to_80`                         | `awk 'NF && !/^[[:space:]]*#/' tool_loop.py \| wc -l` = 78 (within 50-80)     |

## ProviderResult Field Addition

`ProviderResult` now carries 9 fields (was 8 in Plan 02-01). The new `raw_tool_calls: list | None = None` is the SDK passthrough — the loop reads this (not the parsed c17 `tool_calls`) when appending the assistant message back into the conversation. Field is appended LAST so prior positional-construct sites are unaffected; the existing 8 fields keep their Plan 02-01 positions.

| Field             | Type                        | Source                              | Consumer                                  |
| ----------------- | --------------------------- | ----------------------------------- | ----------------------------------------- |
| `raw_tool_calls`  | `list \| None`              | `message.tool_calls` (SDK SimpleNamespace) | tool_loop.py wire-format echo (turn ≥ 2) |

## Wire-Format Echo Test (Highest-Risk Phase 7 Failure Mode)

`test_reasoning_content_and_raw_tool_calls_echoed_in_subsequent_turn` is the contract that catches DeepSeek's most likely silent failure: a turn-2 400 because reasoning_content + the original-shape tool_calls weren't echoed back. The test:

1. Scripts turn 1 with `reasoning_content="R"*30` and `raw_tool_calls=[SimpleNamespace(id="call_1", function=SimpleNamespace(name="record_factor", arguments=<json>))]`.
2. Lets the loop run to turn 2.
3. Inspects `scripted.received_messages[1]` — the messages list fed into the 2nd provider call.
4. Locates the assistant message; asserts `reasoning_content == "R"*30`, `tool_calls[0].id == "call_1"` (i.e., the SDK SimpleNamespace, not the parsed c17 dict), and `content in (None, "")`.

This will be re-verified at Phase 7 against the live DeepSeek `/beta` endpoint.

## Anti-Pattern Audit

`grep -E 'check_feedback|raw_holder|max_rounds|response_format|def generate_json|TransientProviderError' seers_harness/agentic/tool_loop.py` returns 0 — no c16 anti-patterns. The correct exception name `ProviderTransientError` is used (3 occurrences in tool_loop.py incl. import).

## Open Questions for Plan 03-03

1. **`tool_loop_summary` event schema (RESEARCH §7-Q5):** Plan 03-03 needs to emit a `tool_loop_summary` event per node. The loop currently returns `ToolLoopResult(artifact, turns_used, tool_calls_made, last_reasoning_content)`. **Recommendation:** Plan 03-03's dag_runner reads ToolLoopResult and constructs its own event dict; the loop does no logging. `last_reasoning_content` is the final-turn reasoning — if 03-03 wants per-turn reasoning, it can wrap the provider in a recording decorator or extend ToolLoopResult later (additive). Don't add a `reasoning_content_per_turn: list[str | None]` to ToolLoopResult yet — wait until 03-03 actually needs it.

2. **Outer attempt budget (`node.max_attempts`) vs inner `max_tool_calls`:** These are two different budgets per RESEARCH §8 pitfall 4. The loop owns `max_tool_calls=30`; Plan 03-03's dag_runner owns `node.max_attempts` (how many times to retry the whole loop if it raises ToolLoopError). **Recommendation:** confirm Plan 03-03 keeps the name `max_attempts` for the outer; never collapse the two.

3. **Per-turn `provider.last_usage` accumulation:** The Provider Protocol declares `last_usage: dict[str, Any]` as a per-call attribute. The current loop does NOT read it inside the loop body — Plan 03-03's dag_runner needs to decide whether to accumulate `provider.last_usage` per turn (call-site iteration) or have the loop expose a `usage_per_turn` list. **Recommendation:** Plan 03-03 wraps the provider with an accumulator outside the loop; keep tool_loop.py I/O-free.

## Principle 14 Four-Question Self-Audit

1. **What does this code do?** Multi-turn LLM tool-use loop: build the initial messages, ask the provider, append assistant+tool messages, loop until `submit_*_final` sets `state["final_artifact"]` or a failure routes deterministically.
2. **What does it NOT do?** No JSON-mode fallback (PROV-02); no per-node policy branching (PROV-03 lives in the adapter); no external feedback re-injection (`check_feedback` is the c16 anti-pattern); no outer attempt management (`max_attempts` is Plan 03-03's concern); no provider I/O retries beyond the typed `ProviderTransientError` budget.
3. **What happens when it breaks?** `ToolLoopError` for terminal loop failures (cap exceeded, stop-without-submit); `ProviderTransientError` propagates after the per-turn retry budget; `ToolValidationError` from handlers becomes an `ERROR: ...` tool message so the model can self-correct (loop continues).
4. **What does the test suite guarantee?** 11 loop tests + 2 raw_tool_calls tests cover all 6 failure modes, the 3 happy-path shapes (single-turn, many-turn, dispatch-order), the wire-format echo (RESEARCH §2), the line budget (LOOP-04), and the Phase 2.2 SDK passthrough field.

## Deviations from PLAN.md

**None.**

Notes on plan-internal flexibility points the executor exercised:

- The plan permitted `list | None` OR `list[Any] | None` for the `raw_tool_calls` annotation; chose `list | None` per the plan's stated preference for opaque-SDK fields.
- The plan permitted either `attempts = 0; while True` or `for attempt in range(N+1)` for the transient retry block "ONLY if the test for retry-budget-exhausted still passes verbatim." Initial impl used the `while True` form (80 lines exactly). Compacted to `for attempt in range(max_transient_retries_per_turn + 1)` to land at 78 lines (2-line headroom under the LOOP-04 ceiling). All 2 retry tests still pass; semantics unchanged.
- Test count is 13 new tests, exactly matching the plan's `<files>` block.
- Pre-existing test count was 101 + 3 skipped (not 100 as the plan referenced); the plan's "at least 100 passing" gate is satisfied. Total after this plan: 114 + 3 skipped.

## Phase 7 Confirmation Points

1. The `reasoning_content` echo test uses a stub string `"R" * 30` — Phase 7 needs to re-verify that DeepSeek's real reasoning_content emission flows through `OpenAICompatibleProvider` and that the assistant-message echo doesn't trigger a 400 on turn 2.
2. The `raw_tool_calls` test asserts SDK-shape SimpleNamespace passthrough. Phase 7 will receive real `openai.types.chat.ChatCompletionMessageToolCall` objects — the duck-typed loop (`.id`, `.function.name`) should accept these unchanged, but worth one smoke test against real SDK objects at Phase 7 wiring.
3. The transient-error budget is exercised by `ProviderTransientError` raised by the scripted provider. Phase 7 should observe at least one real transient (timeout / 503) under sustained load to confirm the retry-then-propagate semantics behave per the test contract.

## Gate

- Full suite: **114 tests passed + 3 skipped** (101 prior Phase 1+2 + 2 new raw_tool_calls + 11 new tool_loop).
- LOOP-04 line budget: 78 visible lines (50-80 ✓).
- PROV-06 line budget unchanged at 145/150 (Plan 02-02 baseline was 144; the 1-line patch is within budget).
- Anti-pattern grep: 0 occurrences across `check_feedback|raw_holder|max_rounds|response_format|def generate_json|TransientProviderError`.
- Wire-format echo: 5 occurrences of `reasoning_content` in tool_loop.py (echo on assistant message + return on ToolLoopResult + comment + docstring).

## Self-Check: PASSED

All 9 listed file paths exist on disk; full pytest run shows 114 green; no git in this repo so no commit hashes to verify.
