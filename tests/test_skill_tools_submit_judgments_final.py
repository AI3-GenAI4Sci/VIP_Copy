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
        "factor_id": "F-1",
        "per_axis": [
            {
                "axis_id": "D1",
                "verbatim_candidate_quote": "兰蔻防晒霜",
                "bridge_to_anchor": "anchor literal in text",
                "templated_flag": "ok",
                "verdict": "pass",
            },
        ],
        "floor_violations": [],
        "primary_strength": "anchor literal",
        "primary_risk": "none",
        "rationale": "ok",
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
    """decision has a model default of 'hold' — omitting it must NOT raise;
    artifact validates and the missing field is filled in. Locked behavior
    per Plan 02 SUMMARY note 4."""
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
