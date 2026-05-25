"""TOOL-05 — judge_candidate handler invariants.

judge_candidate reads candidate text from state['copies_artifact']['candidates']
(set by submit_copies_final in the prior loop iteration). For every per_axis
verdict with a non-empty verbatim_candidate_quote, the quote MUST be a literal
substring of the candidate text.
"""

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
        "factor_id": "F-1",
        "per_axis": [
            {
                "axis_id": "D1",
                "verbatim_candidate_quote": "兰蔻防晒霜",
                "bridge_to_anchor": "anchor literal in text",
                "templated_flag": "ok",
                "verdict": "pass",
            },
            {
                "axis_id": "D2",
                "verbatim_candidate_quote": "温柔守护",
                "bridge_to_anchor": "warmth motif",
                "templated_flag": "ok",
                "verdict": "pass",
            },
        ],
        "floor_violations": [],
        "primary_strength": "anchor literal",
        "primary_risk": "none",
        "rationale": "all axes pass",
        "decision": "admit",
    }


def test_judge_candidate_passes_when_all_quotes_in_text() -> None:
    state = _seed_state_with_candidate()
    out = judge_candidate(_valid_judgment(), state)
    assert out == "recorded"
    assert len(state["judgments"]) == 1
    assert state["judgments"][0]["candidate_id"] == "C-1"
    assert state["judgments"][0]["decision"] == "admit"


def test_judge_candidate_rejects_quote_not_in_text() -> None:
    state = _seed_state_with_candidate()
    bad_judgment = _valid_judgment()
    bad_judgment["per_axis"][1]["verbatim_candidate_quote"] = "完全不在文本里"
    with pytest.raises(ToolValidationError) as exc_info:
        judge_candidate(bad_judgment, state)
    assert exc_info.value.tool_name == "judge_candidate"
    assert "verbatim_candidate_quote" in exc_info.value.arg_path
    assert "D2" in exc_info.value.arg_path
    assert "judgments" not in state or state["judgments"] == []


def test_judge_candidate_allows_empty_quote() -> None:
    """An empty verbatim_candidate_quote skips the substring check
    (axis can still emit verdict without quoting)."""
    state = _seed_state_with_candidate()
    judgment = _valid_judgment()
    judgment["per_axis"][1]["verbatim_candidate_quote"] = ""
    judgment["per_axis"][1]["templated_flag"] = "empty"
    out = judge_candidate(judgment, state)
    assert out == "recorded"
    assert len(state["judgments"]) == 1


def test_judge_candidate_rejects_unknown_candidate_id_when_quotes_present() -> None:
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
