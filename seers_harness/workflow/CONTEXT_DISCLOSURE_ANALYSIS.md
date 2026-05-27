# Context Disclosure Analysis — Workflow Payload Field Boundary

**目的**: 在 G2 修复 F-08-C 前,先确定 `copy_payload_for` / `rubric_payload_for` 应该披露哪些 user_state 字段。F-08-C 观察到 copy_generation `prompt_cache_miss=120 tokens` 是过窄(信号被剥光),但 blanket whitelist 会把 cache_miss 推到 8000+(prompt prefix 不再稳定,F-08-03 已示 reasoning_tokens 在 cache_miss 高时飙升 8x)。

本分析把 context 披露作为信息论问题处理:在 cache prefix 稳定性约束下,最大化 per-request 信号密度。

> **Sign-off scope**: 本文件 sign-off 的是字段集合 + 边界,不签具体代码改动(那是 Task 2 实施时的 mechanical 翻译)。

---

## 1. Cache-prefix-stable vs per-request fields

枚举 sample request (`stage1/-6834635816105165003`) 的全部 `user_state.*` + `user_state.context.*` 字段,逐字段判断"是否能进 prompt cache prefix"。

**"Cache-prefix-stable" 的工程含义**:DeepSeek prompt cache 是 prefix-based。一段 prompt 若其前 N 个 token 在跨请求间字节级相同,DeepSeek 即可命中前 N 个 token 的 cache。SKILL prose(`message[0].content`)是大段稳定 prefix。`message[1].content` 是 user payload —— 若每个 request 的 payload 头部字段值差异极大,prefix 几乎无法跨请求复用。但如果**payload 内部按"稳定字段 → 高变化字段"排序**,稳定字段部分还能 hit cache。

**关键洞察**: F-08-03 的 cache_miss=120 解释为 — copy_generation node 的 payload 几乎全是 factor 列表(高变化),user_state 完全剥离 → cache prefix 短到几乎只剩 SKILL prose。这对 *cache prefix 稳定性* 是好事(prefix 极短但 100% 复用),但对 *信号密度* 是灾难。

### 1.1 `user_state.profile` 字段

| 字段路径 | Value 例子 | 稳定性 | 用作 prefix? | 备注 |
|---|---|---|---|---|
| `profile.user_id` | `"294379371"` | 跨用户唯一 | ❌ | 唯一识别,无信号价值 |
| `profile.gender` | `"女"` | 二元(女/男/未知) | ✅ 可放 prefix | 类别少 |
| `profile.age` | `31` | 整数,跨用户分布广 | ❌ | 高熵 |
| `profile.city_level` | `"二线城市"` | 4 个类别 | ✅ 可放 prefix | 类别少 |
| `profile.region_level` | `"云南省"` | 30+ 类别 | 中 | mid 熵 |
| `profile.vip_level` | `"金卡会员"` | 4-5 类别 | ✅ 可放 prefix | 类别少 |
| `profile.is_svip` | `1` | 二元 | ✅ 可放 prefix | |
| `profile.register_days` | `2936` | 整数,跨用户分布广 | ❌ | 高熵 |
| `profile.click_cnt_30d` | `77` | 整数 | ❌ | 高熵 |
| `profile.order_cnt_30d` | `3` | 整数 | ❌ | 高熵 |
| `profile.order_cnt_90d` | `15` | 整数 | ❌ | 高熵 |
| `profile.coupon_use_cnt_30d` | `0` | 小整数 | 中 | 低熵但有信号 |
| `profile.cart_cnt_30d` | `5` | 小整数 | ❌ | 高熵 |
| `profile.purchase_price_avg_30d` | `42.333332` | 浮点 | ❌ | 高熵 |
| `profile.fav_price_avg_30d` | `0.0` | 浮点 | ❌ | 高熵 |
| `profile.fav_*` 其余 | (各种 cnt) | 整数 | ❌ | 高熵 |

### 1.2 `user_state.behavior` 字段

| 字段路径 | Value 长度示例 | 稳定性 | 备注 |
|---|---|---|---|
| `behavior.click_brand_id_list_topN` | ~80 chars | ❌ | 跨用户字面值完全不同 |
| `behavior.click_goods_id_list_topN` | ~200 chars | ❌ | 完全个人化 |
| `behavior.click_cat3_id_list_topN` | ~80 chars | ❌ | 跨用户不同 |
| `behavior.seq_click_brand_48h` | ~40 chars | ❌ | 48h 时间窗,每次都不同 |
| `behavior.seq_click_cat3_48h` | ~50 chars | ❌ | 同上 |
| `behavior.order_goods_id_list_topN` | ~300 chars | ❌ | 完全个人化 |
| `behavior.order_brand_id_list_topN` | ~80 chars | ❌ | 同上 |
| `behavior.order_cat3_id_list_topN` | ~60 chars | ❌ | 同上 |
| `behavior.prefer_cat3_topK` | ~150 chars | ❌ | 同上 |
| `behavior.prefer_brand_topK` | ~80 chars | ❌ | 同上 |
| `behavior.collect_goods_id_list_topN` | ~250 chars | ❌ | 同上 |
| `behavior.collect_brand_id_list_topN` | ~60 chars | ❌ | 同上 |
| `behavior.collect_cat3_id_list_topN` | ~60 chars | ❌ | 同上 |
| `behavior.addcart_goods_id_list_topN` | ~250 chars | ❌ | 同上 |
| `behavior.addcart_brand_id_list_topN` | ~60 chars | ❌ | 同上 |
| `behavior.addcart_cat3_id_list_topN` | ~60 chars | ❌ | 同上 |

`behavior.*` 全部是"完全 per-request"。它们是信号金矿,但不可能进 prompt cache prefix。

### 1.3 `user_state.context` 字段

| 字段路径 | Value 例子 | 稳定性 | 备注 |
|---|---|---|---|
| `context.device_type` | `"iPhone"` / `"Android"` | 二元 | ✅ 可放 prefix |
| `context.hour` | `9` | 24 类别 | 中 |
| `context.day_of_week` | `3` | 7 类别 | ✅ 但 F-08-A finding:本 sampler 11/11 全是 3,零方差,不可用作差异化轴 |

### 1.4 `target_product` 字段

| 字段路径 | 稳定性 | 备注 |
|---|---|---|
| `products[].canonical_product_name` | ❌ | 完全 per-request |
| `products[].category` / `group_key` | 中 | 几十类别 |
| `products[].attributes.p_ctr` / `p_car` | ❌ | 浮点高熵 |
| `products[].attributes.ctr_7d` 等 | ❌ | 浮点高熵 |
| `derived_features_by_product[].price_vs_user_baseline_ratio` | ❌ | 浮点 |
| `derived_features_by_product[].brand_recent_touched` | ✅ 二元 | 高信号低熵 |
| `derived_features_by_product[].is_new` | ✅ 二元 | 同上 |
| `derived_features_by_product[].ctr_band` | ✅ 类别(high/mid/low) | 同上 |

---

## 2. 信息密度评估

把 §1 候选字段映射到 F-08-A 维度,评估"该字段提供 SKILL 哪个 hook 角度"。

> **F-08-A 维度参考**(只引用维度名,**不引用字面 angle 名** — angle 名是用户口头举例,非 SKILL prose 词汇):
> - D1 身份与生命阶段
> - D2 经济姿态
> - D3 品牌关系
> - D4 时间与地域上下文
> - D5 美学身份
> - D6 功能 / 健康 / 家庭场景
> - D7 行为漏斗姿态

| 字段 | 跨用户熵 | F-08-A 维度命中 | SKILL hook usability | byte cost / req | 决策导向 |
|---|---|---|---|---|---|
| `profile.gender` | 低(二元)| D1 | 中 — gender 仅决定品类倾向,disposition 推断要 + behavior | ~6 | 含 |
| `profile.age` | 高 | D1 | 高 — 30+ vs 40+ vs 50+ 大幅改 disposition | ~3 | 含 |
| `profile.city_level` | 低(4 类)| D4 | 高 — 一线/二线/下沉 disposition 差异显著 | ~10 | 含 |
| `profile.region_level` | 中(30+)| D4 | 低 — 仅省名,无独立 disposition | ~9 | 弃(信号被 city_level cover) |
| `profile.vip_level` + `is_svip` | 低(4 类 + 二元)| D1, D2 | 高 — 老用户/SVIP 是 D1 强信号 | ~16 | 含 |
| `profile.register_days` | 高 | D1 | 高 — 80 天新用户 vs 5000 天老用户 disposition 极差 | ~5 | 含 |
| `profile.click_cnt_30d` | 高 | D7 | 高 — 信息饕餮型 vs 轻浏览型,F-08-A D7 维度 | ~4 | 含 |
| `profile.order_cnt_30d` + `order_cnt_90d` | 高 | D7 | 高 — 漏斗转化率 | ~6 | 含 |
| `profile.purchase_price_avg_30d` | 高 | D2 | 高 — F-08-A D2 维度最丰富(ASP 跨度 8x)| ~10 | 含 |
| `profile.fav_price_avg_30d` | 高 | D2 | 高 — fav vs purchase 比值 = aspiration 信号 | ~6 | 含 |
| `profile.coupon_use_cnt_30d` | 中 | D2 | 中 — 优惠券密度是价格敏感信号 | ~3 | 含 |
| `profile.cart_cnt_30d` | 高 | D7 | 中 — cart vs order 比 = 犹豫层信号 | ~4 | 含 |
| `profile.fav_brand_cnt_30d` 等 fav_* | 高 | D3 | 中 — fav 数量给品牌关系密度 | ~10 | 含 |
| `behavior.prefer_cat3_topK` | 高 | D1, D6 | 极高 — 头部 cat3 暗示生命阶段(母婴/职场/学生)| ~150 | 含 |
| `behavior.prefer_brand_topK` | 高 | D3 | 极高 — 品牌阶梯 + 死忠 vs 多元 | ~80 | 含 |
| `behavior.seq_click_cat3_48h` | 高 | D4(临场)| 高 — 当下浏览意图 | ~50 | 含(短) |
| `behavior.seq_click_brand_48h` | 高 | D4 | 中 — 短 burst | ~40 | 含 |
| `behavior.addcart_cat3_id_list_topN` | 高 | D7 | 高 — 犹豫层 / 即将转化信号 | ~60 | 含 |
| `behavior.click_brand_id_list_topN` | 高 | D3 | 中 — 与 prefer 重合度高 | ~80 | 含 |
| `behavior.collect_brand_id_list_topN` | 高 | D3 | 中 — 与 prefer 互补(F-08-C 强调) | ~60 | 含 |
| `behavior.order_*` 三条 | 高 | D1, D2, D3 | 极高 — 已购真信号 | ~440 | 含(三条) |
| `behavior.collect_goods_id_list_topN` | 高 | D5, D6 | 中 — 美学/功能 hook | ~250 | 含 |
| `behavior.click_goods_id_list_topN` | 高 | D5 | 中 — 当下兴趣 | ~200 | 弃(与 prefer_cat3 + seq_click 重合) |
| `behavior.addcart_goods_id_list_topN` | 高 | D7 | 高 — 加购具体商品 = 强信号 | ~250 | 含 |
| `behavior.addcart_brand_id_list_topN` | 高 | D3, D7 | 高 — F-08-C 强调的"犹豫层"锚 | ~60 | 含 |
| `behavior.collect_cat3_id_list_topN` | 高 | D5, D6 | 中 — 与 prefer_cat3 重合 | ~60 | 弃 |
| `behavior.click_cat3_id_list_topN` | 高 | D7 | 中 — 与 prefer_cat3 重合 | ~80 | 弃 |
| `context.device_type` | 低 | D4 | 中 — 设备隐含购买力 | ~10 | 含 |
| `context.hour` | 中 | D4 | 中 — 时段场景 | ~3 | 含 |
| `context.day_of_week` | 极低(本批 11/11 = 3) | D4 | 极低 — 零方差不可用 | ~3 | 弃 |
| `products[].canonical_product_name` | 高 | (product anchor)| 必需 — copy 必须知道是什么产品 | ~30 | 含 |
| `products[].category` / `group_key` | 中 | D5, D6 | 高 — 类目决定 anchor type | ~15 | 含 |
| `products[].attributes.p_ctr` 等 | 高 | (社会证明)| 高 — 高评 / 高转化是 social-proof anchor | ~30 | 含 |
| `derived_features_by_product[].price_vs_user_baseline_ratio` | 高 | D2 | 极高 — 价格差跨度直接告诉 disposition | ~6 | 含 |
| `derived_features_by_product[].brand_recent_touched` | 低 | D3 | 高 — 品牌触达暗示 anchor | ~6 | 含 |
| `derived_features_by_product[].ctr_band` | 低(3 类) | (社会证明)| 高 | ~6 | 含 |
| `derived_features_by_product[].is_new` | 低 | (新颖性 anchor)| 高 | ~6 | 含 |

---

## 3. 最佳披露边界提案

### 3.1 `copy_payload_for` — 增量披露字段集

当前(F-08-C 观察):copy_payload_for 只塞 factor 列表,user_state 整段剥离 → cache_miss=120 tokens。

**提案**:在 copy_payload_for 输出中加入以下字段(分两组):

**组 A — Stable prefix-cacheable 字段**(放 payload 前部,跨用户 ~80% 相似,可被 cache hit 部分覆盖):

```
user_state_summary:
  profile:
    gender, age, city_level, vip_level, is_svip
  context:
    device_type, hour
```

预估 byte cost: ~80 bytes,全是低-中熵字段。这一组 entropy 低,跨 20 个 stage-3 reqs 有显著重复,cache prefix 有效率高。

**组 B — Per-request signal-dense 字段**(放 payload 后部,完全 per-request,不进 cache):

```
user_state_signals:
  profile_counts:
    register_days, click_cnt_30d, order_cnt_30d, order_cnt_90d,
    purchase_price_avg_30d, fav_price_avg_30d, coupon_use_cnt_30d,
    cart_cnt_30d, fav_brand_cnt_30d
  behavior_top_lists:
    prefer_cat3_topK, prefer_brand_topK, seq_click_cat3_48h, seq_click_brand_48h,
    order_goods_id_list_topN, order_brand_id_list_topN, order_cat3_id_list_topN,
    addcart_goods_id_list_topN, addcart_brand_id_list_topN, addcart_cat3_id_list_topN,
    collect_goods_id_list_topN, collect_brand_id_list_topN, click_brand_id_list_topN
  target_product_derived:
    price_vs_user_baseline_ratio, brand_recent_touched, ctr_band, is_new
```

预估 byte cost(组 B): ~1400 bytes(全 behavior 头部列表是大块)。

**预估 copy_generation `prompt_cache_miss` 落点**: 1200-1800 tokens(组 B 全 miss + 组 A 部分 miss + factor 列表 + product info 已有)。**目标区间 [500, 5000] 满足**。

### 3.2 `rubric_payload_for` — 增量披露字段集

当前(F-08-C 观察):rubric_payload_for 几乎只看 factor + copy_text,user 信号缺失 → rubric 跨候选打分缺判别力(F-08-B 报告:5 candidates 全 admit)。

**提案**:rubric 比 copy 需要 MORE user 信号(它要判断"这条 copy 对*这个*用户合不合适")。在 rubric_payload_for 输出中加入 §3.1 全部组 A + 组 B,**额外**加:

```
candidate_bridge_logic:
  对每个 copy candidate,把 generate-copy-candidates 节点产出的
  bridge_logic / used_copyable_hooks / intended_effect 三字段 verbatim 传递
  (当前 rubric 看不到这些 — copy_artifact.candidates[i] 含但 rubric 入参剥离)
```

预估 rubric `prompt_cache_miss` 落点: 2500-3500 tokens(更高于 copy,合理)。

### 3.3 `generate-copy-candidates/SKILL.md` line 41 改写

**当前规则**(F-08-C 报告):

> "Hook words come only from `factor.evidence_refs[].value` or `derived_features_by_product[product_id]` bucket label. Nowhere else."

**问题**:此规则把 hook 词来源焊死到 factor 摘抄 + derived bucket label,即使新增 §3.1 字段进 payload,LLM 也不能用。

**改写**(SKILL prose 语言,统一术语,**不引用用户口头举例**):

> "Hook anchors may be drawn from any field in `user_state` or `target_product` available in the payload, with two constraints:
> (a) the resulting copy text must not contain literal tokens from `user_state.behavior.*_id_list_topN` strings (e.g. specific brand names or product names from the user's history) — those are evidence for the disposition, not copy material;
> (b) anchors should be reusable across users sharing the same disposition, not overfit to a single user's literal behavior."

此改写允许 §3.1 全部字段进入 hook 池,但仍守住 phase-1 决策 "copy contains no literal user-history tokens"(in `PROJECT.md`)。

### 3.4 排除清单(明确不进 payload)

| 字段 | 排除理由 |
|---|---|
| `profile.user_id` | 唯一识别,无 disposition 价值,且 PII 风险 |
| `profile.region_level` | 与 city_level 重合,优先 city_level |
| `behavior.click_goods_id_list_topN` | 与 prefer_cat3 + seq_click 重合,边际信号低 |
| `behavior.collect_cat3_id_list_topN` | 与 prefer_cat3 重合 |
| `behavior.click_cat3_id_list_topN` | 与 prefer_cat3 重合 |
| `context.day_of_week` | 本批 sampler 零方差(11/11=3),不可用作差异化;待 sampler 修复后 reconsider |
| `products[].attributes.*` 完整长 list(`click_timestamp_list_topN` / `collect_timestamp_list_topN` 等) | 时间戳长 list 占 byte 大但 disposition 信号低,聚合到 ctr_band 即可 |
| `derived_features_by_product[].click_timestamp_list_topN` | 同上 |

### 3.5 Cache prefix 稳定性策略

为最大化 cache hit:

1. **payload 内部字段顺序固定**:组 A 字段固定顺序放 dict 前部,组 B 字段固定顺序放后部 — 让前 N 个 token(SKILL + 组 A 头部)成稳定 prefix
2. **空字段不 omit 而是显式 null**:`addcart_brand_id_list_topN: null` 比"字段缺失"让 prefix 长度跨请求更稳
3. **数字精度规范化**:`purchase_price_avg_30d: 42.33`(保留 2 位)避免 `42.333332` 长 float 表示差异

---

## 4. 字段集总览

`copy_payload_for` 输出新增字段集合(去重):

```
组 A: gender, age, city_level, vip_level, is_svip, device_type, hour
组 B: register_days, click_cnt_30d, order_cnt_30d, order_cnt_90d,
      purchase_price_avg_30d, fav_price_avg_30d, coupon_use_cnt_30d,
      cart_cnt_30d, fav_brand_cnt_30d,
      prefer_cat3_topK, prefer_brand_topK, seq_click_cat3_48h,
      seq_click_brand_48h, order_goods_id_list_topN, order_brand_id_list_topN,
      order_cat3_id_list_topN, addcart_goods_id_list_topN,
      addcart_brand_id_list_topN, addcart_cat3_id_list_topN,
      collect_goods_id_list_topN, collect_brand_id_list_topN,
      click_brand_id_list_topN,
      target_product_derived: price_vs_user_baseline_ratio,
      brand_recent_touched, ctr_band, is_new
```

`rubric_payload_for` 输出新增字段集合: copy 全集 + `candidate_bridge_logic` (per-candidate `bridge_logic` / `used_copyable_hooks` / `intended_effect` 三字段)。

---

## 5. 预期结果(待 G5 真实 batch 验证)

| Metric | 当前(0527 batch) | 提案后预期 |
|---|---|---|
| copy_generation prompt_cache_miss | 120 tokens | 1200-1800 tokens(在 [500, 5000] 目标区间) |
| copy_generation total_tokens | ~18000 | ~22000-24000(增 ~25%,可接受) |
| rubric prompt_cache_miss(平均) | 跨 reqs 跨度 1152-11008 (F-08-03)| 2500-3500 tokens(中位) |
| rubric 判别力 | 5/5 admit 无 floor violation(F-08-B) | 至少 1/5 reqs 出现 admit/hold 混合,floor_violations 出现非空 |
| 文案多样性(F-08-A 角度命中) | 主要 D5(美学)单一维度 | 多维度命中(D1/D2/D3/D5 至少 3 维度) |

---

## 6. Task 2 实施清单(待 sign-off 后执行)

- `seers_harness/workflow/payloads.py:copy_payload_for`:按 §3.1 字段表新增组 A + 组 B 字典片段,固定顺序
- `seers_harness/workflow/payloads.py:rubric_payload_for`:按 §3.2 字段表新增 user_state 字段 + per-candidate bridge_logic
- `workflow-skills/current/generate-copy-candidates/SKILL.md`:替换 line 41 hook-words 规则为 §3.3 改写文案,使用项目统一术语,不字面引用用户举例
- `seers_harness/workflow/payloads.py`:数字精度规范化 helper(round float 到 2 位)
- 单测:`tests/test_payloads_disclosure.py` 验证字段集严格匹配 §4 清单,字段顺序固定,排除清单字段不在输出

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 组 B 全 miss 让 cache_miss 超过 5000 上限 | 预估 1400 bytes ≈ 1700 tokens,远低于 5000 上限。若 G5 实测超 → 反过来减组 B 字段(优先减 collect_*) |
| 新增字段让 token 总量超 deepseek-v4-pro 上下文 | 当前 total ~18000;新增 ~5000 仍远低于模型上限(64K-128K class)|
| `behavior.*_id_list_topN` 字段含具体品牌 / 商品名 → LLM 把它直接写进文案,违反"copy 不含用户字面 token" decision | SKILL §3.3 改写后规则 (a) 明确禁止;rubric 后续要 catch — 若 G5 实测 catch 失败,新增 G6 加 lint |
| sampler day_of_week 零方差是别处的 bug,本提案无法解决 | 排除清单标 day_of_week 排除;sampler 修复在 phase 9+ 单独 ticket |

---

## Sign-off

待用户签字确认字段边界:

- **字段集合**: 同意 §4 清单
- **SKILL line 41 改写**: 同意 §3.3 改写文本
- **cache_miss 目标区间**: [500, 5000] tokens

Sign-off: pending
