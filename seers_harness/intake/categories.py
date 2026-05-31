"""Production category scope for request preprocessing."""

from __future__ import annotations

import re
from typing import Any


TARGET_CATEGORIES = ("防晒霜/乳", "牙膏/牙粉", "维生素", "香水", "护肩")

_CATEGORY_ALIASES: dict[str, set[str]] = {
    "防晒霜/乳": {
        "防晒",
        "防晒霜/乳",
        "防晒霜",
        "防晒乳",
        "防晒喷雾",
        "防晒啫喱",
        "防晒隔离",
        "隔离防晒",
        "防晒露",
        "防晒膏",
        "防晒凝胶",
    },
    "牙膏/牙粉": {
        "牙膏/牙粉",
        "牙膏",
        "牙粉",
        "儿童牙膏",
        "美白牙膏",
        "抗敏牙膏",
        "含氟牙膏",
    },
    "维生素": {
        "维生素",
        "维生素C",
        "复合维生素",
        "多种维生素",
        "综合维生素",
    },
    "香水": {
        "香水",
        "淡香水",
        "浓香水",
        "女士香水",
        "男士香水",
        "中性香水",
        "淡香精",
        "浓香精",
        "古龙水",
    },
    "护肩": {
        "护肩",
        "护肩带",
        "护肩套",
        "肩周护具",
    },
}

_CATEGORY_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "防晒霜/乳": (
        re.compile(r"^防晒(霜|乳|喷雾|啫喱|隔离|露|膏|凝胶)$"),
        re.compile(r"^隔离防晒$"),
    ),
    "牙膏/牙粉": (
        re.compile(r"^(儿童|婴幼儿|宝宝|美白|抗敏|脱敏|含氟|无氟|清新|草本|酵素|小苏打|益生菌)?牙膏$"),
        re.compile(r"^(美白|洁牙|固齿|草本)?牙粉$"),
    ),
    "维生素": (
        re.compile(r"^维生素([A-Z]|B族|B\d+|D\d+)?$", re.IGNORECASE),
        re.compile(r"^(复合|多种|综合)维生素$"),
    ),
    "香水": (
        re.compile(r"^(女士|男士|中性)?(香水|淡香水|浓香水|淡香精|浓香精|古龙水)$"),
    ),
    "护肩": (
        re.compile(r"^(护肩|护肩带|护肩套|肩周护具)$"),
    ),
}

_CATEGORY_NEGATIVES: dict[str, set[str]] = {
    "防晒霜/乳": {"防晒衣", "防晒帽", "防晒袖", "遮阳伞", "防晒口罩"},
    "牙膏/牙粉": {"牙刷", "牙线", "冲牙器", "漱口水", "牙贴"},
    "维生素": {"维生素饮料", "维生素水", "功能饮料"},
    "香水": {"香水瓶", "香水工具", "香水瓶/香水工具", "车载香水", "香薰", "扩香"},
    "护肩": {"护颈", "护腰", "护腕", "护膝", "护颈/护腰/护腕/护膝/身体矫姿"},
}


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
    if any(text in negatives for negatives in _CATEGORY_NEGATIVES.values()):
        return None
    for category in TARGET_CATEGORIES:
        if text in _CATEGORY_ALIASES[category]:
            return category
        if any(pattern.match(text) for pattern in _CATEGORY_PATTERNS[category]):
            return category
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
