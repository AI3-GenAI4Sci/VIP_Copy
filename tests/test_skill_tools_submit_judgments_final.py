"""TOOL-06 — submit_judgments_final handler invariants."""

from __future__ import annotations

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.tools.skill_tools import submit_judgments_final


def _valid_judgment() -> dict:
    return {
        "candidate_id": "C-1",
        "candidate_index": 0,
        "product_id": "P-001",
        "copy_text": "兰蔻防晒霜温柔守护肌肤",
        "user_factor_id": "UF-1",
        "axis_scores": [
            {"axis_id": "user_factor_grounding", "score": 5, "diagnostic": "aligned"},
            {
                "axis_id": "product_binding",
                "score": 4,
                "diagnostic": "specific",
            },
            {"axis_id": "personalized_conversion", "score": 4, "diagnostic": "slogan-like"},
            {"axis_id": "commercial_sharpness", "score": 4, "diagnostic": "relevant"},
            {"axis_id": "expression_boundary", "score": 4, "diagnostic": "natural"},
        ],
        "total_score": 21,
        "main_strength": "anchor literal",
        "main_weakness": "none",
        "failure_tags": [],
        "decision": "admit",
    }


def test_submit_judgments_final_passes_with_valid_artifact() -> None:
    state: dict = {}
    out = submit_judgments_final({"judgments": [_valid_judgment()]}, state)
    assert out == "finalized"
    assert "final_artifact" in state
    assert state["final_artifact"]["judgments"][0]["candidate_id"] == "C-1"
    assert state["final_artifact"]["judgments"][0]["decision"] == "admit"


def test_submit_judgments_final_fills_default_decision_when_missing() -> None:
    """decision defaults to hold when omitted."""
    bad = _valid_judgment()
    del bad["decision"]
    state: dict = {}
    out = submit_judgments_final({"judgments": [bad]}, state)
    assert out == "finalized"
    assert state["final_artifact"]["judgments"][0]["decision"] == "hold"


def test_submit_judgments_final_fails_when_judgments_not_list() -> None:
    state: dict = {}
    with pytest.raises(ToolValidationError) as exc_info:
        submit_judgments_final({"judgments": "not a list"}, state)
    assert exc_info.value.tool_name == "submit_judgments_final"
    assert "final_artifact" not in state


def test_submit_judgments_final_accepts_empty_judgments_list() -> None:
    state: dict = {}
    out = submit_judgments_final({"judgments": []}, state)
    assert out == "finalized"
    assert state["final_artifact"]["judgments"] == []
