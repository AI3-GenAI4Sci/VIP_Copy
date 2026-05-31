"""TOOL-05 — scored judge_candidate handler invariants."""

from __future__ import annotations

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.tools.skill_tools import judge_candidate


_CANDIDATE_TEXT = "兰蔻防晒霜温柔守护肌肤"


def _seed_state_with_candidate(candidate_id: str = "C-1") -> dict:
    return {
        "copies_artifact": {
            "candidates": [
                {"candidate_id": candidate_id, "text": _CANDIDATE_TEXT},
            ],
        },
    }


def _valid_judgment(candidate_id: str = "C-1") -> dict:
    return {
        "candidate_id": candidate_id,
        "candidate_index": 0,
        "product_id": "P-001",
        "copy_text": _CANDIDATE_TEXT,
        "user_factor_id": "UF-1",
        "axis_scores": [
            {"axis_id": "user_factor_grounding", "score": 4, "diagnostic": "matches factor"},
            {
                "axis_id": "product_binding",
                "score": 3,
                "diagnostic": "has a care scene",
            },
            {"axis_id": "personalized_conversion", "score": 4, "diagnostic": "short and usable"},
            {
                "axis_id": "commercial_sharpness",
                "score": 4,
                "diagnostic": "product category is visible",
            },
            {"axis_id": "expression_boundary", "score": 4, "diagnostic": "sounds natural"},
        ],
        "total_score": 19,
        "main_strength": "anchor literal",
        "main_weakness": "not very distinctive",
        "failure_tags": ["weak_distinction"],
        "decision": "admit",
    }


def test_judge_candidate_passes_when_all_quotes_in_text() -> None:
    state = _seed_state_with_candidate()
    out = judge_candidate(_valid_judgment(), state)
    assert out == "recorded"
    assert len(state["judgments"]) == 1
    assert state["judgments"][0]["candidate_id"] == "C-1"
    assert state["judgments"][0]["decision"] == "admit"
    assert state["judgments"][0]["total_score"] == 19


def test_judge_candidate_rejects_mismatched_copy_text() -> None:
    state = _seed_state_with_candidate()
    bad_judgment = _valid_judgment()
    bad_judgment["copy_text"] = "完全不是这条文案"
    with pytest.raises(ToolValidationError) as exc_info:
        judge_candidate(bad_judgment, state)
    assert exc_info.value.tool_name == "judge_candidate"
    assert exc_info.value.arg_path == "copy_text"
    assert "judgments" not in state or state["judgments"] == []


def test_judge_candidate_rejects_total_score_mismatch() -> None:
    state = _seed_state_with_candidate()
    judgment = _valid_judgment()
    judgment["total_score"] = 25
    with pytest.raises(ToolValidationError) as exc_info:
        judge_candidate(judgment, state)
    assert exc_info.value.tool_name == "judge_candidate"
    assert exc_info.value.arg_path == "total_score"


def test_judge_candidate_rejects_unknown_candidate_id() -> None:
    state = _seed_state_with_candidate(candidate_id="C-1")
    judgment = _valid_judgment(candidate_id="C-DOES-NOT-EXIST")
    with pytest.raises(ToolValidationError) as exc_info:
        judge_candidate(judgment, state)
    assert exc_info.value.tool_name == "judge_candidate"
    assert exc_info.value.arg_path == "candidate_id"
    assert "C-DOES-NOT-EXIST" in exc_info.value.message


def test_judge_candidate_fails_on_schema_violation() -> None:
    """Missing required field → ToolValidationError, not pydantic ValidationError."""
    state = _seed_state_with_candidate()
    bad_judgment = _valid_judgment()
    del bad_judgment["candidate_id"]
    with pytest.raises(ToolValidationError) as exc_info:
        judge_candidate(bad_judgment, state)
    assert exc_info.value.tool_name == "judge_candidate"


def test_judge_candidate_initializes_judgments_list_when_absent() -> None:
    state = _seed_state_with_candidate()
    assert "judgments" not in state
    judge_candidate(_valid_judgment(), state)
    assert state["judgments"]
    judge_candidate(_valid_judgment(), state)
    assert len(state["judgments"]) == 2
