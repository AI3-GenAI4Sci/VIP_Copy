"""Tool-loop failure-routing behaviors — LOOP-03.

Tests 3-8 of RESEARCH §6 outline:
  - invalid args  -> "ERROR: ..." tool message; loop continues
  - unknown tool  -> "ERROR: unknown tool ..." tool message; loop continues
  - cap exceeded  -> ToolLoopError
  - stop without submit -> ToolLoopError
  - transient retry budget exhausted -> ProviderTransientError propagates
  - transient retry succeeds within budget -> loop completes normally
"""

from __future__ import annotations

import pytest

from seers_harness.agentic.tool_loop import (
    ToolLoopError,
    run_skill_via_tools,
)
from seers_harness.core.errors import ProviderTransientError
from seers_harness.tools.skill_tools import (
    TOOL_HANDLERS,
    TOOLS_SPEC,
)

from tests.fakes.scripted_provider import ScriptedProvider, ScriptedTurn


_VALID_FACTOR_ARGS_F1 = {
    "factor_id": "F1",
    "user_side_signal": "user searched skincare",
    "direction": "user_to_need",
    "evidence_paths": ["user_state.behavior.recent_search_cat3_30d"],
    "bridge_to_product": "bridges curiosity to product",
    "transferable_disposition": "skincare-curious",
    "covers_product_ids": ["P1"],
}

_BAD_FACTOR_ARGS = {
    **_VALID_FACTOR_ARGS_F1,
    "factor_id": "FBAD",
    "evidence_paths": ["nonexistent.field"],
}

_VALID_ARTIFACT = {
    "factors": [
        {
            "factor_id": "F1",
            "user_side_signal": "user searched skincare",
            "direction": "user_to_need",
            "transferable_disposition": "skincare-curious",
            "evidence_refs": [
                {"path": "user_state.behavior.recent_search_cat3_30d", "value": "x"}
            ],
            "bridge": "bridges curiosity to product",
            "covers_product_ids": ["P1"],
        }
    ]
}

_PAYLOAD = {
    "user_state": {
        "behavior": {
            "recent_search_cat3_30d": "维生素,面膜,精华液",
        }
    },
    "products": [{"product_id": "P1"}],
}


def _spec():
    return TOOLS_SPEC["discover-personalization-factors"]


def _last_tool_msg(messages: list[dict]) -> dict:
    return [m for m in messages if m.get("role") == "tool"][-1]


def test_invalid_args_routes_to_error_tool_message_and_loop_continues():
    """LOOP-03 — ToolValidationError from handler surfaces as 'ERROR: ...' tool message; loop continues."""
    script = [
        ScriptedTurn(
            tool_calls=[
                {"id": "c1", "name": "record_factor", "arguments": _BAD_FACTOR_ARGS},
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                {"id": "c2", "name": "record_factor", "arguments": _VALID_FACTOR_ARGS_F1},
                {"id": "c3", "name": "submit_factors_final", "arguments": _VALID_ARTIFACT},
            ]
        ),
    ]
    scripted = ScriptedProvider(script=script)
    result = run_skill_via_tools(
        skill_name="discover-personalization-factors",
        skill_bundle="SKILL_BODY",
        payload=_PAYLOAD,
        tools_spec=_spec(),
        tool_handlers=TOOL_HANDLERS,
        provider=scripted,
        node_id="n",
    )
    assert result.turns_used == 2
    # Messages list fed into the 2nd provider call must include the error tool
    # message generated from the 1st turn's failed record_factor dispatch.
    msgs_at_turn_2 = scripted.received_messages[1]
    last_tool = _last_tool_msg(msgs_at_turn_2)
    assert last_tool["content"].startswith("ERROR:")
    assert "evidence_paths" in last_tool["content"]


def test_unknown_tool_name_routes_to_error_tool_message_and_loop_continues():
    """LOOP-03 — unknown tool name surfaces as 'ERROR: unknown tool ...' tool message; loop continues."""
    script = [
        ScriptedTurn(
            tool_calls=[{"id": "cx", "name": "made_up_tool", "arguments": {}}]
        ),
        ScriptedTurn(
            tool_calls=[
                {"id": "c1", "name": "record_factor", "arguments": _VALID_FACTOR_ARGS_F1},
                {"id": "c2", "name": "submit_factors_final", "arguments": _VALID_ARTIFACT},
            ]
        ),
    ]
    scripted = ScriptedProvider(script=script)
    result = run_skill_via_tools(
        skill_name="discover-personalization-factors",
        skill_bundle="SKILL_BODY",
        payload=_PAYLOAD,
        tools_spec=_spec(),
        tool_handlers=TOOL_HANDLERS,
        provider=scripted,
        node_id="n",
    )
    assert result.turns_used == 2
    msgs_at_turn_2 = scripted.received_messages[1]
    last_tool = _last_tool_msg(msgs_at_turn_2)
    assert last_tool["content"] == "ERROR: unknown tool 'made_up_tool'"


def test_cap_exceeded_raises_tool_loop_error():
    """LOOP-03 — exceeding max_tool_calls raises ToolLoopError."""
    script = [
        ScriptedTurn(
            tool_calls=[
                {"id": f"c{i}", "name": "record_factor", "arguments": _VALID_FACTOR_ARGS_F1}
            ]
        )
        for i in range(4)
    ]
    scripted = ScriptedProvider(script=script)
    with pytest.raises(ToolLoopError, match="exceeded max_tool_calls=3"):
        run_skill_via_tools(
            skill_name="discover-personalization-factors",
            skill_bundle="SKILL_BODY",
            payload=_PAYLOAD,
            tools_spec=_spec(),
            tool_handlers=TOOL_HANDLERS,
            provider=scripted,
            node_id="n",
            max_tool_calls=3,
        )
    # The loop executed turns 0, 1, 2 — three provider calls — then the cap raised.
    assert scripted._idx == 3


def test_stop_without_submit_raises_tool_loop_error():
    """LOOP-03 — model emits empty tool_calls without submit -> ToolLoopError."""
    script = [
        ScriptedTurn(
            tool_calls=[],
            finish_reason="stop",
            reasoning_content=None,
        )
    ]
    scripted = ScriptedProvider(script=script)
    with pytest.raises(ToolLoopError, match="model stopped without submit_final"):
        run_skill_via_tools(
            skill_name="discover-personalization-factors",
            skill_bundle="SKILL_BODY",
            payload=_PAYLOAD,
            tools_spec=_spec(),
            tool_handlers=TOOL_HANDLERS,
            provider=scripted,
            node_id="n",
        )


def test_transient_retry_budget_exhausted_propagates():
    """LOOP-03 — 1 initial + 2 retries exhausted -> ProviderTransientError propagates."""
    script = [
        ScriptedTurn(raise_exc=ProviderTransientError("simulated 503")),
        ScriptedTurn(raise_exc=ProviderTransientError("simulated 503")),
        ScriptedTurn(raise_exc=ProviderTransientError("simulated 503")),
    ]
    scripted = ScriptedProvider(script=script)
    with pytest.raises(ProviderTransientError):
        run_skill_via_tools(
            skill_name="discover-personalization-factors",
            skill_bundle="SKILL_BODY",
            payload=_PAYLOAD,
            tools_spec=_spec(),
            tool_handlers=TOOL_HANDLERS,
            provider=scripted,
            node_id="n",
            max_transient_retries_per_turn=2,
        )
    assert scripted._idx == 3


def test_transient_retry_succeeds_within_budget():
    """LOOP-03 — transient error retries successfully within the same turn budget."""
    script = [
        ScriptedTurn(raise_exc=ProviderTransientError("flaky")),
        ScriptedTurn(
            tool_calls=[
                {"id": "c1", "name": "record_factor", "arguments": _VALID_FACTOR_ARGS_F1},
                {"id": "c2", "name": "submit_factors_final", "arguments": _VALID_ARTIFACT},
            ]
        ),
        # Sentinel — must NOT be consumed by the retry.
        ScriptedTurn(
            tool_calls=[{"id": "csentinel", "name": "record_factor", "arguments": {}}]
        ),
    ]
    scripted = ScriptedProvider(script=script)
    result = run_skill_via_tools(
        skill_name="discover-personalization-factors",
        skill_bundle="SKILL_BODY",
        payload=_PAYLOAD,
        tools_spec=_spec(),
        tool_handlers=TOOL_HANDLERS,
        provider=scripted,
        node_id="n",
        max_transient_retries_per_turn=2,
    )
    assert result.turns_used == 1
    assert result.tool_calls_made == 2
    assert scripted._idx == 2
