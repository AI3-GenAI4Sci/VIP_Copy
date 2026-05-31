"""maintain_copy_artifact handler invariants."""

from __future__ import annotations

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.tools.skill_tools import maintain_copy_artifact


def _candidate(candidate_id: str = "C-1", product_id: str = "P-001") -> dict:
    return {
        "candidate_id": candidate_id,
        "product_id": product_id,
        "source_user_factor_id": "UF-1",
        "text": "带娃晒一天，回家脸也不狼狈",
        "commercial_angle": "场景痛点",
        "product_binding": "防晒商品承接户外场景",
        "fact_binding": "商品防晒卖点承接表达",
    }


def _args(action: str, **overrides: object) -> dict:
    base = {
        "action": action,
        "candidates": [],
        "candidate_ids": [],
        "product_id": "",
    }
    base.update(overrides)
    return base


def test_maintain_copy_artifact_upserts_many_by_candidate_id() -> None:
    state: dict = {"candidates": [_candidate("C-1")]}
    replacement = {**_candidate("C-1"), "text": "不懂护肤也会选，晒完不红脸"}
    new_candidate = _candidate("C-2", "P-001")

    out = maintain_copy_artifact(
        _args("upsert_many", candidates=[replacement, new_candidate]),
        state,
    )

    assert out == "updated"
    assert [c["candidate_id"] for c in state["candidates"]] == ["C-1", "C-2"]
    assert state["candidates"][0]["text"] == "不懂护肤也会选，晒完不红脸"


def test_maintain_copy_artifact_delete_many_removes_ids() -> None:
    state: dict = {"candidates": [_candidate("C-1"), _candidate("C-2")]}
    out = maintain_copy_artifact(_args("delete_many", candidate_ids=["C-1"]), state)
    assert out == "updated"
    assert [c["candidate_id"] for c in state["candidates"]] == ["C-2"]


def test_maintain_copy_artifact_save_sets_final_and_copies_artifacts() -> None:
    state: dict = {"candidates": [_candidate()]}
    out = maintain_copy_artifact(_args("save"), state)
    assert out == "saved"
    assert state["final_artifact"] == {"candidates": [_candidate()]}
    assert state["copies_artifact"] == state["final_artifact"]


def test_maintain_copy_artifact_returns_json_on_read() -> None:
    state: dict = {"candidates": [_candidate()]}
    out = maintain_copy_artifact(_args("read"), state)
    assert '"candidates"' in out
    assert '"candidate_id":"C-1"' in out


def test_maintain_copy_artifact_validates_schema_without_style_rules() -> None:
    state: dict = {}
    numeric_copy = {**_candidate(), "text": "SPF50也能轻松出门"}
    out = maintain_copy_artifact(_args("upsert_many", candidates=[numeric_copy]), state)
    assert out == "updated"
    assert state["candidates"][0]["text"] == "SPF50也能轻松出门"


def test_maintain_copy_artifact_rejects_unknown_schema_fields() -> None:
    state: dict = {}
    bad_candidate = {**_candidate(), "bridge_logic": {"product_anchor": "兰蔻"}}
    with pytest.raises(ToolValidationError) as exc_info:
        maintain_copy_artifact(_args("upsert_many", candidates=[bad_candidate]), state)
    assert exc_info.value.tool_name == "maintain_copy_artifact"
    assert "bridge_logic" in exc_info.value.message
    assert "candidates" not in state
