"""Tool-loop wire-format echo — RESEARCH §2 + LOOP-01.

DeepSeek's ``/beta`` reasoning-with-tools requires the prior turn's assistant
message to carry BOTH ``reasoning_content`` AND the original SDK ``tool_calls``
shape on subsequent turns. The loop assembles this assistant message between
the provider call and the tool dispatches. This single test is the highest-
risk Phase 7 silent failure mode (RESEARCH §10) caught at the wire layer.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from seers_harness.agentic.tool_loop import run_skill_via_tools
from seers_harness.tools.skill_tools import TOOL_HANDLERS, TOOLS_SPEC

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


def test_reasoning_content_and_raw_tool_calls_echoed_in_subsequent_turn():
    """RESEARCH §2 — turn-2 messages MUST contain the prior assistant turn's
    reasoning_content + the SDK-shape raw_tool_calls (NOT the parsed c17 dict)."""
    sdk_shape_tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="record_factor",
            arguments=json.dumps(_VALID_FACTOR_ARGS_F1),
        ),
    )
    script = [
        ScriptedTurn(
            tool_calls=[
                {"id": "call_1", "name": "record_factor", "arguments": _VALID_FACTOR_ARGS_F1}
            ],
            raw_tool_calls=[sdk_shape_tool_call],
            reasoning_content="R" * 30,
        ),
        ScriptedTurn(
            tool_calls=[
                {"id": "call_2", "name": "submit_factors_final", "arguments": _VALID_ARTIFACT}
            ],
            reasoning_content="S" * 30,
        ),
    ]
    scripted = ScriptedProvider(script=script)
    run_skill_via_tools(
        skill_name="discover-personalization-factors",
        skill_bundle="SKILL_BODY",
        payload=_PAYLOAD,
        tools_spec=TOOLS_SPEC["discover-personalization-factors"],
        tool_handlers=TOOL_HANDLERS,
        provider=scripted,
        node_id="n",
    )
    msgs_at_turn_2 = scripted.received_messages[1]
    # Locate the assistant turn the loop appended after turn 1.
    assistant_msgs = [m for m in msgs_at_turn_2 if m.get("role") == "assistant"]
    assert len(assistant_msgs) == 1
    assistant_msg = assistant_msgs[0]
    assert assistant_msg["reasoning_content"] == "R" * 30
    # tool_calls MUST be the SDK SimpleNamespace passthrough, not the parsed dict shape.
    assert assistant_msg["tool_calls"] is not None
    assert len(assistant_msg["tool_calls"]) == 1
    assert assistant_msg["tool_calls"][0].id == "call_1"
    # The ScriptedProvider sets raw_response_text=""; the loop normalizes "" to None.
    assert assistant_msg.get("content") in (None, "")
