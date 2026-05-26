"""Workflow-node payload contracts for the tool-use loop (LOOP-06).

Each node sees a strictly bounded view of the Scenario:
  - factor_discovery sees user_state.behavior + products + derived features.
  - copy_generation sees factors + product facts + derived features +
    candidate_generation_policy. NO raw user_state — copy lines are derived
    from the public factor signals (one factor surfaces zero, one, or many
    candidates depending on signal richness; the harness sends no fan-out
    quota to the model — see master_plan §4.5).
  - personalized_copy_rubric sees rubric-shaped candidates + product facts.

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

    NO raw user_state — copy lines are derived from the public factor signals
    in factors_artifact. Quantity is the SKILL's judgment, not the harness's:
    the policy dict tells the model the unit is request/list_group and that
    all candidates are scored together after hard rules. No fan-out quota.
    """
    s = _scenario_dict(scenario)
    artifact = factors_artifact or {}
    products = list(s.get("products") or [])
    return {
        "scenario_id": s.get("scenario_id"),
        "request_id": s.get("request_id"),
        "minimum_semantic_unit": "request/list_group",
        "factors": list(artifact.get("factors") or artifact.get("personalization_factors") or []),
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
) -> dict[str, Any]:
    """Request-level rubric input — candidates + product facts.

    Each ``copy_artifact`` candidate becomes one rubric input row keyed by
    candidate_index.
    """
    s = _scenario_dict(scenario)
    copy = copy_artifact or {}
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
            }
        )
    return {
        "schema_version": "request_personalized_copy_rubric_payload_v1",
        "scenario_id": s.get("scenario_id"),
        "request_id": s.get("request_id"),
        "minimum_semantic_unit": "request/list_group",
        "products": list(s.get("products") or []),
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
        )
    else:
        view = _scenario_dict(scenario)
    return {
        "session_id": session_id,
        "scenario": view,
        "artifacts": deps,
    }
