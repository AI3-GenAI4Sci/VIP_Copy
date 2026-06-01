"""Raw intake field groups and value maps."""

from __future__ import annotations

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
ITEM_ATTRIBUTE_FIELDS = {
    "item_name",
    "item_spu_title",
    "item_cat1_name",
    "item_cat3_name",
    "item_brand_name",
    "brand_level",
    "item_gender_tag",
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
    "gender_match_item_gender_tag",
    "is_in_user_prefer_brand",
    "is_in_user_prefer_cat3",
    "clicked_count_same_brand_30d",
    "clicked_count_same_cat3_30d",
    "clicked_count_same_spu_30d",
    "carted_count_same_brand_30d",
    "carted_count_same_cat3_30d",
    "ordered_count_same_brand_90d",
    "ordered_count_same_cat3_90d",
    "p_ctr",
    "p_car",
    "p_cvr",
}
DROP_PRODUCT_ATTRIBUTE_FIELDS = {
    "active_days_30d",
    "cat1_id",
    "city_id",
    "item_cat3",
    "item_brand",
    "is_spu_order",
    "is_spu_order_clk",
    "is_spu_order_addcart",
    "is_spu_order_c",
    "is_spu_order_c_clk",
    "is_spu_order_c_addcart",
    "is_spu_order_c_expose",
    "is_spu_order_expose",
    "is_exp_order_c_expose",
    "is_otd_ad",
    "is_ctx_item",
    "timestamp",
    "click_timestamp_list_topN",
    "addcart_timestamp_list_topN",
    "collect_timestamp_list_topN",
    "order_timestamp_list_topN",
    "click_timestamp_diff_seconds",
    "addcart_timestamp_diff_seconds",
    "collect_timestamp_diff_seconds",
    "order_timestamp_diff_seconds",
    "title_attr_size",
    "score",
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


