"""Workflow-node payload contracts for the tool-use loop (LOOP-06).

Each node sees a strictly bounded view of the Scenario:
  - factor_discovery sees user_state.behavior + products + derived features.
  - copy_generation sees factors + product facts + derived features +
    candidate_generation_policy + the signed-off user_state disclosure
    boundary. It never receives raw user_state wholesale (one factor surfaces
    zero, one, or many candidates depending on signal richness; the harness
    sends no fan-out quota to the model — see master_plan §4.5).
  - personalized_copy_rubric sees rubric-shaped candidates + product facts +
    the same bounded user_state disclosure and candidate bridge logic.

Per master_plan §4.5, ``candidate_generation_policy`` is locked to exactly
two keys (``unit`` and ``score_all_candidates_together_after_hard_rules``);
any other quota-shaped field declared in this module is structurally
rejected by ``tests/test_payloads_loop06_audit.py``.

The candidate_generation_policy dict at module level is the load-bearing
contract: master_plan §4.5 fixes its two keys exactly.
"""

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
        str(product.get("product_id")): derived.get(str(product.get("product_id")), {})
        for product in products
        if str(product.get("product_id")) in derived
    }


def _target_product_derived_signals(
    scenario: dict[str, Any],
    products: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        product_id: _pick_ordered(features, _TARGET_PRODUCT_DERIVED_KEYS)
        for product_id, features in _derived_for_products(scenario, products).items()
    }


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


def factor_payload_for(scenario: Any) -> dict[str, Any]:
    """Request-level factor-discovery input.

    User history appears once per request/list_group; product selection is
    represented as the products list (no per-item prompt fan-out).
    """
    s = _scenario_dict(scenario)
    products = list(s.get("products") or [])
    return {
        "scenario_id": s.get("scenario_id"),
        "request_id": s.get("request_id"),
        "minimum_semantic_unit": "request/list_group",
        "user_state": s.get("user_state") or {},
        "products": products,
        "target_products": products,
        "target_product_count": len(products),
        "derived_features_by_product": _derived_for_products(s, products),
        "list_context": s.get("list_context") or {},
    }


def copy_payload_for(
    *,
    scenario: Any,
    factors_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Request-level copy-generation input.

    No raw user_state wholesale: only the signed G2 disclosure boundary is
    included. Quantity is the SKILL's judgment, not the harness's: the policy
    dict tells the model the unit is request/list_group and that all candidates
    are scored together after hard rules. No fan-out quota.
    """
    s = _scenario_dict(scenario)
    artifact = factors_artifact or {}
    products = list(s.get("products") or [])
    return {
        "scenario_id": s.get("scenario_id"),
        "request_id": s.get("request_id"),
        "minimum_semantic_unit": "request/list_group",
        "user_state_summary": _user_state_summary(s),
        "factors": list(artifact.get("factors") or artifact.get("personalization_factors") or []),
        "products": products,
        "target_products": products,
        "target_product_count": len(products),
        "candidate_generation_policy": candidate_generation_policy,
        "derived_features_by_product": _derived_for_products(s, products),
        "list_context": s.get("list_context") or {},
        "user_state_signals": _user_state_signals(s, products),
    }


def rubric_payload_for(
    *,
    scenario: Any,
    copy_artifact: dict[str, Any] | None = None,
    factors_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Request-level rubric input — candidates + product facts.

    Each ``copy_artifact`` candidate becomes one rubric input row keyed by
    candidate_index.
    """
    s = _scenario_dict(scenario)
    copy = copy_artifact or {}
    factors = factors_artifact or {}
    products = list(s.get("products") or [])
    candidates: list[dict[str, Any]] = []
    for idx, candidate in enumerate(copy.get("candidates") or []):
        candidates.append(
            {
                "candidate_id": candidate.get("candidate_id") or f"candidate-{idx}",
                "candidate_index": idx,
                "product_id": str(candidate.get("product_id") or ""),
                "factor_id": str(candidate.get("source_factor_id") or ""),
                "copy_text": str(candidate.get("text") or ""),
                "group_key": str(candidate.get("group_key") or ""),
                "bridge_logic": dict(candidate.get("bridge_logic") or {}),
                "used_copyable_hooks": list(candidate.get("used_copyable_hooks") or []),
                "intended_effect": str(candidate.get("intended_effect") or ""),
            }
        )
    return {
        "schema_version": "request_personalized_copy_rubric_payload_v1",
        "scenario_id": s.get("scenario_id"),
        "request_id": s.get("request_id"),
        "minimum_semantic_unit": "request/list_group",
        "user_state_summary": _user_state_summary(s),
        "user_state_signals": _user_state_signals(s, products),
        "factors": list(factors.get("factors") or factors.get("personalization_factors") or []),
        "products": products,
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
    is the node-specific view (built by factor_payload_for / copy_payload_for /
    rubric_payload_for). Unknown node_ids fall back to the raw scenario dict.
    """
    deps = dependency_payloads or {}
    if node_id == "factor_discovery":
        view = factor_payload_for(scenario)
    elif node_id == "copy_generation":
        view = copy_payload_for(
            scenario=scenario,
            factors_artifact=deps.get("factor_discovery") or {},
        )
    elif node_id == "personalized_copy_rubric":
        view = rubric_payload_for(
            scenario=scenario,
            copy_artifact=deps.get("copy_generation") or {},
            factors_artifact=deps.get("factor_discovery") or {},
        )
    else:
        view = _scenario_dict(scenario)
    return {
        "session_id": session_id,
        "scenario": view,
        "artifacts": deps,
    }
