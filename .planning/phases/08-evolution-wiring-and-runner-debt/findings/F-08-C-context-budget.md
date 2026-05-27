# F-08-C — Context Budget 审计：每节点收到了什么 vs 原始 payload 还有什么

**Agent C 任务**：审计 DAG 三个节点（factor_discovery / copy_generation / personalized_copy_rubric）实际接收的 user_state 与 product_state 字段，对比原始 payload，定位"factor summary 瓶颈"。

**样本**：`tests/smoke/.runs/20260527T123110Z/stage1/-6834635816105165003`（一个真实 request；1 个 product；user_id=294379371）。

---

## 1. Payload 顶层 key 对照表

数据来源：每个节点 `evidence/<node>/messages.jsonl` 的 `message[1].content`（即 tool-loop 注入的 user message）。

| 顶层 key | factor_discovery | copy_generation | personalized_copy_rubric |
|---|---|---|---|
| `scenario_id` | √ | √ | √ |
| `request_id` | √ | √ | √ |
| `minimum_semantic_unit` | √ | √ | √ |
| `schema_version` | — | — | √ |
| **`user_state`** | **√（profile×20 + behavior×16 + context×3）** | **× 已被剥离** | **× 已被剥离** |
| `products` | √（完整 attributes，含 24 个 click_timestamp_list_topN 等）| √（同 factor_discovery） | √（同 factor_discovery） |
| `target_products` | √ | √ | × |
| `target_product_count` | √ | √ | × |
| `derived_features_by_product` | √（11 个 bucket label） | √ | × |
| `list_context` | √（target_categories 等） | √ | × |
| **`factors`** | — | **√（factor 摘要 + 部分 evidence_refs.value）** | **× 已被剥离** |
| `candidate_generation_policy` | — | √ | — |
| `candidates` | — | — | √（仅 6 字段：candidate_id / candidate_index / product_id / factor_id / copy_text / group_key） |
| `candidate_count` | — | — | √ |

**关键缺失（红行）**：

- `user_state` 在 factor_discovery 之后**整体消失**，下游两个节点完全看不到原始用户字段。
- `factors`（含 `transferable_disposition` / `bridge` / `evidence_refs`）在 copy_generation 之后**整体消失**，rubric 完全看不到。
- rubric 收到的 candidate 行**仅 6 字段**，连 copy artifact 自带的 `bridge_logic` / `used_copyable_hooks` / `intended_effect` / `considered_drafts` 都被丢弃（详见 §6）。

字符级体量对比：13800 → 24356 → 6517（chars）。copy_generation 因为塞入了 8 条 factor 的长摘要总字数最大；rubric 最瘦。

---

## 2. Token 成本曲线（prompt_cache_miss_tokens）

来自 `evidence/<node>/usage.json`：

| 节点 | prompt_tokens | cached | **cache_miss（新内容）** | completion |
|---|---:|---:|---:|---:|
| factor_discovery | 24,385 | 17,024 | **7,361** | 4,021 |
| copy_generation | 17,656 | 17,536 | **120** | 1,141 |
| personalized_copy_rubric | 6,457 | 3,968 | **2,489** | 2,661 |

**形态**：U 形不对称谷底——factor_discovery 7361 → copy_generation **120**（!） → rubric 2489。

> copy_generation 的 cache_miss 仅 120 tokens 是一个强信号：它在 prompt 里几乎没有 LLM 没见过的"新增个性化语料"，绝大多数是 SKILL bundle + 重复的 products/derived_features 命中前缀缓存。"新内容"压缩到极致，与 §1 表观察到的 user_state 整体剥离一致。

注：120 这个 miss 不等于"copy_gen 看到的总信息量小"——它仍然要读完 24356 字符，但其中绝大部分对模型而言是"重复的产品事实+缓存的 SKILL"，**真正新的、对该用户独有的语料只有 ~120 tokens 那么多**（即 8 条 factor 摘要被前缀缓存吃掉一部分后剩下的增量）。

---

## 3. DAG plumbing 源码引用：哪一行做了切片

**唯一一处 payload 切片中心**：`seers_harness/workflow/payloads.py`。WorkflowRuntime 通过 `provider_payload_for_node(...)` 把 scenario 收窄成 node-specific view（`dag_runner.py:78-81`）。

### 3.1 copy_generation 切片（`payloads.py:86-112`）—— **user_state 在此被剥离**

```python
def copy_payload_for(*, scenario, factors_artifact=None) -> dict[str, Any]:
    """...NO raw user_state — copy lines are derived from the public factor signals
    in factors_artifact."""
    s = _scenario_dict(scenario)
    artifact = factors_artifact or {}
    products = list(s.get("products") or [])
    return {
        "scenario_id": s.get("scenario_id"),
        ...
        "factors": list(artifact.get("factors") or artifact.get("personalization_factors") or []),
        "products": products,
        "target_products": products,
        ...
        # ← 注意：没有 "user_state" 这个 key
    }
```

注释明确写了 *"NO raw user_state"*。这是设计意图（master_plan §4.5），**但本审计的核心问题是：这个意图是否过紧**——见 §4 与 §5。

### 3.2 personalized_copy_rubric 切片（`payloads.py:115-147`）—— **factors + user_state 都被剥离**

```python
def rubric_payload_for(*, scenario, copy_artifact=None) -> dict[str, Any]:
    ...
    candidates: list[dict[str, Any]] = []
    for idx, candidate in enumerate(copy.get("candidates") or []):
        candidates.append({
            "candidate_id": candidate.get("candidate_id") or f"candidate-{idx}",
            "candidate_index": idx,
            "product_id": str(candidate.get("product_id") or ""),
            "factor_id": str(candidate.get("source_factor_id") or ""),
            "copy_text": str(candidate.get("text") or ""),
            "group_key": str(candidate.get("group_key") or ""),
        })
    return {
        "schema_version": "request_personalized_copy_rubric_payload_v1",
        ...
        "products": list(s.get("products") or []),
        "candidates": candidates,    # ← 6 个字段，bridge_logic 等都丢了
        "candidate_count": len(candidates),
        # ← 没有 user_state，没有 factors，没有 derived_features_by_product
    }
```

`copy_artifact` 里现成的 `bridge_logic.product_anchor` / `bridge_logic.relation_anchor` / `used_copyable_hooks` / `intended_effect` / `considered_drafts` 在拼装 rubric payload 时被显式丢弃。

### 3.3 dispatch（`payloads.py:163-175`）

```python
if node_id == "factor_discovery":
    view = factor_payload_for(scenario)
elif node_id == "copy_generation":
    view = copy_payload_for(scenario=scenario,
                           factors_artifact=deps.get("factor_discovery") or {})
elif node_id == "personalized_copy_rubric":
    view = rubric_payload_for(scenario=scenario,
                              copy_artifact=deps.get("copy_generation") or {})
```

DAG 把每个节点的视图限定在严格 down-stream-reduced 集合里。`scenario` 整体一直在内存中（runner 持有），但每个节点只拿到自己那份"切片"。

---

## 4. factor_discovery 看见但 copy_generation 看不见的具体字段

这是本 finding 的核心证据。我枚举了 8 个 factor 在 `evidence_refs[].path` 引用过的所有 user_state 路径，与原始 user_state 全集做差。

### 4.1 完全没有任何 factor 引用过的 user_state.behavior 字段（→ 对 copy_generation 彻底丢失）

| 字段 | 该用户的真实值 | 用户区分度 |
|---|---|---|
| `addcart_brand_id_list_topN` | 真维斯(6), 都市丽人(5), 阿迪达斯(4), 洁柔(3), 韩后(2) | **高**：购物车里的品牌 ≠ 点击/订单中的品牌 |
| `addcart_cat3_id_list_topN` | 文胸(5), 跑步鞋(4), 家居拖鞋(4), 女式打底衫(4), 抽纸(3) | 高：未下单意图层 |
| `collect_brand_id_list_topN` | **美特斯邦威(3), 森马(3), 班尼路(1), 丝柏舍(1), 真维斯(1)** | **极高**：收藏品牌只在收藏里出现，prefer_brand 完全没盖到 |
| `collect_cat3_id_list_topN` | 女式牛仔裤(5), 女式休闲裤(3), 婴幼儿牛奶粉(2), 女式西服(1), 家居拖鞋(1) | 高：长期愿望品类 |
| `prefer_brand_topK` | **韩后(1), 真维斯(2), 阿迪达斯(3), 都市丽人(4), 洁柔(5), 苏秘37°(8)** | **极高**：用户的品牌偏好排名 |
| `seq_click_brand_48h` | **爱依服(2), 阿迪达斯(2)** | **极高**：48 小时品牌足迹（用户的"当下心情"） |

### 4.2 完全没有任何 factor 引用过的 user_state.profile 字段

| 字段 | 该用户的真实值 | 备注 |
|---|---|---|
| `age` | 31 | 人生阶段强信号 |
| `cart_cnt_1d` / `cart_cnt_30d` | 0 / 5 | 即时意图 |
| `click_cnt_1d` | 0 | 当日活跃度 |
| `coupon_use_cnt_30d` | 0 | 价格敏感度反指标 |
| `fav_price_avg_30d` | 0.0 | 收藏价位带 |
| `fav_brand_cnt_30d` | 5 | 收藏多样度 |
| `fav_cnt_1d` / `fav_cnt_30d` / `fav_item_cnt_30d` | 0 / 0 / 0 | 收藏行为节奏 |
| `order_cnt_30d` | 3 | 近 30 天下单量 |

### 4.3 完全没有任何 factor 引用过的 user_state.context 字段

| 字段 | 值 |
|---|---|
| `hour` | 9 |
| `day_of_week` | 3 |

时间上下文（"周三上午 9 点用 iPhone 浏览"）是文案锚点（如"早高峰、通勤、周三"）的最直接来源，但 factor 一行都没引用，copy_gen 就拿不到。

> 注：上面这些字段并非"被代码删除"——它们在 factor_discovery 节点确实存在；但因为**只有被 factor 写入 `evidence_refs[].value` 的字段才有机会到 copy_generation**，未被 factor 引用的字段就在切片处永远消失了。**factor artifact 是用户原始信号唯一的运输工具**。

---

## 5. "factor summary"瓶颈：copy_generation 拿到的是有损压缩

### 5.1 实证测量

| 维度 | factor_discovery 输入 | copy_generation 输入 |
|---|---|---|
| 用户 user_state 字段总字符 | **1363**（behavior 1311 + profile 44 + context 8） | **0**（user_state 整体不存在） |
| 来自 factor.evidence_refs 的实证字符 | — | **1872**（44 个 evidence_refs.value 拼接） |
| 全部 factor 摘要文本（user_side_signal + transferable_disposition + bridge + evidence_refs） | — | ~6500 字符（factors 字段总长） |
| 独立中文实体词（unique zh tokens via regex） | **89** | **83** |
| 命中具体品牌（`阿迪达斯/爱依服/唐狮/真维斯/班尼路/韩后/都市丽人/洁柔/美特斯邦威/森马/苏秘37°/小浣熊` 共 12 个）| **12/12** | **12/12**（被多个 factor user_side_signal 复述提到） |
| 命中具体商品片段 7 个 | **7/7** | **6/7**（`拖鞋女夏` 这个 collect_goods 片段未被 factor 引用，丢失） |

表面看 copy_gen 的实体保留度还行——12/12 品牌 + 6/7 商品。但这是**因为 factor 在 user_side_signal 自然语言里复述了一些品牌名**，并不是因为原始字段被传过去。

### 5.2 但摘要损失的不是"实体名",是**信号结构**

evidence_refs 把 `prefer_brand_topK = "韩后(rank=1), 真维斯(rank=2), 阿迪达斯(rank=3)..."` 这样**带结构的排名**全文塞进 value，这部分**确实保留了**。

真正的损失发生在**未被任何 factor 引用的字段**（§4）。例如：

- `seq_click_brand_48h = "爱依服(2), 阿迪达斯(2)"` 是该用户**最近 48 小时**的品牌足迹，是写"今早刚翻过的爱依服上新"这种**当下感锚点**最直接的来源，但 factor 都没引用，copy_gen 因此**完全不知道用户最近 48 小时关注过什么品牌**。
- `collect_brand_id_list_topN = "美特斯邦威, 森马, 班尼路, 丝柏舍, 真维斯"` 是用户**长期收藏的品牌**，与 prefer_brand 互补（美特斯邦威/森马/班尼路在 prefer_brand 里没出现），是 "国民品牌情结" 这条角度的核心证据，但**整列都丢了**。
- `addcart_brand_id_list_topN = "真维斯(6), 都市丽人(5), 阿迪达斯(4), 洁柔(3), 韩后(2)"` 是"想要但还没付钱"的犹豫层，本应是**反挖犹豫感**的最佳锚——这种锚也丢了。
- 时间上下文（hour=9, day_of_week=3）。"周三上午 9 点"的通勤场景锚消失。

### 5.3 SKILL 关键约束放大了这个瓶颈

`generate-copy-candidates/SKILL.md` line 41 显式规定：

> *Hook words come only from `factor.evidence_refs[].value` or `derived_features_by_product[product_id]` bucket label. Nowhere else.*

也就是说，**copy SKILL 在规则层强制只允许引用 factor 已经摘抄进 evidence_refs 的片段**。这条规则与"`copy_payload` 不传 user_state"是相互锁死的：即便 copy_gen 偶然拿到 user_state 也不许引用，反过来即便 SKILL 放开也没东西可引。**因此 factor 没传出来的字段 = 文案永远到不了的字段**——这是结构性损失，不是 LLM 能力问题。

---

## 6. rubric 应该看到 vs 实际看到

### 6.1 SKILL prose 写它需要什么

`personalized-copy-rubric-judge/SKILL.md` line 14-15 显式声明 inputs：

- `state['copies_artifact']` — candidates with `text`, `source_factor_id`, `target_product_id`, **`bridge_logic`**.
- `state['factors_artifact']` — upstream factors, joined by `source_factor_id`.

且 workflow step 1 写明：

> *Reconstruct the user. Read the joined factor's scene and door, then read the candidate as a user in that scene would. Skip this step and the verdict becomes a copy review, not a personalization judgment.*

也就是说 SKILL 期望评委同时拿到 factor 全文 + 完整 candidate（含 bridge_logic）+ user 的 scene。

### 6.2 实际拿到什么

实际 rubric `message[1]` payload 只有：

- 6 字段的 candidate：`candidate_id` / `candidate_index` / `product_id` / `factor_id` / `copy_text` / `group_key`
- products（产品事实）
- 没有 factors，没有 user_state，没有 derived_features_by_product，**没有 bridge_logic / used_copyable_hooks / intended_effect / considered_drafts**

实证：在 rubric 全部 4 条 messages 中文本扫描——
- `"user_state"` 出现次数：**0**
- `"factors"` 出现次数：**0**
- `"transferable_disposition"` 出现次数：**0**

`factor_id` 只是个 ID 字符串（如 `F3_feminine_self_expression`），没有任何 factor 主体可 join。

### 6.3 后果

判官**不可能**完成 SKILL workflow 第 1 步（"Reconstruct the user. Read the joined factor's scene and door"）——它没有 factor 也没有用户。因此七轴中 `factor_fit`（"line carries the upstream factor's persuasion angle through the same psychological door the factor named"）和 `retrieval_portability`（"another user sharing the same scene and door...would still receive the line honestly"）都失去了对照基准。

这与 F-08-03 观察到的 rubric 推理 token 异常 spike 可能存在因果关系：判官缺乏外部锚点时，会被迫**靠自己想象用户场景**（reasoning_tokens=915，三节点最高），而想象的场景每条 candidate 都不一样，结果是判官在为每个 candidate 重新"凭空建模一遍用户"。

---

## 7. 具体修复提案（按 leverage 降序）

每条都是 `payloads.py` 内的微改动；DAG 现有 plumbing 全部支持（runner 已经把完整 scenario 一直握在手上）。

### 7.1 [最高 leverage] copy_payload_for 增传 raw user behavior + context

**改动文件**：`seers_harness/workflow/payloads.py`
**改动函数**：`copy_payload_for(...)` （line 86-112）

```python
return {
    ...,
    "factors": [...],
    "products": products,
    ...,
    # NEW — narrow user view, NOT full user_state
    "user_state": {
        "behavior": s.get("user_state", {}).get("behavior") or {},
        "context": s.get("user_state", {}).get("context") or {},
        # profile 故意不带：profile 数值类居多，文案锚点价值低
    },
}
```

同时**修改 SKILL** `generate-copy-candidates/SKILL.md` line 41 的"only from"规则放宽：

```
Hook words may come from factor.evidence_refs[].value, derived_features_by_product[product_id]
bucket label, OR scenario.user_state.behavior fields when the chosen door explicitly references
recent or aggregated behavior (seq_click_*_48h, collect_*, addcart_*).
```

**预期收益**：把 §4.1 + §4.3 列出的 6 个 behavior 字段 + 3 个 context 字段（共 ~700 chars 高密度信号）直接喂给 copy_gen，可解锁"48h 当下心情"、"收藏长草"、"购物车犹豫"、"周三早高峰"四类锚点。文案多样性瓶颈在 F-08-02 已确认存在，这是最大杠杆。

### 7.2 [高 leverage] rubric_payload_for 增传 factors_artifact + 完整 candidate

**改动文件**：`seers_harness/workflow/payloads.py`
**改动函数**：`rubric_payload_for(...)` （line 115-147）

需要 `provider_payload_for_node` 同时把 factor_discovery dep 传下来：

```python
# in provider_payload_for_node
elif node_id == "personalized_copy_rubric":
    view = rubric_payload_for(
        scenario=scenario,
        copy_artifact=deps.get("copy_generation") or {},
        factors_artifact=deps.get("factor_discovery") or {},   # NEW
    )
```

```python
def rubric_payload_for(*, scenario, copy_artifact=None, factors_artifact=None):
    ...
    for idx, candidate in enumerate(copy.get("candidates") or []):
        candidates.append({
            "candidate_id": ...,
            "candidate_index": idx,
            "product_id": ...,
            "factor_id": str(candidate.get("source_factor_id") or ""),
            "copy_text": str(candidate.get("text") or ""),
            "group_key": ...,
            # NEW — 让 rubric 能 join factor 内容并阅读 bridge_logic
            "bridge_logic": candidate.get("bridge_logic") or {},
            "used_copyable_hooks": candidate.get("used_copyable_hooks") or [],
            "intended_effect": candidate.get("intended_effect") or "",
        })
    return {
        ...,
        "candidates": candidates,
        # NEW — SKILL workflow step 1 的 "joined factor's scene and door"
        "factors": list((factors_artifact or {}).get("factors") or []),
        # NEW — 用户上下文，让 retrieval_portability 轴有"same scene"参照
        "user_state_summary": {
            "profile": s.get("user_state", {}).get("profile") or {},
            "context": s.get("user_state", {}).get("context") or {},
        },
    }
```

**预期收益**：rubric 能真正执行 SKILL workflow step 1（reconstruct the user），`factor_fit` 和 `retrieval_portability` 两个轴有了客观基准；reasoning_tokens 应该回落（参考 F-08-03 spike）。

### 7.3 [中 leverage] copy_payload_for 增传 list_context 时间 + 用户活动级别

`list_context` 已经传了，但 `user_state.profile` 中的 `vip_level / register_days / city_level / region_level` 没传——这些是"老用户/新用户"、"二线/省份"语境锚的来源。建议同 §7.1 一起加最简一个白名单 profile 子集：

```python
"profile_summary": {
    k: s.get("user_state", {}).get("profile", {}).get(k)
    for k in ("vip_level", "register_days", "city_level", "region_level", "is_svip", "age")
}
```

### 7.4 [低 leverage、纯卫生] DAG 单元测试断言

在 `tests/test_payloads_loop06_audit.py` 增加正向断言：copy_payload `user_state.behavior` 至少包含 `seq_click_brand_48h` 和 `collect_brand_id_list_topN`（防回归）；rubric_payload `factors` 非空且每个 candidate 有 `bridge_logic`。

---

## 附录 A：本审计**未**触碰的文件（避免与他 agent 冲突）

未读：`F-08-A* / F-08-B* / F-08-D*`（其他 agent 的产出）。已读：`F-08-01/02/03`（前置 finding，仅作背景）。
