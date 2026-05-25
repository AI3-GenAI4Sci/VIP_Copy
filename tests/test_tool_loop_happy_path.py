"""Tool-loop happy-path behaviors — LOOP-01 + LOOP-02.

Tests 1, 2, 10 of RESEARCH §6 outline:
  - single-turn submit (test 1)
  - many-turn flow with reflect interleaved (test 2)
  - dispatch order preserved within a single turn's tool_calls list (test 10)

All driven by ScriptedProvider; no provider network call.
"""

from __future__ import annotations

from seers_harness.agentic.tool_loop import (
    ToolLoopResult,
    run_skill_via_tools,
)
from seers_harness.tools.skill_tools import (
    TOOL_HANDLERS,
    TOOLS_SPEC,
    record_factor,
)

from tests.fakes.scripted_provider import ScriptedProvider, ScriptedTurn


_FACTOR_ARGS_F1 = {
    "factor_id": "F1",
    "user_side_signal": "user searched skincare brands recently",
    "direction": "user_to_need",
    "evidence_paths": ["user_state.behavior.recent_search_cat3_30d"],
    "bridge_to_product": "bridges curiosity about skincare ingredients to this product",
    "transferable_disposition": "skincare-curious",
    "covers_product_ids": ["P1"],
}

_FACTOR_ARGS_F2 = {
    "factor_id": "F2",
    "user_side_signal": "user has a favored brand list",
    "direction": "user_to_need",
    "evidence_paths": ["user_state.behavior.user_top_brand_30d"],
    "bridge_to_product": "bridges brand affinity to this product line",
    "transferable_disposition": "brand-loyal",
    "covers_product_ids": ["P1"],
}

_FACTOR_ARGS_F3 = {
    "factor_id": "F3",
    "user_side_signal": "user searched skincare cat3 names",
    "direction": "user_to_need",
    "evidence_paths": ["user_state.behavior.recent_search_cat3_30d"],
    "bridge_to_product": "bridges category-search intent to this product",
    "transferable_disposition": "category-explorer",
    "covers_product_ids": ["P1"],
}


def _factor_dump(factor_id: str, evidence_path: str, signal: str, disposition: str) -> dict:
    return {
        "factor_id": factor_id,
        "user_side_signal": signal,
        "direction": "user_to_need",
        "transferable_disposition": disposition,
        "evidence_refs": [{"path": evidence_path, "value": "x"}],
        "bridge": "bridges curiosity to product",
        "covers_product_ids": ["P1"],
    }


_PAYLOAD = {
    "user_state": {
        "behavior": {
            "recent_search_cat3_30d": "维生素,面膜,精华液",
            "user_top_brand_30d": "雅诗兰黛,资生堂",
        }
    },
    "products": [{"product_id": "P1"}],
}


def _spec():
    return TOOLS_SPEC["discover-personalization-factors"]


def test_happy_path_single_turn_factor_skill():
    """LOOP-02 — one turn emits [record_factor, submit_factors_final] and the loop terminates."""
    artifact_dump = {
        "factors": [
            _factor_dump("F1", "user_state.behavior.recent_search_cat3_30d", "searched skincare", "skincare-curious")
        ]
    }
    turn = ScriptedTurn(
        tool_calls=[
            {"id": "c1", "name": "record_factor", "arguments": _FACTOR_ARGS_F1},
            {"id": "c2", "name": "submit_factors_final", "arguments": artifact_dump},
        ]
    )
    scripted = ScriptedProvider(script=[turn])
    result = run_skill_via_tools(
        skill_name="discover-personalization-factors",
        skill_bundle="SKILL_BODY",
        payload=_PAYLOAD,
        tools_spec=_spec(),
        tool_handlers=TOOL_HANDLERS,
        provider=scripted,
        node_id="n",
    )
    assert isinstance(result, ToolLoopResult)
    assert result.turns_used == 1
    assert result.tool_calls_made == 2
    assert isinstance(result.artifact, dict)
    assert "factors" in result.artifact
    assert len(result.artifact["factors"]) == 1
    assert result.last_reasoning_content == "R" * 30


def test_happy_path_many_turns_with_reflect_between():
    """LOOP-02 — 7 turns (5 record + 1 reflect + 1 submit) execute cleanly."""
    artifact_dump = {
        "factors": [
            _factor_dump(f"F{i}", "user_state.behavior.recent_search_cat3_30d", f"signal-{i}", f"disp-{i}")
            for i in range(1, 6)
        ]
    }
    script = [
        ScriptedTurn(
            tool_calls=[
                {"id": f"c{i}", "name": "record_factor", "arguments": {**_FACTOR_ARGS_F1, "factor_id": f"F{i}"}}
            ]
        )
        for i in range(1, 6)
    ] + [
        ScriptedTurn(
            tool_calls=[{"id": "creflect", "name": "reflect_on_coverage", "arguments": {}}]
        ),
        ScriptedTurn(
            tool_calls=[{"id": "csubmit", "name": "submit_factors_final", "arguments": artifact_dump}]
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
    assert result.turns_used == 7
    assert result.tool_calls_made == 7


def test_dispatch_order_preserved_within_single_turn():
    """LOOP-02 — when a turn emits multiple tool_calls, handlers run in emit order."""
    seen: list[str] = []

    def spy(args: dict, state: dict) -> str:
        seen.append(args["factor_id"])
        return record_factor(args, state)

    handlers = {**TOOL_HANDLERS, "record_factor": spy}

    artifact_dump = {
        "factors": [
            _factor_dump("F1", "user_state.behavior.recent_search_cat3_30d", "s1", "d1"),
            _factor_dump("F2", "user_state.behavior.user_top_brand_30d", "s2", "d2"),
            _factor_dump("F3", "user_state.behavior.recent_search_cat3_30d", "s3", "d3"),
        ]
    }
    script = [
        ScriptedTurn(
            tool_calls=[
                {"id": "c1", "name": "record_factor", "arguments": _FACTOR_ARGS_F1},
                {"id": "c2", "name": "record_factor", "arguments": _FACTOR_ARGS_F2},
                {"id": "c3", "name": "record_factor", "arguments": _FACTOR_ARGS_F3},
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                {"id": "csubmit", "name": "submit_factors_final", "arguments": artifact_dump}
            ]
        ),
    ]
    scripted = ScriptedProvider(script=script)
    result = run_skill_via_tools(
        skill_name="discover-personalization-factors",
        skill_bundle="SKILL_BODY",
        payload=_PAYLOAD,
        tools_spec=_spec(),
        tool_handlers=handlers,
        provider=scripted,
        node_id="n",
    )
    assert seen == ["F1", "F2", "F3"]
    assert result.tool_calls_made == 4
    assert result.turns_used == 2
