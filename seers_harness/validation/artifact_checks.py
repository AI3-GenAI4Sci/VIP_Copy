"""Deterministic cross-artifact checks after model final-submit."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from seers_harness.core.errors import BusinessOutputError


def validate_artifact_against_payload(
    *,
    node_id: str,
    payload: dict[str, Any],
    artifact: BaseModel,
) -> None:
    """Raise ``BusinessOutputError`` when a submitted artifact is unusable.

    These checks replace model-driven intermediate tool turns for
    constraints that are fully knowable by the harness: duplicate ids,
    upstream references, target product coverage, and rubric completeness.
    """
    data = artifact.model_dump(mode="json")
    if node_id == "personalized_user_mining":
        _validate_user_artifact(payload, data)
    elif node_id == "personalized_copy_generation":
        _validate_copy_artifact(payload, data)
    elif node_id == "personalized_copy_rubric":
        _validate_rubric_artifact(payload, data)


def _validate_user_artifact(payload: dict[str, Any], data: dict[str, Any]) -> None:
    factors = _list_of_dicts(data.get("user_factors"))
    if not factors and _has_user_signal(payload):
        raise BusinessOutputError(
            "personalized_user_mining produced zero user_factors for a request with user signals"
        )
    _reject_duplicate_ids(factors, "user_factor_id")
    for factor in factors:
        factor_id = str(factor.get("user_factor_id") or "")
        if not str(factor.get("need_or_pain") or "").strip():
            raise BusinessOutputError(
                f"user_factor_id {factor_id!r} has empty need_or_pain"
            )


def _validate_copy_artifact(payload: dict[str, Any], data: dict[str, Any]) -> None:
    candidates = _list_of_dicts(data.get("candidates"))
    _reject_duplicate_ids(candidates, "candidate_id")
    target_product_count = int(payload.get("target_product_count") or 0)
    if target_product_count > 0 and not candidates:
        raise BusinessOutputError(
            "personalized_copy_generation produced zero candidates for a non-empty request"
        )

    factor_ids = {
        str(factor.get("user_factor_id"))
        for factor in _list_of_dicts(payload.get("user_factors"))
        if factor.get("user_factor_id")
    }
    product_ids = {
        str(product.get("product_id"))
        for product in _list_of_dicts(payload.get("products"))
        if product.get("product_id")
    }
    candidate_product_ids: set[str] = set()
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "")
        factor_id = str(candidate.get("source_user_factor_id") or "")
        product_id = str(candidate.get("product_id") or "")
        candidate_product_ids.add(product_id)
        if factor_ids and factor_id not in factor_ids:
            raise BusinessOutputError(
                f"candidate_id {candidate_id!r} source_user_factor_id {factor_id!r} "
                "is not present in upstream user_factors"
            )
        if product_ids and product_id not in product_ids:
            raise BusinessOutputError(
                f"candidate_id {candidate_id!r} product_id {product_id!r} "
                "is not present in target products"
            )
        for field in ("text", "product_binding", "fact_binding"):
            if not str(candidate.get(field) or "").strip():
                raise BusinessOutputError(
                    f"candidate_id {candidate_id!r} has empty {field}"
                )

    missing_products = sorted(product_ids - candidate_product_ids)
    if missing_products:
        raise BusinessOutputError(
            "missing candidates for product_id: " + ", ".join(missing_products)
        )


def _validate_rubric_artifact(payload: dict[str, Any], data: dict[str, Any]) -> None:
    judgments = _list_of_dicts(data.get("judgments"))
    _reject_duplicate_ids(judgments, "candidate_id")

    candidate_ids = {
        str(candidate.get("candidate_id"))
        for candidate in _list_of_dicts(payload.get("candidates"))
        if candidate.get("candidate_id")
    }
    judgment_ids = {
        str(judgment.get("candidate_id"))
        for judgment in judgments
        if judgment.get("candidate_id")
    }
    missing = sorted(candidate_ids - judgment_ids)
    if missing:
        raise BusinessOutputError(
            "missing judgments for candidate_id: " + ", ".join(missing)
        )
    extra = sorted(judgment_ids - candidate_ids)
    if candidate_ids and extra:
        raise BusinessOutputError(
            "judgments reference unknown candidate_id: " + ", ".join(extra)
        )


def _reject_duplicate_ids(rows: list[dict[str, Any]], field: str) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for row in rows:
        value = str(row.get(field) or "")
        if not value:
            raise BusinessOutputError(f"empty {field}")
        if value in seen:
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        raise BusinessOutputError(
            f"duplicate {field}: " + ", ".join(sorted(set(duplicates)))
        )


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _has_user_signal(payload: dict[str, Any]) -> bool:
    signal_roots = (
        payload.get("user_state_signals"),
        payload.get("user_state_summary"),
    )
    return any(_has_meaningful_value(root) for root in signal_roots)


def _has_meaningful_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_meaningful_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_meaningful_value(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return value is not None
