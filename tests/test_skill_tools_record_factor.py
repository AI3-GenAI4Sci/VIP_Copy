"""TOOL-01 — record_factor handler invariants."""

from __future__ import annotations

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.tools.skill_tools import record_factor


def _valid_factor_args() -> dict:
    return {
        "factor_id": "F-1",
        "user_side_signal": "user_recent_search=维生素",
        "direction": "user_to_need",
        "evidence_paths": ["user_state.behavior.recent_search_cat3_30d"],
        "bridge_to_product": "兰蔻轻盈防晒乳",
        "transferable_disposition": "中年自我保健倾向",
        "covers_product_ids": ["P-001"],
    }


def test_record_factor_appends_and_returns_recorded(sample_scenario_payload: dict) -> None:
    state: dict = {"payload": sample_scenario_payload, "factors": []}
    out = record_factor(_valid_factor_args(), state)
    assert out == "recorded"
    assert len(state["factors"]) == 1
    assert state["factors"][0]["factor_id"] == "F-1"
    assert state["factors"][0]["transferable_disposition"] == "中年自我保健倾向"


def test_record_factor_initializes_factors_list_when_absent(sample_scenario_payload: dict) -> None:
    state: dict = {"payload": sample_scenario_payload}
    record_factor(_valid_factor_args(), state)
    assert state["factors"]
    record_factor(_valid_factor_args(), state)
    assert len(state["factors"]) == 2


def test_record_factor_rejects_unresolvable_evidence_path(sample_scenario_payload: dict) -> None:
    args = _valid_factor_args()
    args["evidence_paths"] = ["user_state.behavior.nonexistent_key"]
    state: dict = {"payload": sample_scenario_payload, "factors": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_factor(args, state)
    assert exc_info.value.tool_name == "record_factor"
    assert "nonexistent_key" in exc_info.value.message
    assert state["factors"] == []


def test_record_factor_rejects_missing_transferable_disposition(sample_scenario_payload: dict) -> None:
    args = _valid_factor_args()
    del args["transferable_disposition"]
    state: dict = {"payload": sample_scenario_payload, "factors": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_factor(args, state)
    assert exc_info.value.tool_name == "record_factor"
    assert state["factors"] == []


def test_record_factor_rejects_empty_evidence_paths(sample_scenario_payload: dict) -> None:
    args = _valid_factor_args()
    args["evidence_paths"] = []
    state: dict = {"payload": sample_scenario_payload, "factors": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_factor(args, state)
    assert exc_info.value.tool_name == "record_factor"
    assert state["factors"] == []
