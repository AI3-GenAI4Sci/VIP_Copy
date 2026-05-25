from __future__ import annotations

import csv
from pathlib import Path

from seers_harness.intake import TARGET_CATEGORIES, preprocess_request_from_csv


HEADER = [
    "request_id",
    "mid",
    "item_id",
    "spu_id",
    "source_spu_id",
    "goods_seq",
    "item_cat3_name",
    "item_cat1_name",
    "item_name",
    "item_brand_name",
    "brand_level",
    "item_arriv_price",
    "purchase_price_avg_30d",
    "prefer_cat3_topK",
    "prefer_brand_topK",
    "seq_search_cat3_48h",
    "seq_click_cat3_48h",
    "click_cat3_id_list_topN",
    "click_brand_id_list_topN",
    "order_brand_id_list_topN",
    "review_cnt",
    "ctr_7d",
    "is_new",
    "active_days_30d",
    "gender",
    "city_level",
    "vip_level",
    "device_type",
]


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER, delimiter="#")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in HEADER})


def base_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "request_id": "REQ-1",
        "mid": "USER-1",
        "item_id": "item-1",
        "spu_id": "spu-1",
        "source_spu_id": "source-1",
        "goods_seq": 1,
        "item_cat3_name": "防晒霜/乳",
        "item_cat1_name": "美妆护肤",
        "item_name": "兰蔻轻盈防晒乳",
        "item_brand_name": "兰蔻",
        "brand_level": "国际A",
        "item_arriv_price": 120,
        "purchase_price_avg_30d": 100,
        "prefer_cat3_topK": "防晒霜/乳,维生素",
        "prefer_brand_topK": "兰蔻,养生堂",
        "seq_search_cat3_48h": "防晒乳,面膜",
        "seq_click_cat3_48h": "防晒霜/乳",
        "click_cat3_id_list_topN": "防晒霜/乳",
        "click_brand_id_list_topN": "兰蔻",
        "order_brand_id_list_topN": "养生堂",
        "review_cnt": 600,
        "ctr_7d": 0.12,
        "is_new": 0,
        "active_days_30d": 900,
        "gender": 2,
        "city_level": 2,
        "vip_level": "金卡会员",
        "device_type": "shop_iphone",
    }
    row.update(overrides)
    return row


def test_preprocess_request_keeps_only_target_cat3_scope_with_precise_aliases(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    write_rows(
        csv_path,
        [
            base_row(item_id="p-sun", spu_id="spu-sun", source_spu_id="src-sun", item_cat3_name="防晒乳", item_name="兰蔻轻盈防晒乳", goods_seq=2),
            base_row(item_id="p-tooth", spu_id="spu-tooth", source_spu_id="src-tooth", item_cat3_name="牙膏", item_name="清新牙膏", goods_seq=3),
            base_row(item_id="p-vitamin", spu_id="spu-vitamin", source_spu_id="src-vitamin", item_cat3_name="维生素", item_name="天然维生素C160片 2026新款", item_brand_name="养生堂", goods_seq=4),
            base_row(item_id="p-shoulder", spu_id="spu-shoulder", source_spu_id="src-shoulder", item_cat3_name="护颈/护肩/护腰/护腕/护膝/身体矫姿", item_name="轻薄护肩披肩", goods_seq=5),
            base_row(item_id="p-perfume", spu_id="spu-perfume", source_spu_id="src-perfume", item_cat3_name="淡香水", item_name="清新淡香水", goods_seq=6),
            base_row(item_id="p-vitamin-drink", item_cat3_name="维生素饮料", item_name="维生素风味饮料", goods_seq=7),
            base_row(item_id="p-perfume-tool", item_cat3_name="香水瓶/香水工具", item_name="便携香水瓶", goods_seq=8),
            base_row(request_id="REQ-2", item_id="p-other-request", item_cat3_name="维生素", goods_seq=1),
        ],
    )

    scenario = preprocess_request_from_csv(csv_path, request_id="REQ-1")

    assert TARGET_CATEGORIES == ("防晒霜/乳", "牙膏/牙粉", "维生素", "香水", "护肩")
    assert scenario["request_id"] == "REQ-1"
    assert [product["product_id"] for product in scenario["products"]] == [
        "p-sun",
        "p-tooth",
        "p-vitamin",
        "p-shoulder",
        "p-perfume",
    ]
    assert [product["category"] for product in scenario["products"]] == [
        "防晒霜/乳",
        "牙膏/牙粉",
        "维生素",
        "护肩",
        "香水",
    ]


def test_preprocess_request_preserves_original_fields_and_computes_nonredundant_features(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    write_rows(
        csv_path,
        [
            base_row(item_id="p-1", source_spu_id="stable-1", item_cat3_name="维生素", item_name="【蓝帽】天然维生素C160片 2026新款", goods_seq=2),
            base_row(item_id="p-1-dup", source_spu_id="stable-1", item_cat3_name="维生素", item_name="天然维生素C 160片", goods_seq=9),
        ],
    )

    scenario = preprocess_request_from_csv(csv_path, request_id="REQ-1")

    assert len(scenario["products"]) == 1
    product = scenario["products"][0]
    assert product["product_id"] == "p-1"
    assert product["source_ids"] == {
        "item_id": "p-1",
        "spu_id": "spu-1",
        "source_spu_id": "stable-1",
    }
    assert product["canonical_product_name"] == "天然维生素C片"
    assert product["attributes"]["item_name"] == "【蓝帽】天然维生素C160片 2026新款"
    assert product["attributes"]["item_arriv_price"] == 120
    assert scenario["user_state"]["profile"]["gender"] == "女"
    assert scenario["user_state"]["behavior"]["prefer_cat3_topK"] == "防晒霜/乳(rank=1), 维生素(rank=2)"

    features = scenario["derived_features_by_product"]["p-1"]
    assert set(features) == {
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
    }
    assert features["cat3_alignment"] == "aligned"
    assert features["brand_alignment"] == "aligned"
