"""Tool registry and artifact handlers for the split personalized pipeline."""

from __future__ import annotations

from seers_harness.tools.skill_tools import (
    MAINTAIN_USER_FACTORS_ARTIFACT_SPEC,
    TOOL_HANDLERS,
    TOOLS_SPEC,
    maintain_copy_artifact,
    maintain_user_factors_artifact,
)


def _valid_user_factor() -> dict:
    return {
        "user_factor_id": "UF-1",
        "signal_basis": "深夜活跃且近期反复浏览护肤/营养相关类目",
        "need_or_pain": "希望改善熬夜后的状态，同时降低尝试成本",
        "scene_trigger": "23 点睡前刷购",
        "buying_heuristic": "偏好高口碑、低门槛尝试的日常调理品",
        "expression_hooks": ["熬夜脸", "低门槛", "高口碑"],
        "evidence_refs": [{"path": "user_state_signals.behavior_top_lists.prefer_cat3_topK", "value": None}],
    }


def _valid_candidate() -> dict:
    return {
        "candidate_id": "C-1",
        "product_id": "P-1",
        "source_user_factor_id": "UF-1",
        "text": "熬夜脸也能轻松修护",
        "commercial_angle": "熬夜痛点前置",
        "product_binding": "维 B 商品承接熬夜后调理诉求",
        "fact_binding": "商品标题含维 B/舒缓压力/改善痘肌",
    }


def test_tools_spec_uses_split_skill_keys_and_tools() -> None:
    assert set(TOOLS_SPEC) == {
        "personalized-user-mining",
        "personalized-copy-generation",
        "personalized-copy-rubric-judge",
    }
    assert [t["function"]["name"] for t in TOOLS_SPEC["personalized-user-mining"]] == [
        "maintain_user_factors_artifact",
        "reflect_on_user_factor_coverage",
    ]
    assert [t["function"]["name"] for t in TOOLS_SPEC["personalized-copy-generation"]] == [
        "maintain_copy_artifact",
        "reflect_on_copy_quality",
    ]


def test_user_factor_artifact_spec_uses_user_side_schema() -> None:
    props = MAINTAIN_USER_FACTORS_ARTIFACT_SPEC["function"]["parameters"]["properties"]
    item_props = props["user_factors"]["items"]["properties"]
    assert list(item_props) == [
        "user_factor_id",
        "signal_basis",
        "need_or_pain",
        "scene_trigger",
        "buying_heuristic",
        "expression_hooks",
        "evidence_refs",
    ]


def test_user_factor_save_finalizes_user_personalization_artifact() -> None:
    state = {"user_factors": [_valid_user_factor()]}
    out = maintain_user_factors_artifact({"action": "save", "user_factors": [], "user_factor_ids": []}, state)
    assert out == "saved"
    assert state["final_artifact"]["user_factors"][0]["user_factor_id"] == "UF-1"


def test_copy_save_uses_new_candidate_schema() -> None:
    state = {"candidates": [_valid_candidate()]}
    out = maintain_copy_artifact({"action": "save", "candidates": [], "candidate_ids": [], "product_id": ""}, state)
    assert out == "saved"
    assert state["final_artifact"]["candidates"][0]["source_user_factor_id"] == "UF-1"


def test_old_factor_handler_removed() -> None:
    assert "maintain_factor_artifact" not in TOOL_HANDLERS
