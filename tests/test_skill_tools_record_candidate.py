"""TOOL-03 — record_candidate handler invariants.

Validation order (locked by skill_tools.py docstring):
    (1) drafts integrity   — index in range AND text == drafts[index]
    (2) Arabic-digit
    (3) CN-num-as-value
    (4) length 10..16 visible Chinese chars
    (5) anchor literal     — product_anchor + relation_anchor in text
    (6) user-history leak  — dynamic projection from payload.user_state

Each step has at least one targeted test; two extra tests pin step ordering
so a future refactor that reorders the checks fails loudly.
"""

from __future__ import annotations

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.tools.skill_tools import record_candidate


# Base text passes every step:
#   - 11 visible Chinese chars (in [10, 16])
#   - no Arabic digits, no CN numeral-as-value
#   - product_anchor "兰蔻" and relation_anchor "防晒霜" both literal
#   - no user-history token from the fixture appears in it
_VALID_TEXT = "兰蔻防晒霜温柔守护肌肤"


def _valid_candidate_args(text: str = _VALID_TEXT) -> dict:
    return {
        "candidate_id": "C-1",
        "target_product_id": "P-001",
        "source_factor_id": "F-1",
        "text": text,
        "considered_drafts": [text, "兰蔻防晒霜清爽呵护一整天"],
        "chosen_draft_index": 0,
        "bridge_logic": {
            "product_anchor": "兰蔻",
            "relation_anchor": "防晒霜",
        },
        "used_copyable_hooks": [],
        "intended_effect": "凸显防晒主张",
    }


def test_record_candidate_appends_when_valid(sample_scenario_payload: dict) -> None:
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    out = record_candidate(_valid_candidate_args(), state)
    assert out == "recorded"
    assert len(state["candidates"]) == 1
    assert state["candidates"][0]["candidate_id"] == "C-1"
    assert state["candidates"][0]["text"] == _VALID_TEXT


def test_record_candidate_initializes_candidates_list_when_absent(
    sample_scenario_payload: dict,
) -> None:
    state: dict = {"payload": sample_scenario_payload}
    record_candidate(_valid_candidate_args(), state)
    assert len(state["candidates"]) == 1


def test_record_candidate_rejects_chosen_draft_index_out_of_range(
    sample_scenario_payload: dict,
) -> None:
    args = _valid_candidate_args()
    args["chosen_draft_index"] = 5  # only 2 drafts present
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    assert exc_info.value.tool_name == "record_candidate"
    assert exc_info.value.arg_path == "chosen_draft_index"
    assert state["candidates"] == []


def test_record_candidate_rejects_text_not_matching_chosen_draft(
    sample_scenario_payload: dict,
) -> None:
    args = _valid_candidate_args()
    args["text"] = "兰蔻防晒霜清爽呵护一整天"  # equals drafts[1], not drafts[0]
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    assert exc_info.value.tool_name == "record_candidate"
    assert exc_info.value.arg_path == "text"
    assert "considered_drafts" in exc_info.value.message
    assert state["candidates"] == []


def test_record_candidate_rejects_arabic_digit(sample_scenario_payload: dict) -> None:
    bad_text = "兰蔻防晒霜1温柔守护肌肤"  # 12 visible chars, contains "1"
    args = _valid_candidate_args(bad_text)
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    assert exc_info.value.tool_name == "record_candidate"
    assert exc_info.value.arg_path == "text"
    assert "Arabic digit" in exc_info.value.message
    assert state["candidates"] == []


def test_record_candidate_rejects_chinese_numeral_as_value(
    sample_scenario_payload: dict,
) -> None:
    bad_text = "兰蔻防晒霜三天守护肌肤呢"  # has 三天 — CN num-as-value
    args = _valid_candidate_args(bad_text)
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    assert exc_info.value.tool_name == "record_candidate"
    assert exc_info.value.arg_path == "text"
    assert "Chinese numeral-as-value" in exc_info.value.message
    assert state["candidates"] == []


def test_record_candidate_rejects_text_below_minimum_length(
    sample_scenario_payload: dict,
) -> None:
    bad_text = "兰蔻防晒霜守护肌肤"  # 9 visible chars (< 10)
    args = _valid_candidate_args(bad_text)
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    assert exc_info.value.tool_name == "record_candidate"
    assert exc_info.value.arg_path == "text"
    assert "[10, 16]" in exc_info.value.message
    assert state["candidates"] == []


def test_record_candidate_rejects_text_above_maximum_length(
    sample_scenario_payload: dict,
) -> None:
    bad_text = "兰蔻防晒霜温柔守护肌肤温和清新自然"  # 17 visible chars
    args = _valid_candidate_args(bad_text)
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    assert exc_info.value.tool_name == "record_candidate"
    assert exc_info.value.arg_path == "text"
    assert "[10, 16]" in exc_info.value.message
    assert state["candidates"] == []


def test_record_candidate_rejects_missing_product_anchor(
    sample_scenario_payload: dict,
) -> None:
    args = _valid_candidate_args()
    args["bridge_logic"]["product_anchor"] = "雅诗兰黛"  # not in text
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    assert exc_info.value.tool_name == "record_candidate"
    assert exc_info.value.arg_path == "bridge_logic.product_anchor"
    assert state["candidates"] == []


def test_record_candidate_rejects_missing_relation_anchor(
    sample_scenario_payload: dict,
) -> None:
    args = _valid_candidate_args()
    # product_anchor still in text; relation_anchor swapped to a substring not
    # present in text so we hit the relation_anchor branch specifically.
    args["bridge_logic"]["relation_anchor"] = "守护肌肤之美"
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    assert exc_info.value.tool_name == "record_candidate"
    assert exc_info.value.arg_path == "bridge_logic.relation_anchor"
    assert state["candidates"] == []


def test_record_candidate_rejects_user_history_leak(
    sample_scenario_payload: dict,
) -> None:
    # "维生素" is a recent-search token in the fixture and is not present in
    # P-001's product attributes — record_candidate must reject it.
    leaky_text = "兰蔻防晒霜伴你维生素满分肌肤"
    args = _valid_candidate_args(leaky_text)
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    assert exc_info.value.tool_name == "record_candidate"
    assert exc_info.value.arg_path == "text"
    assert "维生素" in exc_info.value.message
    assert state["candidates"] == []


def test_record_candidate_drafts_check_runs_before_arabic_check(
    sample_scenario_payload: dict,
) -> None:
    """Step (1) drafts integrity must fire before step (2) Arabic-digit."""
    args = _valid_candidate_args()
    # text contains an Arabic digit AND does not match drafts[0].
    args["text"] = "兰蔻防晒霜1温柔守护肌肤"
    # drafts unchanged — drafts[0] is the digit-free _VALID_TEXT.
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    # Error must come from step (1), not step (2).
    assert "considered_drafts" in exc_info.value.message
    assert "Arabic digit" not in exc_info.value.message
    assert exc_info.value.arg_path == "text"


def test_record_candidate_arabic_check_runs_before_length_check(
    sample_scenario_payload: dict,
) -> None:
    """Step (2) Arabic-digit must fire before step (4) length."""
    # Text is 8 visible chars (would fail length) AND contains "1".
    bad_text = "兰蔻防晒霜1温柔"
    args = _valid_candidate_args(bad_text)
    state: dict = {"payload": sample_scenario_payload, "candidates": []}
    with pytest.raises(ToolValidationError) as exc_info:
        record_candidate(args, state)
    # Error must come from step (2), not step (4).
    assert "Arabic digit" in exc_info.value.message
    assert "[10, 16]" not in exc_info.value.message
    assert exc_info.value.arg_path == "text"
