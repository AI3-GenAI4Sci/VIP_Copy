from __future__ import annotations

import pathlib
import re

from seers_harness.workflow.payloads import (
    copy_payload_for,
    provider_payload_for_node,
    rubric_payload_for,
)


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
ANALYSIS_PATH = PROJECT_ROOT / "seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md"
SKILL_PATH = PROJECT_ROOT / "workflow-skills/current/generate-copy-candidates/SKILL.md"

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
            {"product_id": "P-1", "group_key": "维生素", "canonical_product_name": "叶酸片"},
            {"product_id": "P-2", "group_key": "护肤", "canonical_product_name": "面霜"},
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


def _factors_artifact() -> dict:
    return {
        "factors": [
            {
                "factor_id": "F-1",
                "transferable_disposition": "更信任熟悉品牌的稳妥选择",
                "evidence_refs": [{"value": "品牌A"}],
            }
        ]
    }


def _copy_artifact() -> dict:
    return {
        "candidates": [
            {
                "candidate_id": "C-1",
                "product_id": "P-1",
                "source_factor_id": "F-1",
                "text": "熟悉那一口，今天也稳",
                "group_key": "维生素",
                "bridge_logic": {
                    "product_anchor": "熟悉",
                    "relation_anchor": "稳",
                },
                "used_copyable_hooks": ["熟悉品牌"],
                "intended_effect": "把熟悉感变成低风险的选择理由",
            }
        ]
    }


def test_context_disclosure_analysis_has_signed_boundary():
    text = ANALYSIS_PATH.read_text(encoding="utf-8")

    assert re.search(r"^Sign-off:\s*\d{4}-\d{2}-\d{2}", text, re.MULTILINE)


def test_copy_payload_discloses_only_signed_field_groups_in_fixed_order():
    payload = copy_payload_for(scenario=_scenario(), factors_artifact=_factors_artifact())

    assert list(payload["user_state_summary"]["profile"]) == SUMMARY_PROFILE_KEYS
    assert list(payload["user_state_summary"]["context"]) == SUMMARY_CONTEXT_KEYS
    assert list(payload["user_state_signals"]["profile_counts"]) == PROFILE_COUNT_KEYS
    assert list(payload["user_state_signals"]["behavior_top_lists"]) == BEHAVIOR_TOP_LIST_KEYS
    assert list(payload["user_state_signals"]["target_product_derived"]["P-1"]) == TARGET_PRODUCT_DERIVED_KEYS
    assert list(payload["user_state_signals"]["target_product_derived"]["P-2"]) == TARGET_PRODUCT_DERIVED_KEYS

    assert payload["user_state_signals"]["profile_counts"]["purchase_price_avg_30d"] == 42.33
    assert payload["user_state_signals"]["profile_counts"]["fav_price_avg_30d"] == 108.13
    assert payload["user_state_signals"]["target_product_derived"]["P-1"]["price_vs_user_baseline_ratio"] == 0.88

    serialized = repr(payload["user_state_summary"]) + repr(payload["user_state_signals"])
    for excluded in (
        "private-user",
        "region_level",
        "day_of_week",
        "click_goods_id_list_topN",
        "collect_cat3_id_list_topN",
        "click_cat3_id_list_topN",
        "click_timestamp_list_topN",
    ):
        assert excluded not in serialized


def test_rubric_payload_receives_factors_user_signals_and_candidate_bridge_logic():
    payload = rubric_payload_for(
        scenario=_scenario(),
        copy_artifact=_copy_artifact(),
        factors_artifact=_factors_artifact(),
    )

    assert payload["factors"] == _factors_artifact()["factors"]
    assert payload["user_state_summary"]["profile"]["gender"] == "女"
    assert payload["user_state_signals"]["behavior_top_lists"]["prefer_cat3_topK"] == "保健食品,维生素"
    assert payload["candidates"][0]["bridge_logic"] == {
        "product_anchor": "熟悉",
        "relation_anchor": "稳",
    }
    assert payload["candidates"][0]["used_copyable_hooks"] == ["熟悉品牌"]
    assert payload["candidates"][0]["intended_effect"] == "把熟悉感变成低风险的选择理由"


def test_skill_hook_rule_allows_signed_payload_fields_without_user_history_literals():
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "Hook words come only from" not in text
    assert "Hook anchors may be drawn" in text
    assert "user_state_summary" in text
    assert "user_state_signals" in text
    assert "target_products" in text
    assert "derived_features_by_product" in text
    assert not FORBIDDEN_SKILL_PATTERN.search(text)


def test_provider_payload_dispatches_rubric_with_factor_and_copy_artifacts():
    payload = provider_payload_for_node(
        node_id="personalized_copy_rubric",
        scenario=_scenario(),
        dependency_payloads={
            "factor_discovery": _factors_artifact(),
            "copy_generation": _copy_artifact(),
        },
        session_id="session-1",
    )

    assert payload["session_id"] == "session-1"
    assert payload["scenario"]["factors"] == _factors_artifact()["factors"]
    assert payload["scenario"]["candidates"][0]["bridge_logic"]["relation_anchor"] == "稳"


def test_rubric_payload_keeps_copy_artifact_only_call_backward_compatible():
    payload = rubric_payload_for(scenario=_scenario(), copy_artifact=_copy_artifact())

    assert payload["factors"] == []
    assert payload["candidates"][0]["candidate_id"] == "C-1"
