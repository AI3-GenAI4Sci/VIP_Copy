"""Workflow-node payload contracts for the split personalized-copy pipeline."""

from __future__ import annotations

from typing import Any


# Master_plan §4.5 — locked literal. The audit test grep-checks both string
# substrings ("request/list_group" and "score_all_candidates_together_after_hard_rules").
candidate_generation_policy: dict[str, Any] = {
    "unit": "request/list_group",
    "score_all_candidates_together_after_hard_rules": True,
}

_SUMMARY_PROFILE_KEYS = ("gender", "age", "city_level", "vip_level", "is_svip")
_SUMMARY_CONTEXT_KEYS = ("device_type", "hour")
_PROFILE_COUNT_KEYS = (
    "register_days",
    "click_cnt_30d",
    "order_cnt_30d",
    "order_cnt_90d",
    "purchase_price_avg_30d",
    "fav_price_avg_30d",
    "coupon_use_cnt_30d",
    "cart_cnt_30d",
    "fav_brand_cnt_30d",
)
_BEHAVIOR_TOP_LIST_KEYS = (
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
)
_TARGET_PRODUCT_DERIVED_KEYS = (
    "price_vs_user_baseline_ratio",
    "brand_recent_touched",
    "ctr_band",
    "is_new",
)
_DERIVED_FEATURE_KEYS = (
    "price_vs_user_baseline_ratio",
    "price_vs_user_baseline_bucket",
    "cat3_alignment",
    "brand_alignment",
    "user_typical_brand_level",
    "brand_level_vs_user_history",
    "review_band",
    "ctr_band",
    "is_cold_start_combo",
    "recent_search_intent_distance",
    "user_activity_level",
)
_PRODUCT_ATTRIBUTE_KEYS = (
    "item_name",
    "item_spu_title",
    "item_cat1_name",
    "item_cat3_name",
    "item_brand_name",
    "brand_level",
    "item_arriv_price",
    "tag_price",
    "discount_rate",
    "ctr_7d",
    "cvr_7d",
    "item_satisfy",
    "review_cnt",
    "return_rate_30d",
    "is_new",
    "is_hot",
    "is_exclusive",
    "is_in_user_prefer_brand",
    "is_in_user_prefer_cat3",
    "clicked_count_same_brand_30d",
    "clicked_count_same_cat3_30d",
    "carted_count_same_brand_30d",
    "carted_count_same_cat3_30d",
    "ordered_count_same_brand_90d",
    "ordered_count_same_cat3_90d",
)


def _normalize_payload_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    return value


def _pick_ordered(source: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    source_dict = source if isinstance(source, dict) else {}
    return {key: _normalize_payload_value(source_dict.get(key)) for key in keys}


def _scenario_dict(scenario: Any) -> dict[str, Any]:
    """Coerce a Scenario-like input (pydantic model OR dict) to plain dict."""
    if hasattr(scenario, "model_dump"):
        data = scenario.model_dump(mode="json")  # type: ignore[assignment]
    elif isinstance(scenario, dict):
        data = dict(scenario)
    else:
        raise TypeError(f"unsupported scenario type: {type(scenario).__name__}")
    metadata = data.get("metadata") or {}
    if "derived_features_by_product" not in data and isinstance(metadata, dict):
        derived = metadata.get("derived_features_by_product")
        if isinstance(derived, dict):
            data["derived_features_by_product"] = derived
    if "list_context" not in data and isinstance(metadata, dict):
        list_context = metadata.get("list_context")
        if isinstance(list_context, dict):
            data["list_context"] = list_context
    return data


def _derived_for_products(scenario: dict[str, Any], products: list[dict[str, Any]]) -> dict[str, Any]:
    derived = scenario.get("derived_features_by_product") or {}
    if not isinstance(derived, dict):
        return {}
    return {
        str(product.get("product_id")): _bounded_derived_features(
            derived.get(str(product.get("product_id")), {})
        )
        for product in products
        if str(product.get("product_id")) in derived
    }


def _bounded_derived_features(features: Any) -> dict[str, Any]:
    source = features if isinstance(features, dict) else {}
    return {
        key: _normalize_payload_value(source[key])
        for key in _DERIVED_FEATURE_KEYS
        if key in source
    }


def _target_product_derived_signals(
    scenario: dict[str, Any],
    products: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        product_id: _pick_ordered(features, _TARGET_PRODUCT_DERIVED_KEYS)
        for product_id, features in _derived_for_products(scenario, products).items()
    }


def _bounded_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bounded: list[dict[str, Any]] = []
    for product in products:
        if not isinstance(product, dict):
            continue
        raw_attributes = product.get("attributes") if isinstance(product.get("attributes"), dict) else {}
        out = {
            "product_id": str(product.get("product_id") or ""),
            "group_key": product.get("group_key"),
            "category": product.get("category"),
            "canonical_product_name": product.get("canonical_product_name"),
            "attributes": _pick_ordered(raw_attributes, _PRODUCT_ATTRIBUTE_KEYS),
        }
        observed = product.get("observed")
        if isinstance(observed, dict):
            out["observed"] = {
                key: observed.get(key)
                for key in ("is_clicked", "is_addcart", "is_order", "goods_seq")
                if key in observed
            }
        bounded.append(out)
    return bounded


def _user_state_summary(scenario: dict[str, Any]) -> dict[str, Any]:
    user_state = scenario.get("user_state") if isinstance(scenario.get("user_state"), dict) else {}
    profile = user_state.get("profile") if isinstance(user_state.get("profile"), dict) else {}
    context = user_state.get("context") if isinstance(user_state.get("context"), dict) else {}
    return {
        "profile": _pick_ordered(profile, _SUMMARY_PROFILE_KEYS),
        "context": _pick_ordered(context, _SUMMARY_CONTEXT_KEYS),
    }


def _user_state_signals(
    scenario: dict[str, Any],
    products: list[dict[str, Any]],
) -> dict[str, Any]:
    user_state = scenario.get("user_state") if isinstance(scenario.get("user_state"), dict) else {}
    profile = user_state.get("profile") if isinstance(user_state.get("profile"), dict) else {}
    behavior = user_state.get("behavior") if isinstance(user_state.get("behavior"), dict) else {}
    return {
        "profile_counts": _pick_ordered(profile, _PROFILE_COUNT_KEYS),
        "behavior_top_lists": _pick_ordered(behavior, _BEHAVIOR_TOP_LIST_KEYS),
        "target_product_derived": _target_product_derived_signals(scenario, products),
    }


def user_personalization_payload_for(scenario: Any) -> dict[str, Any]:
    """User-side personalization mining input.

    This node receives user-side features and light list context only. Product
    facts are withheld so user factors stay reusable across request products.
    """
    s = _scenario_dict(scenario)
    products = _bounded_products(list(s.get("products") or []))
    return {
        "schema_version": "request_user_personalization_payload_v1",
        "scenario_id": s.get("scenario_id"),
        "request_id": s.get("request_id"),
        "minimum_semantic_unit": "request/list_group",
        "user_state_summary": _user_state_summary(s),
        "user_state_signals": _user_state_signals(s, products),
        "list_context": s.get("list_context") or {},
    }


def copy_payload_for(
    *,
    scenario: Any,
    user_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Product-side copy-generation input."""
    s = _scenario_dict(scenario)
    artifact = user_artifact or {}
    products = _bounded_products(list(s.get("products") or []))
    return {
        "schema_version": "request_personalized_copy_generation_payload_v1",
        "scenario_id": s.get("scenario_id"),
        "request_id": s.get("request_id"),
        "minimum_semantic_unit": "request/list_group",
        "user_state_summary": _user_state_summary(s),
        "user_factors": list(artifact.get("user_factors") or []),
        "products": products,
        "target_products": products,
        "target_product_count": len(products),
        "candidate_generation_policy": candidate_generation_policy,
        "derived_features_by_product": _derived_for_products(s, products),
        "list_context": s.get("list_context") or {},
    }


def rubric_payload_for(
    *,
    scenario: Any,
    copy_artifact: dict[str, Any] | None = None,
    user_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rubric input with user factors, candidates, and product context."""
    s = _scenario_dict(scenario)
    copy = copy_artifact or {}
    user = user_artifact or {}
    products = _bounded_products(list(s.get("products") or []))
    candidates: list[dict[str, Any]] = []
    for idx, candidate in enumerate(copy.get("candidates") or []):
        candidates.append(
            {
                "candidate_id": candidate.get("candidate_id") or f"candidate-{idx}",
                "candidate_index": idx,
                "product_id": str(candidate.get("product_id") or ""),
                "user_factor_id": str(candidate.get("source_user_factor_id") or ""),
                "copy_text": str(candidate.get("text") or ""),
                "commercial_angle": str(candidate.get("commercial_angle") or ""),
                "product_binding": str(candidate.get("product_binding") or ""),
                "fact_binding": str(candidate.get("fact_binding") or ""),
            }
        )
    return {
        "schema_version": "request_personalized_copy_rubric_payload_v1",
        "scenario_id": s.get("scenario_id"),
        "request_id": s.get("request_id"),
        "minimum_semantic_unit": "request/list_group",
        "user_state_summary": _user_state_summary(s),
        "user_factors": list(user.get("user_factors") or []),
        "products": products,
        "derived_features_by_product": _derived_for_products(s, products),
        "candidates": candidates,
        "candidate_count": len(candidates),
    }


def provider_payload_for_node(
    *,
    node_id: str,
    scenario: Any,
    dependency_payloads: dict[str, dict[str, Any]] | None = None,
    session_id: str = "",
) -> dict[str, Any]:
    """Dispatch to the per-node payload builder.

    Returns ``{"session_id", "scenario", "artifacts"}`` where ``scenario``
    is the node-specific view. Unknown node_ids fall back to the raw
    scenario dict.
    """
    deps = dependency_payloads or {}
    if node_id == "personalized_user_mining":
        view = user_personalization_payload_for(scenario)
    elif node_id == "personalized_copy_generation":
        view = copy_payload_for(
            scenario=scenario,
            user_artifact=deps.get("personalized_user_mining") or {},
        )
    elif node_id == "personalized_copy_rubric":
        view = rubric_payload_for(
            scenario=scenario,
            copy_artifact=deps.get("personalized_copy_generation") or {},
            user_artifact=deps.get("personalized_user_mining") or {},
        )
    else:
        view = _scenario_dict(scenario)
    return {
        "session_id": session_id,
        "scenario": view,
        "artifacts": deps,
    }
