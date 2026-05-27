---
finding_id: F-08-B
status: confirmed
severity: P0 (kills all SKILL-prose-based quality controls)
phase: 08
batch_id: 20260527T123110Z
discovered: 2026-05-28
investigator: Agent B
scope: copy_generation + personalized_copy_rubric_judge real-LLM outputs
---

# F-08-B: 文案模板化与去 personalization 的根因 — SKILL prose 根本没下发到模型

## TL;DR

用户抱怨的「商品名+几个字拼接 / 句式高重复 / 多样性差 / personalization 缺失」**不是 SKILL 设计失败**——
SKILL.md 的全部 prose（包括 generate-copy-candidates 的 5 步 + 7 反模式、personalized-copy-rubric-judge
的 7 binary axes + floor 规则）**从未进入 LLM 的 system message**。

`seers_harness/workflow/dag_runner.py:84` 写死了字面字符串：

```python
result = run_skill_via_tools(
    skill_name=node.skill_name,
    skill_bundle="SKILL_BODY",   # ← 字面 10 字节字符串，不是 SKILL.md 内容
    ...
)
```

下游 `agentic/tool_loop.py:51` 把这 10 字节当 system prompt 塞进 messages：
`{"role": "system", "content": "SKILL_BODY"}`。

证据 — 三个 sample 的 `messages.jsonl[0]`（copy_generation 和 rubric 节点都一样）：

```
ROLE: system  CONTENT_LEN: 10  '"SKILL_BODY"'
```

模型在没有 SKILL prose 的情况下，**靠 tool spec 的 `description` + 自身先验** 写文案。
当前 tool spec 的 description 只讲机械约束（长度 10–16、anchor literal、不能含数字、不能泄露 user
history），从未告诉模型「不要把商品名当文案、要换 anchor、要多样化句式」。模型自然按训练分布里
最常见的"广告卡 slogan"模式输出 —— **"4字情绪短语，3-5字连接词 + 商品名"** 正是商业广告语
料的众数模板。这就是用户看到的"宠爱自己，用兰蔻奇迹香水"。

下面所有"SKILL prose 没起作用 / 反模式没被触发 / 7 axes 只剩 3-5 axes"的现象，**唯一上游因都是
这一行字面常量**。把它修了，其他 6 条修复才有任何意义。

---

## 1. 逐 candidate 字面分析（3 个 sample）

### Sample 1 — perfume (兰蔻奇迹香水) — stage1
n=5 candidates；mean visible-CN length = **11.0 chars**；含完整商品名 `兰蔻奇迹香水` 的 = **4/5**；含
`兰蔻奇迹` 前缀的 = **5/5**；comma-template-head `[4字]，...商品名` 匹配 = **5/5**。

| # | text | 模板分解 |
|---|------|---------|
| 1 | 气质升级，就选兰蔻奇迹香水 | `[4字情绪]，就选 + 兰蔻奇迹香水` |
| 2 | 宠爱自己，用兰蔻奇迹香水 | `[4字情绪]，用 + 兰蔻奇迹香水` |
| 3 | 大牌不贵，兰蔻奇迹香水 | `[4字情绪]，+ 兰蔻奇迹香水` |
| 4 | 护肤之后，有兰蔻奇迹相伴 | `[4字情绪]，有 + 兰蔻奇迹 + 相伴` |
| 5 | 轻奢入门，选兰蔻奇迹香水 | `[4字情绪]，选 + 兰蔻奇迹香水` |

5 行都是同一句法骨架，仅情绪短语换皮。所谓"5 个角度"在 `intended_effect` 里能区分，但落到 text
里只剩 4 字情绪词的差异——这种差异在卡片场景下用户读不出来。

### Sample 2 — posture cushion (护腰坐垫) — stage2-1
n=5；mean = **12.2 chars**；含产品名 `坐垫/护腰垫/矫姿垫` 的 = **5/5**；comma-template-head = **1/5**。

| # | text | 模板分解 |
|---|------|---------|
| 1 | 学生护腰坐垫，久坐不累好帮手 | `[人群+品类]，[功能+收尾词]` |
| 2 | 矫姿护腰垫，性价比超高入手 | `[品类]，[价格短语]` |
| 3 | 好评如潮护腰坐垫，舒适矫姿 | `[社证+品类]，[功能短语]` |
| 4 | 久坐办公腰酸？矫姿坐垫解救 | `[痛点提问]，[品类]+解救` |
| 5 | 运动品牌矫姿垫，品质有保障 | `[品牌+品类]，[质量短语]` |

句法相对更分散（疑问、痛点、社证、品牌、价格），但 5 行里 `护腰/矫姿 + 坐垫/垫` 出现 5 次——
品类名仍是主要"信息"，用户能在图片+标题已知品类的前提下，从文案里**几乎读不到额外信息**。
case 2 / 5 退化成"功能+收尾词"广告语。

### Sample 3 — sunscreen (蜜丝婷小粉帽) — stage2-3
n=**7**（这里说明 LLM 没把候选数控制在 5）；mean = **10.4 chars**；含 `小粉帽` 或 `蜜丝婷` 的 =
**7/7**；comma-template-head = **3/7**。

| # | text | 模板分解 |
|---|------|---------|
| 1 | 护肤首选，小粉帽防晒霜 | `[绝对断言]，+ 商品昵称+品类` |
| 2 | 蜜丝婷防晒，超值性价比 | `[品牌+品类]，[价格短语]` |
| 3 | 全家防晒，小粉帽来守护 | `[场景]，+ 商品昵称+来守护` |
| 4 | 蜜丝婷国际品牌，品质值得信赖 | `[品牌+定位]，[质量短语]` |
| 5 | 尝鲜新品防晒，选小粉帽 | `[新品]，选+商品昵称` |
| 6 | 好评如潮防晒，选小粉帽 | `[社证]，选+商品昵称` |
| 7 | 户外运动防晒，选小粉帽 | `[场景]，选+商品昵称` |

candidate 5/6/7 完全同骨架（`[修饰]+防晒，选小粉帽`）。candidate 1 用了 SKILL 明确禁止的绝对
断言"首选"，**rubric 也确实标了 `unsubstantiated_absolute_claim`**——但 rubric 给的是 `hold`，没有
`reject`，且也只判了 1 个 candidate 就 submit_final 了（artifact 只有一个 judgment，其它 6 个未判）。

---

## 2. SKILL prose 审计（generate-copy-candidates）

### 想"阻止"模板化的 prose（**全部未进入 LLM**）

`SKILL.md:23-31` 五步骨架明确写：

```
3. Choose an anchor type. Land the angle on exactly one of: a specific moment, a sensory
   or bodily reaction, a third-party reaction, a contrast, a habit or trait, an observable
   consequence, or a physical detail of the product itself. Anchor types are diversity
   dimensions across the candidate set, not a checklist for one line.

4. Write to slogan cadence. A short two-beat line cut by a comma; concrete nouns instead
   of abstract category words; conversational register, like a friend leaning in with one
   piece of advice.
```

`SKILL.md:35` 多样性检查：

```
6. Call reflect_on_diversity. Its core questions are whether candidates spread across
   distinct psychological doors and across distinct anchor types, and whether any two
   candidates would still work after swapping their products. Same-anchor or same-door
   clusters are the failure to catch here.
```

`SKILL.md:50-56` 反模式列表里有 4 条直接命中现在的失败：
- `Universal merchant line` — 完全击中"气质升级，就选 X"
- `Factor-noun echo` — 击中"大牌不贵, X"
- `Emotion-only filler` — 击中"宠爱自己, 用 X"
- `Same anchor across the set` — 击中 sample-3 后三行

### 可能"诱导"模板化的 prose
None worth flagging — SKILL prose 内部矛盾很少。问题不在 prose 本身。

### 判决
**Prose 设计是合格的；它从未到达模型。**

---

## 3. LLM reasoning 考古（perfume case）

从 `messages.jsonl` 的 assistant turns 提取（reasoning_content 字段）：

### 第一轮 reasoning（生成初稿，候选全以 `兰蔻奇` 开头）：

> "Let me plan 5 candidates with different factors:
> Candidate 1: F3_feminine_self_expression - perfume as invisible accessory
> ...
> **Let me brainstorm some copies:**
> For F3 (feminine self-expression):
> - 兰蔻奇迹香水，你的隐形配饰 (Lancôme Miracle perfume, your invisible accessory) - 13 chars
> For F2 (mother self-reward):
> - 兰蔻奇迹，宠爱自己的花香时刻 ..."

**关键观察**：模型自发把每条都以"兰蔻奇迹..."起头。它没看到 SKILL prose 里关于 anchor diversity
的要求；它只看到 `record_candidate` tool description 里的"anchors literal in text"——于是把"商品名是
anchor 且必须出现"误读为"商品名最自然的位置是开头"。考虑过的 `隐形配饰`、`花香时光`、
`点睛之笔` 都是更具体的 anchor，但**全部被同一骨架包住**。

### 第二轮 reasoning（被 `reflect_on_diversity` 触发后"修复"）：

> "1. First 3 characters of each candidate:
> - c1: 兰蔻奇 (starts with 兰蔻奇迹香水)
> - c2: 兰蔻奇 ...
> **All 5 start with 兰蔻奇! That's a problem - 3 or more starting with the same product
> anchor. I need to re-record some candidates with different anchor heads.**
>
> Let me redesign with different heads:
> c1: '气质升级，就选兰蔻奇迹香水' - starts with '气质升' - 13 chars
> c2: '宠爱自己，用兰蔻奇迹香水' - starts with '宠爱自' - 12 chars
> c3: '大牌不贵，兰蔻奇迹香水' - starts with '大牌不' - 11 chars
> c4: '护肤之后，有兰蔻奇迹相伴' - starts with '护肤之' - 13 chars
> c5: '轻奢入门，选兰蔻奇迹香水' - starts with '轻奢入' - 12 chars
>
> Now the first 3 chars are all different ..."

**致命发现**：`reflect_on_diversity` 的 question 1 只问"前 3 个字符是否相同"。模型机械满足这条
canary 后，把**所有更具体的 anchor（隐形配饰 / 花香时光 / 点睛之笔 / 半价奢宠 / 把巴黎带回家）
全部丢弃**，换成 4 字情绪词。原 considered_drafts 里更有"温度"的版本（如"做妈妈也做女神"、"把巴黎带回家"）**在最终 chosen 里被全部淘汰**：

```json
"considered_drafts": [
  "兰蔻奇迹，宠爱自己的花香时光",   // 更具体的"花香时光" anchor
  "宠爱自己，用兰蔻奇迹香水",       // ← 选中：通用情绪+商品名
  "做妈妈也做女神，兰蔻奇迹"       // 最具人物 voice 的版本
],
"chosen_draft_index": 1
```

模型自己在 reasoning 里写下了"做妈妈也做女神"这种**真正 personalize 给妈妈的句子**，
然后选了**最通用的那条**。这是 reflect 的 canary 太机械（只查头 3 字符）+ SKILL prose 没下发
（没有"sensory anchor / habit anchor / third-party reaction"那段教学）的合力结果。

---

## 4. Rubric 也在失败 — 7 axes 退化成 LLM 自创的 3 / 5 axes

### Perfume case（兰蔻奇迹）：每一条都是 `admit`，零 floor_violations。

`SKILL.md (personalized-copy-rubric-judge):18-32` 明确规定 7 个 axes：

```
factor_fit, persuasion_specificity, user_perspective, welcome_address,
no_system_introspection, no_price_or_number_hook, retrieval_portability
```

实际 artifact 里 5 个 candidate 的 per_axis 都只有 **3 个 axes**：
```
factor_relevance, emotional_resonance, brand_fit
```

这 3 个 axes **完全是 LLM 自己编的**。SKILL 规定的 6 个 floor axes 一个都不在。这意味着：

- `user_perspective` floor 没跑 → "宠爱自己，用兰蔻奇迹香水" 这种纯商家命令句不会被 reject
- `persuasion_specificity` floor 没跑 → 通用情绪短语没有 anchor 也能 admit
- `welcome_address` floor 没跑 → 任何身份标签也不会被 catch（虽然这批没出现）

### Posture cushion case（学生护腰坐垫）：每一条 `admit`。

实际 axes：`clarity, relevance, persuasiveness, fluency, factuality` — **依然是模型自创**，且
更偏"广告基本面"而非 SKILL 规定的 personalization 检查。

### Sunscreen case（小粉帽）：第 1 个 candidate `hold`，floor_violations=`unsubstantiated_absolute_claim`。

实际 axes：`factual_accuracy, relevance_to_product, grammar_spelling, brand_compliance, emotional_tone`。
注意 `floor_violations` 字段写了一个 axis ID（`unsubstantiated_absolute_claim`），这个 ID
**不存在于 per_axis 数组里**——证明 rubric 的 floor 机制也在乱猜（schema 允许，但 SKILL contract 完全被忽略）。同时此 sample 的 artifact **只判了 1 个 candidate 就 submit_judgments_final**——剩下 6 个未判 —— 进一步证实模型在没有 SKILL 引导下不知道"要把每一个 candidate 都判完"。

### 该 catch 没 catch 到的内容
对 perfume 5 条而言，**`persuasion_specificity` 应该 reject 至少 4 条**（无具体 moment/sensory
/contrast/habit anchor，只有抽象情绪）。但 LLM 自创的 `factor_relevance`、`emotional_resonance`
完全没要求 anchor 必须是具体物——它甚至给"气质升级"这种最抽象的词打了 pass + "Strong alignment
with feminine self-expression factor; culturally resonant '气质' concept."

### 判决
**Rubric 是合格的"理论"判官；它从未拿到判决书。** 同一 SKILL_BODY 字面常量 bug。

---

## 5. 「商品名必须在文案里」的来源

搜索结果：

- **SKILL.md** (generate-copy-candidates)：从未要求文案"必须"包含商品名。`SKILL.md:41` 只要求
  "Hook words come only from `factor.evidence_refs[].value` or `derived_features_by_product
  [product_id]` bucket label"——这是关于"用什么 hook"，不是"必须出现完整商品名"。

- **Tool spec `RECORD_CANDIDATE_SPEC`** (skill_tools.py:594-605)：description 写了
  "anchors literal in text"——但**"anchor"= `bridge_logic.product_anchor + relation_anchor`**，不是商品名。
  代码层面 `skill_tools.py:319-332` 校验的就是这两个 anchor 字符串是 text 子串。

- **Pydantic 模型** (`BridgeLogic`, `CopyCandidate`)：`product_anchor` / `relation_anchor` 是
  free-form `str = ""`，没有任何"必须等于商品名"的约束。

**结论**：SKILL prose、tool spec、pydantic 三层**全都没有**强制"商品名出现"。是 **LLM 在没有 SKILL
guidance 时，把 `product_anchor` 这个字段名直觉理解为"产品名是 anchor"，又把"anchor 必须 literal
in text"理解为"产品名必须出现"**。这是 tool spec 字段命名 + 空 SKILL prose 的组合诱导。

证据 — perfume case 模型 reasoning 自述：

> "**Bridge: product_anchor: '兰蔻奇迹香水', relation_anchor: '气质升级'**
> ...
> Check 'anchors literal in text':
> - c1: '兰蔻奇迹香水' - anchors product name
> - c2: '兰蔻奇迹' - anchors brand + product line
> ..."

模型把 `product_anchor` = product name 当成了第一直觉。

---

## 6. Diversity floor — 现状几乎不存在

SKILL prose 搜 `diversity / distinct / varied`：

- `SKILL.md:27` "Anchor types are diversity dimensions across the candidate set"
- `SKILL.md:35` `reflect_on_diversity` "whether candidates spread across distinct
  psychological doors and across distinct anchor types"
- `SKILL.md:56` Anti-pattern "Same anchor across the set"

但因为 SKILL prose 没下发，模型只能看到：

`tool_loop.py:51` 注入的 system message = `"SKILL_BODY"`（10 字节）
+ `reflect_on_diversity` 返回的 `_REFLECT_DIVERSITY` 文本（skill_tools.py:107-121）：

```
1. Read the first 3 characters of every candidate text you have recorded.
   List the heads. Are 3 or more starting with the same product anchor?
   If yes, your structural variety is fake — re-record those candidates with different
   anchor heads.

2. Imagine a retrieved user who does NOT share the literal behavior tokens of the current
   user. For each candidate, would the line still feel honest to that user ...

3. Read each candidate as a 22-year-old, a 35-year-old, and a 55-year-old.
   Does it land for at least two of the three? ...
```

**这是当前唯一的 diversity 信号**。它只查 3 件事：
1. 前 3 字符不重复（→ 模型把商品名挪到尾巴就过关）
2. 跨用户可移植性（→ 模型给的"宠爱自己" / "气质升级"都过得了，因为它们本来就极通用）
3. 三个年龄段可读（→ 模型给的"轻奢入门" / "气质升级"也过——它们越通用越容易过）

**这三个 canary 全部奖励"更通用"的文案**，而 SKILL prose 真正想要的"distinct anchor types
(moment/sensory/contrast/habit/consequence)"、"physical detail of product itself" 完全没进入
reflect 通道。perfume case 的"前 3 字符多样化"修复正是这种激励错配的直接产物。

---

## 7. 修复建议（按 leverage 排序，原子，每条触一个文件）

### Fix #1 — **P0**：把 SKILL.md 真实内容下发到 LLM
**文件**：`seers_harness/workflow/dag_runner.py`

把第 84 行的字面常量替换为读取 `workflow-skills/current/<skill_name>/SKILL.md` 并把文件内容作为
`skill_bundle`。这是所有其他 6 条修复的前提；不做这条，其他 6 条全部无效。

```python
# 当前（line 84）
skill_bundle="SKILL_BODY",

# 改为
skill_bundle=load_skill_body(node.skill_name),   # 读取并缓存 SKILL.md 全文
```

修完后 token cost 会因为 prompt prefix 增长可能上升 ~2-4k tokens/call，但绝大多数会被 DeepSeek
prompt cache 命中（参考 F-08-03 的 cache 命中率讨论）。

### Fix #2 — 修 `reflect_on_diversity` 的激励错配
**文件**：`seers_harness/tools/skill_tools.py:107-121`（`_REFLECT_DIVERSITY` 字符串）

当前 question 1 只问"前 3 字符相同？"，被模型用"换 anchor 位置"机械绕过。改为问 SKILL prose
里真正的 anchor 类型分散：

```
1. For each candidate, name the anchor type it sits on (one of: specific moment, sensory
   or bodily reaction, third-party reaction, contrast, habit or trait, observable
   consequence, physical detail of product). If two or more candidates share the same
   anchor type, re-record one of them on a different anchor type — not by rephrasing
   the same anchor.

2. For each candidate, write the 4–6 character fragment that carries the persuasion
   angle (i.e., remove the product name and the connector words like 选 / 用 / 就选 /
   入手). If the remaining fragment is a generic emotion word (宠爱自己 / 气质升级 /
   轻奢入门 / 大牌不贵 类), the line has no anchor — re-record with a concrete noun
   or moment.

3. Swap the product name in each candidate with any other product of the same category.
   Does the line still read as if it could have been written for the swapped product?
   If yes, the line has no this-product-specific anchor — re-record.
```

新 Q2 直接把"4 字情绪+商品名"模式钉死，新 Q3 直接把"通用句"钉死。

### Fix #3 — 在 `record_candidate` tool description 中显式禁止"商品名拼接"模板
**文件**：`seers_harness/tools/skill_tools.py:589-604`（`RECORD_CANDIDATE_SPEC.function.description`）

当前 description 只讲 6 条结构性约束。append 一段语义约束：

```
The text must NOT degrade to '<short emotion phrase>, <connector> <product name>'.
The product_anchor is a permission to mention the product, not a requirement to put the
product name in the visible text — when a stronger non-product anchor (a moment, a
sensory reaction, a habit) carries the angle, use it as the visible text and put only
the minimal product reference at the tail.
```

### Fix #4 — 重命名 `product_anchor` → `product_reference_in_text`（消除诱导）
**文件**：`seers_harness/domain/models.py:50-53`（`BridgeLogic`）+ `seers_harness/tools/skill_tools.py:573-583`（spec properties）+ pydantic alias

`product_anchor` 这个字段名把"产品名"和"anchor 类型"两件事混在一起。改为 `product_reference_in_text`
后，SKILL prose 里"anchor type = moment/sensory/contrast/habit/..." 才能不跟 schema 字段名冲突。
向后兼容用 pydantic `alias=` 保留旧 key。

### Fix #5 — 在 rubric SKILL prose 里显式给出 axis_id 枚举（防 LLM 编新 axes）
**文件**：`workflow-skills/current/personalized-copy-rubric-judge/SKILL.md`

当前 SKILL.md:24-32 已经列出了 7 个 axis_id，但 LLM 实际跑出来全是自创 axes（`factor_relevance`/
`clarity`/`factual_accuracy` 等）——这部分原因是 SKILL prose 没下发（Fix #1 修），但即使下发后
也建议在 SKILL.md 顶部加：

```
## Axis identifiers (closed set — do not invent)

axis_id MUST be one of exactly these seven strings; any other axis_id in per_axis
is a contract violation:

  factor_fit | persuasion_specificity | user_perspective | welcome_address |
  no_system_introspection | no_price_or_number_hook | retrieval_portability
```

### Fix #6 — `judge_candidate` tool 加 axis_id 枚举校验
**文件**：`seers_harness/tools/skill_tools.py:653-667`（`_PER_AXIS_PROPERTIES`）

`axis_id` 当前是 free-form `string`。加 enum：

```python
"axis_id": {
    "type": "string",
    "enum": [
        "factor_fit", "persuasion_specificity", "user_perspective",
        "welcome_address", "no_system_introspection",
        "no_price_or_number_hook", "retrieval_portability",
    ],
},
```

这一条 + Fix #5 联合，把 rubric 的 7-axis contract 从"SKILL prose 口头规定"升级为"strict tool spec
强制"。模型自创 axes 直接 schema-reject。

### Fix #7 — `submit_judgments_final` 校验"每个 candidate 都被判过"
**文件**：`seers_harness/tools/skill_tools.py:419-429`（`submit_judgments_final` 函数）

当前函数只校验 schema，不校验 coverage。sunscreen sample 里只判了 1/7 个 candidate 就 final 了。
加：

```python
expected_ids = {c["candidate_id"] for c in (state.get("copies_artifact") or {}).get("candidates") or []}
judged_ids = {j["candidate_id"] for j in artifact.model_dump()["judgments"]}
if expected_ids - judged_ids:
    raise ToolValidationError(
        message=f"submit_judgments_final missing judgments for: {sorted(expected_ids - judged_ids)}",
        tool_name="submit_judgments_final",
    )
```

---

## 最深的 3 个 root cause 与 top 2 修复

### 三个 root cause（按因果深度排序）

1. **SKILL_BODY 字面常量** (`dag_runner.py:84`)：SKILL prose **从未下发** 给 LLM。这一个 bug 单独
   解释了全部下游失败——"反模式"没触发因为 LLM 没看过反模式；"7 axes"退化成自创 3-5 axes 因为
   LLM 没看过 axes 列表；diversity 检查被"换前 3 字符"绕过因为模型不知道"anchor type"是什么。

2. **Diversity reflect canary 的激励错配** (`_REFLECT_DIVERSITY` Q1)：只查"前 3 字符是否
   重复"，模型机械满足后**抛弃了 `considered_drafts` 里更具体的版本**，反而退化到更通用的模板。
   即使 SKILL 下发了，这条 canary 仍会拉低质量。

3. **`product_anchor` 字段名 + 空 SKILL prose 的共谋诱导**：在没有 SKILL prose 教学"anchor 是
   moment/sensory/habit 等 7 类语义概念"的前提下，模型把 `product_anchor` 字段名直接理解为
   "产品名是 anchor"，又把"anchor literal in text"读成"产品名必须在 text 里"。

### Top 2 最高 leverage 的修复

- **Fix #1**：把 `"SKILL_BODY"` 字面常量换成真正读取 SKILL.md。这一条解锁了 60%+ 的 SKILL prose
  设计意图，是其他所有修复的前提。

- **Fix #2**：重写 `_REFLECT_DIVERSITY` Q1/Q2/Q3，把"前 3 字符不重复"替换为"命名 anchor type" +
  "剥掉商品名后看剩下的是不是通用情绪词" + "换商品名后是否仍然成立"。这条独立于 Fix #1 也有效，
  直接钉死现在最严重的"4字情绪+商品名"模板。
