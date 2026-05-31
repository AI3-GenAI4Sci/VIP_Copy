"""maintain_copy_artifact save invariants."""

from __future__ import annotations

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.tools.skill_tools import maintain_copy_artifact


def _valid_candidate() -> dict:
    return {
        "candidate_id": "C-1",
        "product_id": "P-001",
        "source_user_factor_id": "UF-1",
        "text": "熬夜脸也能轻松修护",
        "commercial_angle": "熬夜痛点前置",
        "product_binding": "商品承接日常调理诉求",
        "fact_binding": "标题含维 B 和修护卖点",
    }


def test_save_passes_with_valid_candidate_state() -> None:
    state: dict = {"candidates": [_valid_candidate()]}
    out = maintain_copy_artifact({"action": "save", "candidates": [], "candidate_ids": [], "product_id": ""}, state)
    assert out == "saved"
    assert state["final_artifact"] == state["copies_artifact"]
    assert state["copies_artifact"]["candidates"][0]["source_user_factor_id"] == "UF-1"


def test_submit_copies_final_fails_when_candidate_missing_required_field() -> None:
    bad_candidate = _valid_candidate()
    del bad_candidate["text"]
    state: dict = {"candidates": [bad_candidate]}
    with pytest.raises(ToolValidationError) as exc_info:
        maintain_copy_artifact({"action": "save", "candidates": [], "candidate_ids": [], "product_id": ""}, state)
    assert exc_info.value.tool_name == "maintain_copy_artifact"
    assert "final_artifact" not in state


def test_save_fails_when_candidates_state_not_list() -> None:
    state: dict = {"candidates": "not a list"}
    with pytest.raises(ToolValidationError):
        maintain_copy_artifact({"action": "save", "candidates": [], "candidate_ids": [], "product_id": ""}, state)


def test_save_accepts_empty_candidates_list() -> None:
    state: dict = {}
    out = maintain_copy_artifact({"action": "save", "candidates": [], "candidate_ids": [], "product_id": ""}, state)
    assert out == "saved"
    assert state["final_artifact"]["candidates"] == []
