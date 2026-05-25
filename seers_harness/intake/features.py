"""Field parsing, compact profiles, and derived request features."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from seers_harness.intake.categories import canonical_category, normalize_text


REQUEST_ID_FIELDS = ("request_id", "mid", "logid")
USER_ID_FIELDS = ("user_id", "uid", "mid")

USER_PROFILE_FIELDS = {
    "age",
    "gender",
    "region_level",
    "city_level",
    "vip_level",
    "is_svip",
    "register_days",
    "fav_price_avg_30d",
    "purchase_price_avg_30d",
    "click_cnt_1d",
    "click_cnt_30d",
    "cart_cnt_1d",
    "cart_cnt_30d",
    "fav_cnt_1d",
    "fav_cnt_30d",
    "fav_item_cnt_30d",
    "fav_brand_cnt_30d",
    "order_cnt_30d",
    "order_cnt_90d",
    "coupon_use_cnt_30d",
}

USER_BEHAVIOR_FIELDS = {
    "prefer_cat3_topK",
    "prefer_brand_topK",
    "prefer_cat3_topk",
    "prefer_brand_topk",
    "seq_click_brand_48h",
    "seq_click_cat3_48h",
    "seq_search_brand_48h",
    "seq_search_cat3_48h",
    "click_cat3_id_list_topN",
    "click_brand_id_list_topN",
    "click_goods_id_list_topN",
    "collect_cat3_id_list_topN",
    "collect_brand_id_list_topN",
    "collect_goods_id_list_topN",
    "addcart_cat3_id_list_topN",
    "addcart_brand_id_list_topN",
    "addcart_goods_id_list_topN",
    "order_cat3_id_list_topN",
    "order_brand_id_list_topN",
    "order_goods_id_list_topN",
}

CONTEXT_FIELDS = {"day_of_week", "hour", "device_type"}
OBSERVED_FIELDS = {"is_clk_c", "is_addcart_c", "is_exp_order_c", "goods_seq"}
IDENTITY_FIELDS = {
    "request_id",
    "mid",
    "logid",
    "user_id",
    "uid",
    "item_id",
    "spu_id",
    "source_spu_id",
}

FREQ_AGG_FIELDS = {
    "click_goods_id_list_topN": 5,
    "addcart_goods_id_list_topN": 5,
    "collect_goods_id_list_topN": 5,
    "order_goods_id_list_topN": 5,
    "click_cat3_id_list_topN": 5,
    "click_brand_id_list_topN": 5,
    "collect_cat3_id_list_topN": 5,
    "collect_brand_id_list_topN": 5,
    "addcart_cat3_id_list_topN": 5,
    "addcart_brand_id_list_topN": 5,
    "order_cat3_id_list_topN": 5,
    "order_brand_id_list_topN": 5,
    "seq_click_cat3_48h": 5,
    "seq_click_brand_48h": 5,
    "seq_search_cat3_48h": 5,
    "seq_search_brand_48h": 5,
}
RANK_AGG_FIELDS = {
    "prefer_cat3_topK": 10,
    "prefer_brand_topK": 10,
    "prefer_cat3_topk": 10,
    "prefer_brand_topk": 10,
}

GENDER_MAP = {0: "未知", 1: "男", 2: "女", 3: "未知"}
CITY_LEVEL_MAP = {
    1: "一线城市",
    2: "二线城市",
    3: "三线城市",
    4: "四线城市",
    5: "五线城市",
    6: "下沉城市",
}
VIP_LEVEL_ALLOWED = {"金卡会员", "银卡会员", "白金卡会员"}
BRAND_LEVEL_ALLOWED = {"国际A", "国际B", "国际C", "国内A", "国内B", "国内C", "国内D"}
DEVICE_TYPE_MAP = {"shop_android": "Android", "shop_iphone": "iPhone"}

NUMERIC_CLIP = {
    "ctr_7d": 1.0,
    "cvr_7d": 1.0,
    "item_satisfy": 1.0,
    "return_rate_30d": 1.0,
    "discount_rate": 1.0,
    "click_cnt_1d": 50000.0,
    "register_days": 18000.0,
}


def parse_field(field_name: str, value: str) -> Any:
    if value == "":
        return None
    low = field_name.lower()
    if "topn" in low or "topk" in low or low.endswith("_list") or low.startswith("seq_"):
        return [parse_scalar(part) for part in value.split(",") if part.strip()]
    return parse_scalar(value)


def parse_scalar(value: str) -> Any:
    raw = value.strip()
    if raw == "":
        return None
    if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def resolve_first(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            return str(value)
    return ""


def user_state_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": resolve_first(row, USER_ID_FIELDS),
        "profile": compact_profile({k: humanize(k, row[k]) for k in USER_PROFILE_FIELDS if present(row.get(k))}),
        "behavior": compact_profile({k: humanize(k, row[k]) for k in USER_BEHAVIOR_FIELDS if present(row.get(k))}),
        "context": {k: humanize(k, row[k]) for k in CONTEXT_FIELDS if present(row.get(k))},
    }


def product_from_row(row: dict[str, Any], *, category: str, line_no: int) -> dict[str, Any]:
    product_id = resolve_first(row, ("item_id", "spu_id", "source_spu_id")) or f"row-{line_no}"
    group_key = str(row.get("item_cat3_name") or category).strip()
    attributes = {
        key: humanize(key, value)
        for key, value in row.items()
        if present(value)
        and key not in IDENTITY_FIELDS
        and key not in USER_PROFILE_FIELDS
        and key not in USER_BEHAVIOR_FIELDS
        and key not in CONTEXT_FIELDS
        and key not in OBSERVED_FIELDS
    }
    attributes["item_cat3_name"] = row.get("item_cat3_name") or group_key
    attributes["generation_category"] = category
    observed = {
        "is_clicked": to_bool(row.get("is_clk_c")),
        "is_addcart": to_bool(row.get("is_addcart_c")),
        "is_order": to_bool(row.get("is_exp_order_c")),
        "goods_seq": to_int(row.get("goods_seq"), default=line_no),
    }
    return {
        "product_id": product_id,
        "source_ids": {
            key: row[key]
            for key in ("item_id", "spu_id", "source_spu_id")
            if present(row.get(key))
        },
        "group_key": group_key,
        "category": category,
        "canonical_product_name": canonical_product_name(row.get("item_name")),
        "attributes": attributes,
        "observed": observed,
    }


def stable_product_key(row: dict[str, Any]) -> str:
    source_key = resolve_first(row, ("source_spu_id", "spu_id", "item_id"))
    if source_key:
        return f"id:{source_key}"
    return f"name:{canonical_product_name(row.get('item_name'))}"


def canonical_product_name(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"^[【\[\(（][^】\]\)）]{1,20}[】\]\)）]", "", text)
    text = re.sub(r"\b20\d{2}\s*(年款|新款|款)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+(\.\d+)?\s*(片|粒|颗|ml|mL|g|kg|支|瓶|盒|包|袋|只|件|套)\b", "", text)
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"(新款|升级款|正品|官方|旗舰店|专柜同款|蓝帽)", "", text)
    return re.sub(r"\s+", "", text).strip(" -_/，,。")


def compact_profile(profile: dict[str, Any]) -> dict[str, Any]:
    compacted = dict(profile)
    for key, top_k in FREQ_AGG_FIELDS.items():
        if isinstance(compacted.get(key), list):
            compacted[key] = compress_list_to_freq(compacted[key], top_k)
    for key, top_k in RANK_AGG_FIELDS.items():
        if isinstance(compacted.get(key), list):
            compacted[key] = compress_list_to_rank(compacted[key], top_k)
    return compacted


def compress_list_to_freq(items: list[Any], top_k: int) -> str:
    tokens = [token for token in (clean_seq_token(item) for item in items) if token]
    if not tokens:
        return ""
    return ", ".join(f"{item}({count})" for item, count in Counter(tokens).most_common(top_k))


def compress_list_to_rank(items: list[Any], top_k: int) -> str:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        token = clean_seq_token(item)
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= top_k:
            break
    return ", ".join(f"{name}(rank={idx})" for idx, name in enumerate(deduped, start=1))


def build_derived_features(
    *,
    user_row: dict[str, Any],
    product_row: dict[str, Any],
    category: str,
    brand_level_index: dict[str, str] | None = None,
    cat3_cat1_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    cat3_cat1 = cat3_cat1_index or {}
    prefer_cat3 = list_values(user_row.get("prefer_cat3_topK") or user_row.get("prefer_cat3_topk"))
    prefer_brand = list_values(user_row.get("prefer_brand_topK") or user_row.get("prefer_brand_topk"))
    item_cat3 = str(product_row.get("item_cat3_name") or "")
    item_cat1 = str(product_row.get("item_cat1_name") or "")
    item_brand = str(product_row.get("item_brand_name") or "")
    price_ratio = price_vs_user_baseline(product_row, user_row)
    typical_level = typical_brand_level(
        prefer_brand=prefer_brand,
        brand_level_index=brand_level_index or {},
        fallback_brand=item_brand,
        fallback_level=str(product_row.get("brand_level") or ""),
    )
    review_cnt = to_float(product_row.get("review_cnt"))
    ctr_7d = to_float(product_row.get("ctr_7d"))
    seq_search_cat3 = list_values(user_row.get("seq_search_cat3_48h"))
    review_band = band_review(review_cnt)
    return {
        "price_vs_user_baseline_ratio": None if price_ratio is None else round(price_ratio, 4),
        "price_vs_user_baseline_bucket": bucket_price_ratio(price_ratio),
        "cat3_alignment": cat3_alignment(
            category=category,
            item_cat3=item_cat3,
            item_cat1=item_cat1,
            prefer_cat3=prefer_cat3,
            click_cat3=list_values(user_row.get("click_cat3_id_list_topN")),
            seq_search_cat3=seq_search_cat3,
            seq_click_cat3=list_values(user_row.get("seq_click_cat3_48h")),
            collect_cat3=list_values(user_row.get("collect_cat3_id_list_topN")),
            cat3_cat1=cat3_cat1,
        ),
        "brand_alignment": brand_alignment(
            item_brand=item_brand,
            prefer_brand=prefer_brand,
            click_brand=list_values(user_row.get("click_brand_id_list_topN")),
            order_brand=list_values(user_row.get("order_brand_id_list_topN")),
        ),
        "user_typical_brand_level": typical_level,
        "brand_level_vs_user_history": compare_brand_level(typical_level, product_row.get("brand_level")),
        "review_band": review_band,
        "ctr_band": band_ctr(min(ctr_7d, 1.0) if ctr_7d is not None else None),
        "is_cold_start_combo": bool(to_float(product_row.get("is_new")) == 1.0 and review_band in {"cold", "low"}),
        "recent_search_intent_distance": search_distance(
            category=category,
            item_cat3=item_cat3,
            item_cat1=item_cat1,
            seq_search_cat3=seq_search_cat3,
            cat3_cat1=cat3_cat1,
        ),
        "user_activity_level": activity_level(to_float(user_row.get("active_days_30d"))),
    }


def cat3_alignment(
    *,
    category: str,
    item_cat3: str,
    item_cat1: str,
    prefer_cat3: list[str],
    click_cat3: list[str],
    seq_search_cat3: list[str],
    seq_click_cat3: list[str],
    collect_cat3: list[str],
    cat3_cat1: dict[str, str],
) -> str:
    if category in canonical_categories(prefer_cat3) or item_cat3 in prefer_cat3:
        return "aligned"
    if category in canonical_categories(seq_search_cat3) or item_cat3 in seq_search_cat3:
        return "recent_searched"
    touched = click_cat3 + seq_click_cat3 + collect_cat3
    if category in canonical_categories(touched) or item_cat3 in touched:
        return "recent_touched"
    if item_cat1 and any(cat3_cat1.get(other) == item_cat1 for other in prefer_cat3 + touched):
        return "adjacent"
    return "mismatch"


def brand_alignment(*, item_brand: str, prefer_brand: list[str], click_brand: list[str], order_brand: list[str]) -> str:
    if not item_brand:
        return "unknown"
    if item_brand in prefer_brand:
        return "aligned"
    if item_brand in click_brand or item_brand in order_brand:
        return "recent_touched"
    return "mismatch"


def search_distance(
    *,
    category: str,
    item_cat3: str,
    item_cat1: str,
    seq_search_cat3: list[str],
    cat3_cat1: dict[str, str],
) -> str:
    if not seq_search_cat3:
        return "no_recent_search"
    if category in canonical_categories(seq_search_cat3) or item_cat3 in seq_search_cat3:
        return "same"
    if item_cat1 and any(cat3_cat1.get(other) == item_cat1 for other in seq_search_cat3):
        return "adjacent"
    return "mismatch"


def canonical_categories(values: list[str]) -> set[str]:
    return {category for value in values if (category := canonical_category(value))}


def price_vs_user_baseline(product_row: dict[str, Any], user_row: dict[str, Any]) -> float | None:
    price = to_float(product_row.get("item_arriv_price"))
    baseline = to_float(user_row.get("purchase_price_avg_30d"))
    if price is None or baseline is None or baseline <= 0:
        return None
    return (price - baseline) / baseline


def bucket_price_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "无基线"
    if ratio < -0.5:
        return "远低于"
    if ratio < -0.15:
        return "略低于"
    if ratio < 0.15:
        return "持平"
    if ratio < 0.5:
        return "略高于"
    if ratio < 2.0:
        return "远高于"
    return "远超出"


def typical_brand_level(
    *,
    prefer_brand: list[str],
    brand_level_index: dict[str, str],
    fallback_brand: str,
    fallback_level: str,
) -> str | None:
    levels = Counter(brand_level_index[brand] for brand in prefer_brand if brand in brand_level_index)
    if levels:
        return levels.most_common(1)[0][0]
    if fallback_brand and fallback_brand in prefer_brand and fallback_level in BRAND_LEVEL_ALLOWED:
        return fallback_level
    return None


def compare_brand_level(typical: str | None, current: Any) -> str:
    current_text = str(current or "").strip()
    if not typical or current_text not in BRAND_LEVEL_ALLOWED:
        return "unknown"
    rank = {"国际A": 7, "国际B": 6, "国际C": 5, "国内A": 4, "国内B": 3, "国内C": 2, "国内D": 1}
    if rank[current_text] > rank[typical]:
        return "upgrade"
    if rank[current_text] < rank[typical]:
        return "downgrade"
    return "same"


def band_review(value: float | None) -> str:
    if value is None or value < 51:
        return "cold"
    if value < 415:
        return "low"
    if value < 1980:
        return "normal"
    if value < 12100:
        return "popular"
    return "hot"


def band_ctr(value: float | None) -> str:
    if value is None or value < 0.069:
        return "low"
    if value < 0.179:
        return "mid"
    if value < 0.302:
        return "high"
    return "very_high"


def activity_level(value: float | None) -> str:
    if value is None:
        return "中"
    if value < 400:
        return "低"
    if value < 1260:
        return "中"
    if value < 1626:
        return "高"
    return "极高"


def list_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [token for token in (clean_seq_token(item) for item in value) if token]
    if isinstance(value, str):
        out = []
        for chunk in value.split(","):
            token = clean_seq_token(chunk.split("(")[0])
            if token:
                out.append(token)
        return out
    return []


def clean_seq_token(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or normalize_text(text).lower() in {"0", "0.0", "none", "null", "nan"}:
        return None
    return text


def humanize(key: str, value: Any) -> Any:
    if key == "gender" and isinstance(value, (int, float)):
        return GENDER_MAP.get(int(value), "未知")
    if key == "city_level" and isinstance(value, (int, float)):
        return CITY_LEVEL_MAP.get(int(value), "未知")
    if key == "vip_level":
        text = str(value).strip()
        return text if text in VIP_LEVEL_ALLOWED else "未知"
    if key == "brand_level":
        text = str(value).strip()
        return text if text in BRAND_LEVEL_ALLOWED else "未知"
    if key == "device_type":
        text = str(value).strip()
        return DEVICE_TYPE_MAP.get(text, "未知")
    cap = NUMERIC_CLIP.get(key)
    if cap is not None:
        number = to_float(value)
        if number is not None:
            clipped = min(number, cap)
            return int(clipped) if isinstance(value, int) else clipped
    return value


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value != ""
    if isinstance(value, list):
        return bool(value)
    return True


def to_bool(value: Any) -> bool:
    try:
        return float(value or 0) == 1.0
    except (TypeError, ValueError):
        return str(value).strip() == "1"


def to_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except (TypeError, ValueError):
        return default


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
