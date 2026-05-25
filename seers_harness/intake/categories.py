"""Production category scope for request preprocessing."""

from __future__ import annotations

import re
from typing import Any


TARGET_CATEGORIES = ("防晒霜/乳", "牙膏/牙粉", "维生素", "香水", "护肩")

_SUNSCREEN = {"防晒霜/乳", "防晒霜", "防晒乳", "防晒喷雾", "防晒啫喱"}
_TOOTHPASTE = {"牙膏/牙粉", "牙膏", "牙粉"}
_VITAMIN = {"维生素", "维生素C", "复合维生素", "多种维生素"}
_PERFUME = {"香水", "淡香水", "浓香水", "女士香水", "男士香水", "中性香水"}
_PERFUME_NON_PRODUCT = {"香水瓶", "香水工具", "香水瓶/香水工具"}


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", "", text)
    return text.strip()


def canonical_category(value: Any) -> str | None:
    """Return the five-category bucket for a raw third-level category.

    The matcher is deliberately alias-based. It handles known business aliases
    and slash-composite shoulder categories, while avoiding broad substring
    matches such as "维生素饮料" or "香水瓶/香水工具".
    """

    text = normalize_text(value)
    if not text:
        return None
    if text in _SUNSCREEN:
        return "防晒霜/乳"
    if text in _TOOTHPASTE:
        return "牙膏/牙粉"
    if text in _VITAMIN:
        return "维生素"
    if text in _PERFUME:
        return "香水"
    if text in _PERFUME_NON_PRODUCT:
        return None
    parts = {part for part in re.split(r"[/／、,，\s]+", text) if part}
    if "护肩" in parts or text == "护肩":
        return "护肩"
    return None


def category_candidates(row: dict[str, Any]) -> list[str]:
    keys = ("item_cat3_name", "cat3_name", "category_bucket", "category", "item_cat3")
    return [str(row[key]).strip() for key in keys if row.get(key) not in (None, "")]


def row_category(row: dict[str, Any]) -> str | None:
    for candidate in category_candidates(row):
        category = canonical_category(candidate)
        if category:
            return category
    return None
