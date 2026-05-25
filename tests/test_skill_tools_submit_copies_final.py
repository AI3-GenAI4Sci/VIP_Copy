"""TOOL-04 — submit_copies_final handler invariants."""

from __future__ import annotations

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.tools.skill_tools import submit_copies_final


def _valid_candidate() -> dict:
    return {
        "candidate_id": "C-1",
        "product_id": "P-001",
        "target_product_id": "P-001",
        "group_key": "防晒霜/乳",
        "text": "兰蔻防晒霜温柔守护肌肤",
        "source_factor_id": "F-1",
        "bridge_logic": {
            "product_anchor": "兰蔻",
            "relation_anchor": "防晒霜",
        },
        "considered_drafts": ["兰蔻防晒霜温柔守护肌肤"],
        "chosen_draft_index": 0,
        "used_copyable_hooks": [],
        "intended_effect": "凸显防晒主张",
    }


def test_submit_copies_final_passes_with_valid_artifact() -> None:
    state: dict = {}
    out = submit_copies_final({"candidates": [_valid_candidate()]}, state)
    assert out == "finalized"
    # Both keys must be set per TOOL-04 contract — copies_artifact is read by
    # the rubric SKILL's judge_candidate in the next loop iteration.
    assert "final_artifact" in state
    assert "copies_artifact" in state
    assert state["final_artifact"] == state["copies_artifact"]
    assert state["copies_artifact"]["candidates"][0]["candidate_id"] == "C-1"


def test_submit_copies_final_fails_when_candidate_missing_required_field() -> None:
    bad_candidate = _valid_candidate()
    del bad_candidate["text"]
    state: dict = {}
    with pytest.raises(ToolValidationError) as exc_info:
        submit_copies_final({"candidates": [bad_candidate]}, state)
    assert exc_info.value.tool_name == "submit_copies_final"
    assert "final_artifact" not in state
    assert "copies_artifact" not in state


def test_submit_copies_final_fails_when_candidates_not_list() -> None:
    state: dict = {}
    with pytest.raises(ToolValidationError) as exc_info:
        submit_copies_final({"candidates": "not a list"}, state)
    assert exc_info.value.tool_name == "submit_copies_final"
    assert "final_artifact" not in state
    assert "copies_artifact" not in state


def test_submit_copies_final_accepts_empty_candidates_list() -> None:
    state: dict = {}
    out = submit_copies_final({"candidates": []}, state)
    assert out == "finalized"
    assert state["final_artifact"]["candidates"] == []
    assert state["copies_artifact"]["candidates"] == []
