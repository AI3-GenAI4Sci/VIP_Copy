from __future__ import annotations

import pathlib
import re

from seers_harness.workflow.payloads import (
    copy_payload_for,
    provider_payload_for_node,
    rubric_payload_for,
    user_personalization_payload_for,
)


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
ANALYSIS_PATH = PROJECT_ROOT / "seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md"
SKILL_PATH = PROJECT_ROOT / "workflow-skills/current/personalized-copy-generation/SKILL.md"

SUMMARY_PROFILE_KEYS = ["gender", "age", "city_level", "vip_level", "is_svip"]
SUMMARY_CONTEXT_KEYS = ["device_type", "hour"]
PROFILE_COUNT_KEYS = [
    "register_days",
    "click_cnt_30d",
    "order_cnt_30d",
    "order_cnt_90d",
    "purchase_price_avg_30d",
    "fav_price_avg_30d",
    "coupon_use_cnt_30d",
    "cart_cnt_30d",
    "fav_brand_cnt_30d",
]
BEHAVIOR_TOP_LIST_KEYS = [
    "prefer_cat3_topK",
    "prefer_brand_topK",
    "seq_click_cat3_48h",
    "seq_click_brand_48h",
    "order_goods_id_list_topN",
    "order_brand_id_list_topN",
    "order_cat3_id_list_topN",
    "addcart_goods_id_list_topN",
    "addcart_brand_id_list_topN",
    "addcart_cat3_id_list_topN",
    "collect_goods_id_list_topN",
    "collect_brand_id_list_topN",
    "click_brand_id_list_topN",
]
TARGET_PRODUCT_DERIVED_KEYS = [
    "price_vs_user_baseline_ratio",
    "brand_recent_touched",
    "ctr_band",
    "is_new",
]
FORBIDDEN_SKILL_PATTERN = re.compile(
    r"低.{0,3}价.{0,3}大牌|大牌.{0,3}不贵|周三|代理父亲|信息饕餮|多娃妈妈|金卡仪式|睡前种草"
)


def _scenario() -> dict:
    return {
        "scenario_id": "S-1",
        "request_id": "R-1",
        "user_state": {
            "profile": {
                "user_id": "private-user",
                "gender": "女",
                "age": 31,
                "city_level": "二线城市",
                "region_level": "云南省",
                "vip_level": "金卡会员",
                "is_svip": 1,
                "register_days": 2936,
                "click_cnt_30d": 77,
                "order_cnt_30d": 3,
                "order_cnt_90d": 15,
                "purchase_price_avg_30d": 42.333332,
                "fav_price_avg_30d": 108.126,
                "coupon_use_cnt_30d": 0,
                "cart_cnt_30d": 5,
                "fav_brand_cnt_30d": 7,
            },
            "behavior": {
                "prefer_cat3_topK": "保健食品,维生素",
                "prefer_brand_topK": "品牌A,品牌B",
                "seq_click_cat3_48h": "维生素>叶酸",
                "seq_click_brand_48h": "品牌A",
                "order_goods_id_list_topN": "1001,1002",
                "order_brand_id_list_topN": "品牌C",
                "order_cat3_id_list_topN": "营养品",
                "addcart_goods_id_list_topN": "2001,2002",
                "addcart_brand_id_list_topN": "品牌D",
                "addcart_cat3_id_list_topN": "护肤",
                "collect_goods_id_list_topN": "3001,3002",
                "collect_brand_id_list_topN": "品牌E",
                "collect_cat3_id_list_topN": "不应披露",
                "click_brand_id_list_topN": "品牌F",
                "click_goods_id_list_topN": "不应披露",
                "click_cat3_id_list_topN": "不应披露",
            },
            "context": {
                "device_type": "iPhone",
                "hour": 9,
                "day_of_week": 3,
            },
        },
        "products": [
            {
                "product_id": "P-1",
                "group_key": "维生素",
                "canonical_product_name": "叶酸片",
                "attributes": {
                    "item_name": "叶酸片",
                    "item_arriv_price": 39.9,
                    "click_timestamp_list_topN": list(range(100)),
                    "title_attr_size": "0,0,0,0,0,0,0,0,0,0",
                },
            },
            {
                "product_id": "P-2",
                "group_key": "护肤",
                "canonical_product_name": "面霜",
                "attributes": {
                    "item_name": "面霜",
                    "item_arriv_price": 99.0,
                    "click_timestamp_list_topN": list(range(100)),
                },
            },
        ],
        "metadata": {
            "derived_features_by_product": {
                "P-1": {
                    "price_vs_user_baseline_ratio": 0.87654,
                    "brand_recent_touched": True,
                    "ctr_band": "high",
                    "is_new": False,
                    "click_timestamp_list_topN": [1, 2, 3],
                },
                "P-2": {
                    "price_vs_user_baseline_ratio": 1.23456,
                    "brand_recent_touched": False,
                    "ctr_band": "mid",
                    "is_new": True,
                },
            },
            "list_context": {"target_categories": ["维生素"]},
        },
    }


def _user_artifact() -> dict:
    return {
        "user_factors": [
            {
                "user_factor_id": "UF-1",
                "signal_basis": "近期反复浏览熟悉品牌的基础营养品",
                "need_or_pain": "更信任熟悉品牌带来的低风险选择感",
                "scene_trigger": "早餐后补充营养",
                "buying_heuristic": "偏好省心、顺手、日常可坚持",
                "expression_hooks": ["熟悉品牌", "低风险", "日常坚持"],
                "evidence_refs": [{"path": "user_state_signals.behavior_top_lists.prefer_brand_topK", "value": None}],
            }
        ]
    }


def _copy_artifact() -> dict:
    return {
        "candidates": [
            {
                "candidate_id": "C-1",
                "product_id": "P-1",
                "source_user_factor_id": "UF-1",
                "text": "熟悉补充更安心",
                "commercial_angle": "品牌信任",
                "product_binding": "叶酸片承接基础营养补充诉求",
                "fact_binding": "商品类目和品牌关系稳定",
            }
        ]
    }


def test_context_disclosure_analysis_has_signed_boundary():
    text = ANALYSIS_PATH.read_text(encoding="utf-8")
    assert re.search(r"^Sign-off:\s*\d{4}-\d{2}-\d{2}", text, re.MULTILINE)


def test_user_personalization_payload_discloses_only_user_side_field_groups():
    payload = user_personalization_payload_for(_scenario())

    assert payload["schema_version"] == "request_user_personalization_payload_v1"
    assert list(payload["user_state_summary"]["profile"]) == SUMMARY_PROFILE_KEYS
    assert list(payload["user_state_summary"]["context"]) == SUMMARY_CONTEXT_KEYS
    assert list(payload["user_state_signals"]["profile_counts"]) == PROFILE_COUNT_KEYS
    assert list(payload["user_state_signals"]["behavior_top_lists"]) == BEHAVIOR_TOP_LIST_KEYS
    assert list(payload["user_state_signals"]["target_product_derived"]["P-1"]) == TARGET_PRODUCT_DERIVED_KEYS

    serialized = repr(payload)
    for excluded in (
        "private-user",
        "region_level",
        "day_of_week",
        "click_goods_id_list_topN",
        "collect_cat3_id_topN",
        "click_timestamp_list_topN",
        "title_attr_size",
    ):
        assert excluded not in serialized


def test_copy_payload_receives_user_factors_and_product_context_without_behavior_lists():
    payload = copy_payload_for(scenario=_scenario(), user_artifact=_user_artifact())

    assert payload["schema_version"] == "request_personalized_copy_generation_payload_v1"
    assert payload["user_factors"] == _user_artifact()["user_factors"]
    assert payload["target_products"][0]["product_id"] == "P-1"
    assert payload["derived_features_by_product"]["P-1"]["price_vs_user_baseline_ratio"] == 0.88
    assert "user_state_signals" not in payload
    assert "profile_counts" not in repr(payload)


def test_rubric_payload_receives_user_factors_candidates_and_product_context():
    payload = rubric_payload_for(
        scenario=_scenario(),
        copy_artifact=_copy_artifact(),
        user_artifact=_user_artifact(),
    )

    assert payload["schema_version"] == "request_personalized_copy_rubric_payload_v1"
    assert payload["user_factors"] == _user_artifact()["user_factors"]
    assert payload["candidates"][0]["copy_text"] == "熟悉补充更安心"
    assert payload["candidates"][0]["user_factor_id"] == "UF-1"
    assert payload["candidates"][0]["product_binding"] == "叶酸片承接基础营养补充诉求"


def test_skill_generation_doc_names_new_copy_artifact_without_old_factor_schema():
    text = SKILL_PATH.read_text(encoding="utf-8")

    for expected in [
        "user_factors",
        "source_user_factor_id",
        "commercial_angle",
        "product_binding",
        "fact_binding",
        "maintain_copy_artifact",
    ]:
        assert expected in text
    for forbidden in [
        "maintain_factor_artifact",
        "source_factor_id",
        "signal_pattern",
        "product_fit",
        "manifestation",
    ]:
        assert forbidden not in text
    assert not FORBIDDEN_SKILL_PATTERN.search(text)


def test_provider_payload_dispatches_three_split_nodes():
    user_payload = provider_payload_for_node(
        node_id="personalized_user_mining",
        scenario=_scenario(),
        session_id="session-1",
    )
    copy_payload = provider_payload_for_node(
        node_id="personalized_copy_generation",
        scenario=_scenario(),
        dependency_payloads={"personalized_user_mining": _user_artifact()},
        session_id="session-2",
    )
    rubric_payload = provider_payload_for_node(
        node_id="personalized_copy_rubric",
        scenario=_scenario(),
        dependency_payloads={
            "personalized_user_mining": _user_artifact(),
            "personalized_copy_generation": _copy_artifact(),
        },
        session_id="session-3",
    )

    assert user_payload["session_id"] == "session-1"
    assert copy_payload["scenario"]["user_factors"] == _user_artifact()["user_factors"]
    assert rubric_payload["scenario"]["candidates"][0]["copy_text"] == "熟悉补充更安心"
