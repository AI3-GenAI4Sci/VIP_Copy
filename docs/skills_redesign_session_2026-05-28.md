# SKILLS 重设计讨论纪要 — 2026-05-28

> 本文档来源于 2026-05-28 的一次 case 分析与 SKILLS 重设计讨论。讨论的入口是
> `tests/smoke/.runs/20260528T055154Z/` 这次 phase-8 G5 真实 DeepSeek Stage 3
> 跑批的 evidence。文档目标是把"为什么当前 SKILL/schema/payload 写不出好
> slogan"讲清楚，并落出可执行的删 / 改 / 重写清单，留给后续 phase 9 的
> SKILLS 重写工作使用。

---

## 1. 入口现象

`20260528T055154Z` 跑批接通了演化机制的核心闭环：bootstrap 完整跑过一次，
distill_after_stage1 真从 bootstrap 的四份 evidence 里抽出 3 条 delta
（`delta_social_proof_concreteness` / `delta_anchor_portability_preference` /
`delta_value_language_without_numbers`），portfolio 实际持有 3 条 delta。
但 Stage 3 c=20 在第一个 in-flight future 上就遇到 DeepSeek 402 Insufficient
Balance，runner 进入 fail-fast，剩余 16 条被砍断，最终 `gaps_found`。

撇开余额问题，这次 batch 暴露的真问题是 **slogan 质量本身**。
当前 SKILLS 教模型写出来的最优级别长这样：

- `这瓶兰蔻香，终于轮到你`
- `用过都说好，这瓶闭眼入`
- `不必显小显大，香就刚好`
- `孩子护得好好的，你的脸呢`

这些句子都是**单段心理叙事**，**几乎没有商品事实**——LLM 不是写得不好，是
SKILL/schema/axis 的组合在结构上**不允许**它写好。

---

## 2. 真目标：商品册个性化

> 同一商品，不同用户感兴趣的点不一样。slogan 的天职是**让商品自己推销自己**，
> 同时**叠一层用户场景共鸣**。

参考的标准结构（用户给的衬衫例子）：

```
品牌特卖，正品保障  /  挺括有型，彰显成熟魅力
^^^^^^^^^^^^^^^^^^      ^^^^^^^^^^^^^^^^^^^^^^^^
事实层 + 风险层          属性层 + 情感层
（商品自我推销）         （用户共鸣钩）
```

四件事在一句话里同时落地：**事实 + 风险 + 属性 + 情感**。当前 SKILL 教出的
"终于轮到你"只有第四层中的半个，且零商品事实。

防晒同一商品对不同用户的演示：

| 用户 | slogan |
|---|---|
| A：31 岁妈妈，UPF50+ 儿童防晒衣已购 | `蜜丝婷温和到能给娃用，你的脸也该护一程` |
| B：20 岁大学生，敏感肌，购买均价 ¥58 | `泰版小黄帽敏感肌也能稳，学生党刚好接住` |

同一瓶防晒，**激活的商品事实子集不同**（A: 温和 / 可儿用；B: 泰版 / 敏感肌 /
学生党价位）；用户钩也不同（A: 陪娃迁移防护；B: 浏览已久 + 价格接得住）。
这是商品册个性化的命门。

---

## 3. tool error 全集（`record_candidate` 6 条硬规则）

写在 `seers_harness/tools/skill_tools.py:194-340`。按写入顺序：

| # | 规则 | 这次 trace 触发 | 应该是硬还是软 | 处理 |
|---|---|---|---|---|
| 1 | `text == considered_drafts[chosen_draft_index]` | 没 | **硬**（数据完整性）| 保留 |
| 2 | 无阿拉伯数字 | 没 | **硬**（暴露 retrieval 边界）| 保留 |
| 3 | 无 CN 数字+单位组合 | 没 | **硬** | **缩窄白名单**：剔出"份/月/年/天/号"，只留货币/折扣单位（折/元/块/毛/百分/倍）。"一份心意"、"三月里"不该被误伤 |
| 4 | 可见中文字符 ∈ [10,16] | **触发**（"这瓶兰蔻，终于轮到你" 9 字被拒，逼模型加无意义的"香"凑到 11）| **软**（风格偏好）| **从 tool 删，移到 SKILL 作 guidance**："多数好 slogan 落在 12–22 字，更短或更长当结构需要时都可" |
| 5 | `bridge_logic.product_anchor / relation_anchor` 都是 text 字面子串 | **大规模触发**（4 条 candidate 在 turn-1 全栽，turn-2 又栽 4 次）| 字段本身错（见 §4）| **整条删**，连同 BridgeLogic 字段重设计 |
| 6 | 无 user_history token leak | 没 | **硬**（隐私）| 保留 |

应该新增的真硬规定（SKILL 软提示挡不住，应该上 tool 层）：

- **无系统自指**——正则白名单挡 `为你推荐 / 根据你的偏好 / 系统检测到` 等
- **无身份判定标签词**——挡 `妈妈群体 / 中产 / 银发族 / 学生党` 这类**用作判定**
  的标签；注意 `陪娃 / 刷牙 / 挑了那么久` 这种**场景描写**不挡

---

## 4. schema 字段逐字段判生死

`domain/models.py:25-79` 定义了 `PersonalizationFactor`、`BridgeLogic`、
`CopyCandidate` 三张表。逐字段：

### 4.1 CopyCandidate（13 字段）

| 字段 | 评价 | 处理 |
|---|---|---|
| `candidate_id` | 唯一标识 | 保留 |
| `product_id` + `target_product_id` | `_hydrate` 自动从 target 拷贝到 product，语义重叠 | **合并为 `product_id` 一个**，删 `target_product_id` |
| `group_key: str = ""` | trace 100% 是 `""`；schema 没人写过；下游没人读 | **删** |
| `text` | slogan 本体 | 保留 |
| `source_factor_id` | 上下游 join key | 保留 |
| `bridge_logic.product_anchor / relation_anchor` | 强制都是 text 字面子串。物理后果是 LLM 先写句子、再回头从句子里抠两个 substring 填充——schema 从句子推 schema 而不是反过来，是反向约束。relation_anchor 的语义是"哪两者之间的关系"也没在 SKILL 里定义。 | **整条 BridgeLogic 删**，用新结构 TextAnchors 替代（见 §4.3）|
| `considered_drafts: list[str]` | trace 看：5 条 drafts 全是同一个心理点的近义重排（`喷上的刹那 / 手腕一抹香 / 这缕香 / 一天里`），不产生结构性多样性 | 字段保留，但 SKILL 必须用示例说清 drafts 之间要拉开**结构差**（产品事实主导 / 用户钩主导 / 两段并置）——不是同一意思换说法 |
| `chosen_draft_index` | 与 drafts 配对 | 保留 |
| `used_copyable_hooks: list[str]` | 自由文本数组，无 validator 让它对齐 text。trace 里 c4 写了"高评论量, 高转化率, 低退货率, 高满意度"4 项，text 是"用过都说好"——0 个 hook 在 text 里出现。完全 dead 的 introspection 字段。 | **删**，被新的 `quoted_product_fact` / `quoted_user_hook` 取代 |
| `intended_effect: str` | 后置注解，0 约束。LLM 用它写"让用户感到被允许为自己消费"这种心理意图，schema 不验真。 | **删** |

### 4.2 PersonalizationFactor（7 字段）

| 字段 | 评价 | 处理 |
|---|---|---|
| `factor_id` | id | 保留 |
| `user_side_signal: str` | 用户侧叙事 | 保留，改名 `user_side_evidence_paragraph` 让语义明确 |
| `direction: user_to_need / item_to_need / cross` | "cross" 在 SKILL.md 里没定义；trace 里 4 个 factor 出现 3 种 direction 但下游没人按 direction 分流——枚举值不进入任何决策 | **删**——纯文档字段，不 load-bearing |
| `transferable_disposition: str` | 用户心理 | 保留，改名 `user_disposition` |
| `evidence_refs: list[EvidenceRef]` | 混合用户证据和商品证据，无类型区分。下游 copy_gen 想找"商品事实"得自己用 path 前缀判别。trace 里 `self_care_reclamation` 这条 factor 的 4 条 evidence_refs 全部指向 `user_state.*`，0 条产品证据。 | **拆成两个字段**：`user_evidence_refs` / `product_evidence_refs`，类型相同但语义分离，schema 各要求至少 1 条 |
| `bridge: str` | SKILL 定义是"door's logic"——心理桥的散文。Trace 里全是抽象心理叙事，没装产品卖点。 | **拆**：新增 `product_side_proposition`（该因子下产品的卖点是什么）；`bridge` 改名 `meeting_logic`，说明两者怎么对接 |
| `covers_product_ids: list[str]` | id | 保留 |

### 4.3 新 TextAnchors（替代 BridgeLogic）

```python
class TextAnchors(BaseModel):
    quoted_product_fact: str    # text 字面子串，指向商品事实
    quoted_user_hook: str       # text 字面子串，指向用户场景/心理
    model_config = {"extra": "forbid"}
```

两字段都必须**非空**——`quoted_user_hook` 空了就是单段心理叙事，正是这次 trace
的塌方根因。两字段都是 substring 没变，**但语义角色明确**：

- `quoted_product_fact` 必须指向商品事实——品牌名 / 品类词 / 属性词 / 定性价位
  词 / 社会证明定性带
- `quoted_user_hook` 必须指向用户钩——场景 / 动作 / 历史 / 心理触发

tool 层只做 substring 检查（语义判定做不准）；语义约束放在 SKILL 文字 + 对照
示例里。

---

## 5. SKILL.md 当删的段（不是改，是删）

### 5.1 `generate-copy-candidates/SKILL.md`

| 段 | 内容 | 为什么删 |
|---|---|---|
| Purpose 整段 | "The user is, by default, not yet interested..." | meta-叙事，对 LLM 0 信息增益。LLM 不需要被说服为什么要写 copy |
| Workflow step 4 "slogan cadence" | "A short two-beat line cut by a comma" | 把单段两拍当成 slogan 唯一形态——错。slogan 可以是单段、两段、四段，结构由内容决定 |
| Workflow step 5 "Match the user layer" | "youthful self-expression register..." | "register"是文学批评词，LLM 抓不到；产物是空话 |
| reflect_on_diversity 第 1 条头字符检测 | "Read the first 3 characters..." | 头字符相同对真失败 0 discrimination；trace 里全部"recorded"无一被它拦下 |
| reflect_on_diversity 第 3 条 22/35/55 通吃 | "land for at least two of the three" | **反个性化**——slogan 就应该只对某个用户 land，对别的用户不响 |
| Key rule "One anchor per line; one door per candidate" | 把多锚结构判违规 | 直接禁掉"商品事实 + 用户钩"双锚结构 |
| Anti-pattern 列表 6 条 | 抽象类别标签，无 bad/good 对比示例 | 不给示例 LLM 只能猜什么算"universal"或"emotion-only filler" |
| Composition 段 | 上下游说明 | 给做编排的人看的，不是给 LLM |
| Language 段 | 中文输入→中文输出 | 一句话，inline 即可 |

剩下能保的核心：**factor 是角度不是词汇 / 视角翻转 / 商品事实必须显现 /
用户钩必须显现**。

### 5.2 `discover-personalization-factors/SKILL.md`

| 段 | 处理 |
|---|---|
| 9 步走的 step 3-7（door enumeration / selection / 5 silent layers / non-obvious / transferability）| **压缩为 3 步**：扫场景 → 列商品事实清单 → 配对成"商品命题 ↔ 用户处境"对 |
| Key rule "A role, identity, life stage, tier, or family relation is a *scene input*, not a factor conclusion" | 保留——这条是真的 |
| Anti-pattern 6 条 | 大半删，没示例的 anti-pattern 列表是噪音 |

### 5.3 `personalized-copy-rubric-judge/SKILL.md`

| 段 | 处理 |
|---|---|
| `no_price_or_number_hook` 措辞 | **删"price-implication wording"那一段**，定性价格描述（特卖 / 入门价 / 性价比 / 破价）放行；只挡数字 / 货币符号 / 百分比 / 折扣率 |
| `welcome_address` 措辞 | 改为"用户身份不作为**判定标签**出现；场景式描写不受限"，并给对照示例（`妈妈版的`❌，`陪娃出门`✅） |
| 7 轴 | **加第 8 轴 `product_fact_present`**（floor=true）：可见 text 是否携带至少一个具体商品事实碎片（品牌 / 属性 / 观察标签 / 价位定性词）|
| Workflow step 2 "Critique-before-verdict" | 保留，真规则 |

### 5.4 Python 硬编码的 reflect prompt（`skill_tools.py:96-126`）

`_REFLECT_COVERAGE` 和 `_REFLECT_DIVERSITY` 不是 SKILL.md，是 Python 字符串常量。
SKILL 改了这里也要改：

- `_REFLECT_COVERAGE` Q1 让 LLM 列出每个 behavior 字段并解释为什么 skip——
  **过程仪式，删**
- `_REFLECT_DIVERSITY` Q1 头字符检测、Q3 三个年龄通吃——**全删**。换成：
  - Q1: "每条 candidate 的 quoted_product_fact 是否指向商品事实（品牌/品类/
    属性/价位定性/社会证明定性）？任何指向心理状态或动作的判 fail"
  - Q2: "每条 candidate 的 quoted_user_hook 是否指向该用户场景（动作/历史/
    心理触发）而非通用情感词？"

---

## 6. payload 实测：copy_gen 端拿到的上下文

### 6.1 当前给的（`copy_payload_for` in `seers_harness/workflow/payloads.py:167`）

- `user_state_summary.profile`：gender / age / city_level / vip_level / is_svip
- `user_state_summary.context`：device_type / hour
- `user_state_signals.profile_counts`：register_days / click/order/purchase_price_avg 等 9 项
- `user_state_signals.behavior_top_lists`：13 个 list（订单/加购/收藏/点击 × goods/brand/cat3 + seq + prefer + click_brand），每个含 topN 长字符串
- `user_state_signals.target_product_derived`：price_vs_user_baseline_ratio / brand_recent_touched / ctr_band / is_new
- `factors`：上游完整 factor 列表
- `products + target_products`：每个产品的**完整 attributes 字典**——含
  几十个 unix 时间戳数组（`collect_timestamp_list_topN` /
  `click_timestamp_list_topN`），把 `item_brand_name=兰蔻`、`item_arriv_price=249`
  这种关键字段淹在噪音里

### 6.2 该有但没有的（**4 项缺失**）

- ❌ `selling_points` / `feature_highlights`：商品营销上挂的"卖点 tags"
  （`敏感肌温和` / `持久留香` / `国货之光` / `宝藏品牌` 这种**已被商家定性化**
  的标签）
- ❌ `key_attribute_phrases`：商品标题/详情页 SKU 描述里**可作 copy 锚点**的
  短语清单（兰蔻这个 SKU 的"花香调"、"奇迹"、"节日礼物"全在 `item_name` 里
  要 LLM 自己挑）
- ❌ `value_position_label`：定性的价位位置（`深折` / `破价` / `入门款` /
  `正价`），而不是 `discount_rate=0.5081633`
- ❌ `social_proof_band`：把 `review_cnt=1193, item_satisfy=0.93,
  return_rate_30d=0.002` 这堆数字**汇总为定性带**（`评论密集` / `高满意` /
  `退货低`——这些可直接进 text 不违规）

### 6.3 user_state 侧的过度披露

13 个 behavior_top_lists 全开，每个 topN 长字符串列表——这是 prompt 体积肿
的另一半根因（前一半是跨 request 不共享 prefix）。trace 里 partial copy 平均
prompt_cache_miss = 15154 tokens，远高于签字的 [500, 5000]。

---

## 7. factor 产出能不能推导出商品+用户双钩 slogan？

不能。`PersonalizationFactor` 当前 7 个字段里：

- 6 个是用户/心理侧（`user_side_signal` / `transferable_disposition` /
  `direction` / 部分 `evidence_refs` / 部分 `bridge` / `factor_id`）
- 1 个 `evidence_refs` 是混合无结构的

trace 实证：`self_care_reclamation` 这条 factor 的 4 条 evidence_refs 全是
`user_state.*`，0 条产品证据。下游 copy_gen 想写商品事实，**结构上 factor 没
装载这件事**。

应当强制改 schema：

```python
class PersonalizationFactor(...):
    user_evidence_refs: list[EvidenceRef]      # 至少 1 条 path 指向 user_state.*
    product_evidence_refs: list[EvidenceRef]   # 至少 1 条 path 指向 products[*].attributes.* 或 derived_features_by_product.*
    user_disposition: str                       # 用户心理
    product_side_proposition: str               # 该因子下产品的卖点是什么 — NEW
    meeting_logic: str                          # 二者如何对接（原 bridge 改名）
```

这样 copy_gen 端拿到 factor 时**强制看到两份证据 + 两条 narrative**，slogan 的
"前段=product_side_proposition / 后段=user_disposition"映射在 factor 层就预成形。

---

## 8. 重写后的 `generate-copy-candidates/SKILL.md` 草稿

下面这版按 LLM-targeted 写，**不是给人看的**：imperative voice，每个字段配
示例，软硬规定分清。

````md
---
name: generate-copy-candidates
description: For one (product, factor) pair, write one card slogan that carries both a concrete product fact and a concrete user-side hook quoted from the same line.
---

# Generate Copy Candidates

## What you receive

Per request:
- `factors`: each factor has `product_side_proposition`, `user_disposition`,
  `product_evidence_refs`, `user_evidence_refs`.
- `products[*].attributes`: brand name, cat3 name, item_name, observed labels,
  social-proof figures, price-position bucket.
- `derived_features_by_product`: precomputed user×product relations.

## What you write per (product, factor) pair

`CopyCandidate` with these fields. **Each field shown with one example value.**

| Field | Example | Note |
|---|---|---|
| `text` | 兰蔻特卖正品到手，花香一缕只为自己 | Any length, any structure. Single-beat, two-segment, three-segment all valid. Pick the form the message demands. |
| `text_anchors.quoted_product_fact` | 兰蔻 | Literal substring of text. Must be a product fact: brand / category / observed label / qualitative price position / qualitative social-proof band. |
| `text_anchors.quoted_user_hook` | 只为自己 | Literal substring of text. Must be a user-side fragment: scene / action / personal history / psychological trigger. |
| `considered_drafts` | [花香一缕只为自己, 兰蔻入门款香给自己留, 兰蔻特卖正品到手花香一缕只为自己] | At least 3 drafts; each must vary in structural emphasis (product-led vs user-led vs balanced), not in word choice. |
| `chosen_draft_index` | 2 | `text` must equal `considered_drafts[chosen_draft_index]`. |

## Hard rules (tool will reject)

- No Arabic digits. No CN digit+currency unit (一折 / 五元 / 八块).
- No system self-reference (no 为你推荐, no 根据你的偏好).
- No user-history tokens that are not also product tokens (privacy leak).
- `quoted_product_fact` is a literal substring of `text` AND references a
  product fact (brand name, category word, attribute term, qualitative price-
  position word, qualitative social-proof descriptor). Anchoring on a
  psychological state or generic action fails.
- `quoted_user_hook` is a literal substring of `text` AND references a user-
  side fragment (scene, action, history echo, psychological trigger).
  Anchoring on a product feature fails.

## Soft guidance (judgment, not gate)

- Length: most good slogans land in 12–22 visible characters. Shorter or longer
  is fine when structure demands.
- Form: single-beat (花香一缕只为自己) and multi-segment (兰蔻特卖正品到手，
  花香一缕只为自己) both valid. Pick the form the message demands. Do not force
  two-beat when the angle is single.
- Identity: scene-style writing (陪娃出门 / 刷牙这件事) is allowed. Label-style
  writing (妈妈群体 / 中产人群) is not — translate the label into the moment
  the label creates.
- Qualitative price talk (特卖 / 入门价 / 性价比 / 破价) is allowed. Numbers,
  percentages, currency are forbidden.
- Qualitative social proof (评论密集 / 回头客多 / 口碑好) is allowed. Numeric
  proof (1193 条评论) is not.

## Examples — bad vs good

| Bad | Why bad | Good | Why good |
|---|---|---|---|
| 这瓶兰蔻香，终于轮到你 | quoted_product_fact = 兰蔻 OK; quoted_user_hook = 轮到你 is a psychological promise with no concrete user evidence quoted; line sells nothing about the product beyond brand | 兰蔻入门款，金卡刚好接住 | product_fact = 兰蔻入门款 (brand + qualitative price-position); user_hook = 金卡刚好接住 (the user's VIP tier as concrete history) |
| 用过都说好，这瓶闭眼入 | product_fact absent (这瓶 is deictic); user_hook absent (generic crowd appeal) | 评论密集的兰蔻香，跨过日常就这一回 | product_fact = 评论密集的兰蔻香 (qualitative social-proof + brand); user_hook = 跨过日常就这一回 (first prestige purchase as scene) |
| 孩子护得好好的，你的脸呢 | user_hook strong; product_fact ABSENT — line sells no concrete product attribute | 蜜丝婷温和到能给娃用，你的脸也该护一程 | product_fact = 蜜丝婷温和 (brand + attribute); user_hook = 能给娃用，你的脸也该护一程 (scene + transfer logic) |

## Workflow

For each (product, factor) pair:

1. Inventory the product facts the factor surfaces. From
   `factor.product_side_proposition` + `factor.product_evidence_refs` +
   `products[*].attributes`, list 2–4 quotable fragments. These are your
   candidate `quoted_product_fact`s.

2. Inventory the user-side hooks the factor surfaces. From
   `factor.user_disposition` + `factor.user_evidence_refs`, list 2–4 quotable
   fragments. These are your candidate `quoted_user_hook`s.

3. Write 3+ drafts varying which product fact meets which user hook, and in
   which structural form. Drafts must differ in structure, not just word
   choice. One draft can be product-led, one user-led, one balanced.

4. Select the draft where both anchors point to something concrete and the
   line reads naturally. If no draft has both, regenerate — do not submit a
   single-anchor line.

5. Submit through `submit_copies_final`.

If the factor surfaces no quotable product fact, skip this (product, factor)
pair. Skipping is preferred over a hollow line.
````

---

## 9. `discover-personalization-factors/SKILL.md` 重写骨架

不贴整版，结构改动：

- 删 9 步走，改 3 步：扫场景 → 列商品卖点 → 配对
- 每个 factor 必须同时输出 `product_side_proposition` 和 `user_disposition`，
  schema 改为两字段 required
- `product_evidence_refs` 至少 1 条 path 指向 `products[*].attributes.*` 或
  `derived_features_by_product.*`
- `user_evidence_refs` 至少 1 条 path 指向 `user_state.*`
- 每个新字段在 SKILL.md 里有一段例子（trace 里 `smart_deal_prestige_entry` 这
  条 factor 的 bridge 写得好——明确点出了"五折 + 阿迪点击 + 金卡识别真折扣"
  的产品命题；`self_care_reclamation` 是反例——"是一扇罕见的、只为自己打开
  的窗"是心理隐喻，0 商品事实可锚）

---

## 10. 行动清单（按优先级排序）

| 优先级 | 工作项 | 涉及文件 |
|---|---|---|
| P0 | 长度 [10,16] 从 tool 层移到 SKILL guidance；length validator 删除 | `seers_harness/tools/skill_tools.py:313-320` |
| P0 | BridgeLogic 整体改为 TextAnchors，字段改名 quoted_product_fact / quoted_user_hook，两字段必填非空 | `seers_harness/domain/models.py:50-79` + `seers_harness/tools/skill_tools.py:322-337` |
| P0 | `no_price_or_number_hook` axis 措辞改：禁数字 / 货币符号 / 百分比 / 折扣率，放行定性价格词 | `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md:29` |
| P0 | rubric 加第 8 轴 `product_fact_present`（floor=true）| 同上 |
| P1 | PersonalizationFactor schema：拆 evidence_refs 为 user/product 两份；新增 product_side_proposition；bridge 改名 meeting_logic | `seers_harness/domain/models.py:25-47` |
| P1 | CopyCandidate 删 group_key / target_product_id（合并到 product_id）/ used_copyable_hooks / intended_effect | 同上 |
| P1 | `direction` 枚举从 PersonalizationFactor 删除 | 同上 |
| P1 | reflect_on_diversity 头字符检测 + 22/35/55 通吃删除 | `seers_harness/tools/skill_tools.py:112-126` |
| P2 | copy_payload_for 新增 4 字段：selling_points / key_attribute_phrases / value_position_label / social_proof_band | `seers_harness/workflow/payloads.py:167` |
| P2 | user_state_signals.behavior_top_lists 从 13 项压缩到信号密度高的 5-6 项，缓 prompt_cache_miss 肿大 | 同上 |
| P2 | generate-copy-candidates SKILL.md 整体重写为 §8 草稿 | `workflow-skills/current/generate-copy-candidates/SKILL.md` |
| P2 | discover-personalization-factors SKILL.md 整体重写为 §9 骨架 | `workflow-skills/current/discover-personalization-factors/SKILL.md` |
| P3 | tool 层加新硬规定：no system self-reference / no identity-label-as-judgment | `seers_harness/tools/skill_tools.py` |
| P3 | CN 数字+单位白名单缩窄：剔出 份/月/年/天/号 | `seers_harness/tools/skill_tools.py:47-50` |

---

## 11. 关键判断回顾

1. **slogan 形式不是硬性规定**——单段、两段、四段、长短都是工具，由内容决定。
   当前 schema 的长度硬上限和 SKILL 的"two-beat line cut by a comma"措辞都把
   软约束当成了硬约束。

2. **schema 字段不是越多越好**——`used_copyable_hooks` / `intended_effect` /
   `group_key` / `direction` 四个字段都是后置注解或文档式占位，不进入任何
   validator，对 LLM 是 token 浪费，对系统是 dead code。删。

3. **schema 字段需要例子值**——只声明字段名+类型不够。LLM 看不到例子就只能
   猜字段该填什么，于是 `intended_effect` 被填成了"让用户感到被允许为自己
   消费"这种心理意图叙述。新版 SKILL 的"What you write"表强制每个字段配一个
   示例值。

4. **tool 层和 SKILL 层职责分清**——tool 层做 deterministic 检查（substring /
   正则 / 类型），SKILL 层做语义引导。当前 `bridge_logic` 两个 anchor 强制
   substring 是 tool 在做语义判定（靠 LLM 自己保证 substring 的语义角色），
   失败模式是 LLM 反向操作：先写句子、再回填 substring。新版 TextAnchors 把
   语义角色（product_fact / user_hook）写进字段名 + SKILL 示例，tool 只检查
   substring，分工清晰。

5. **不要补丁式改动**——这次讨论暴露的是 schema 层、payload 层、SKILL 层、
   axis 层、reflect prompt 层**五个层面的协同问题**。任意一层不动，下一次跑
   仍会在同一处塌方。`07-WRIN-TRIAGE.md` 的关单应等这一轮重设计落地，否则
   是 phase-8 演化机制空转。
