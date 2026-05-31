"""Payload boundaries for the split personalized-copy workflow."""

from __future__ import annotations

from seers_harness.workflow.payloads import (
    copy_payload_for,
    provider_payload_for_node,
    rubric_payload_for,
    user_personalization_payload_for,
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
                "addcart_cat3_id_list_topN": "护肤",
                "collect_brand_id_list_topN": "品牌E",
                "click_brand_id_list_topN": "品牌F",
                "click_goods_id_list_topN": "不应披露",
            },
            "context": {"device_type": "iPhone", "hour": 23, "day_of_week": 3},
        },
        "products": [
            {
                "product_id": "P-1",
                "group_key": "维生素",
                "canonical_product_name": "叶酸片",
                "attributes": {"item_name": "叶酸片", "item_arriv_price": 39.9},
            }
        ],
        "metadata": {
            "derived_features_by_product": {
                "P-1": {
                    "price_vs_user_baseline_ratio": 0.87654,
                    "brand_recent_touched": True,
                    "ctr_band": "high",
                    "is_new": False,
                }
            },
            "list_context": {"target_categories": ["维生素"]},
        },
    }


def _user_artifact() -> dict:
    return {
        "user_factors": [
            {
                "user_factor_id": "UF-1",
                "signal_basis": "深夜活跃且近期浏览维生素",
                "need_or_pain": "希望低门槛改善熬夜状态",
                "scene_trigger": "23 点睡前刷购",
                "buying_heuristic": "看重高口碑和低门槛",
                "expression_hooks": ["熬夜脸", "低门槛"],
                "evidence_refs": [{"path": "user_state_signals.behavior_top_lists.prefer_cat3_topK", "value": None}],
            }
        ]
    }


def test_user_personalization_payload_is_user_side_only() -> None:
    payload = user_personalization_payload_for(_scenario())
    assert payload["schema_version"] == "request_user_personalization_payload_v1"
    assert "products" not in payload
    assert "target_products" not in payload
    assert payload["user_state_summary"]["context"]["hour"] == 23
    assert payload["user_state_signals"]["behavior_top_lists"]["prefer_cat3_topK"] == "保健食品,维生素"
    assert "private-user" not in repr(payload)
    assert "click_goods_id_list_topN" not in repr(payload)


def test_copy_payload_uses_user_factors_and_product_context_without_behavior_lists() -> None:
    payload = copy_payload_for(scenario=_scenario(), user_artifact=_user_artifact())
    assert payload["schema_version"] == "request_personalized_copy_generation_payload_v1"
    assert payload["user_factors"] == _user_artifact()["user_factors"]
    assert payload["target_products"][0]["product_id"] == "P-1"
    assert "user_state_signals" not in payload
    assert "derived_features_by_product" in payload


def test_provider_payload_routes_three_nodes() -> None:
    deps = {"personalized_user_mining": _user_artifact()}
    user_payload = provider_payload_for_node(node_id="personalized_user_mining", scenario=_scenario())["scenario"]
    copy_payload = provider_payload_for_node(node_id="personalized_copy_generation", scenario=_scenario(), dependency_payloads=deps)["scenario"]
    assert user_payload["schema_version"] == "request_user_personalization_payload_v1"
    assert copy_payload["user_factors"] == _user_artifact()["user_factors"]


def test_rubric_payload_uses_user_factors_candidates_and_products() -> None:
    copy_artifact = {"candidates": [{"candidate_id": "C-1", "product_id": "P-1", "source_user_factor_id": "UF-1", "text": "熬夜脸也能轻松修护", "commercial_angle": "痛点前置", "product_binding": "维 B 承接调理", "fact_binding": "标题含维 B"}]}
    payload = rubric_payload_for(scenario=_scenario(), copy_artifact=copy_artifact, user_artifact=_user_artifact())
    assert payload["user_factors"] == _user_artifact()["user_factors"]
    assert payload["candidates"][0]["user_factor_id"] == "UF-1"
    assert payload["products"][0]["product_id"] == "P-1"
