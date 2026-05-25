"""TOOL-02 — submit_factors_final handler invariants."""

from __future__ import annotations

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.tools.skill_tools import submit_factors_final


def _valid_factor() -> dict:
    return {
        "factor_id": "F-1",
        "user_side_signal": "user_recent_search=维生素",
        "direction": "user_to_need",
        "evidence_refs": [{"path": "user_state.behavior.recent_search_cat3_30d", "value": "维生素"}],
        "bridge": "兰蔻轻盈防晒乳",
        "transferable_disposition": "中年自我保健倾向",
        "covers_product_ids": ["P-001"],
    }


def test_submit_factors_final_passes_with_valid_artifact() -> None:
    state: dict = {}
    out = submit_factors_final({"factors": [_valid_factor()]}, state)
    assert out == "finalized"
    assert "final_artifact" in state
    assert state["final_artifact"]["factors"][0]["factor_id"] == "F-1"


def test_submit_factors_final_fails_when_factor_missing_disposition() -> None:
    bad_factor = _valid_factor()
    del bad_factor["transferable_disposition"]
    state: dict = {}
    with pytest.raises(ToolValidationError) as exc_info:
        submit_factors_final({"factors": [bad_factor]}, state)
    assert exc_info.value.tool_name == "submit_factors_final"
    assert "transferable_disposition" in exc_info.value.message
    assert "final_artifact" not in state


def test_submit_factors_final_fails_when_factors_not_list() -> None:
    state: dict = {}
    with pytest.raises(ToolValidationError) as exc_info:
        submit_factors_final({"factors": "not a list"}, state)
    assert exc_info.value.tool_name == "submit_factors_final"
    assert "final_artifact" not in state


def test_submit_factors_final_accepts_empty_factors_list() -> None:
    state: dict = {}
    out = submit_factors_final({"factors": []}, state)
    assert out == "finalized"
    assert state["final_artifact"]["factors"] == []
