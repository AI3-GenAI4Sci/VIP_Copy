---
name: personalized-user-mining
description: Use when mining reusable user-side personalization factors from profile, behavior history, context, and list-level signals.
allowed-tools: none
---

# 用户侧个性化挖掘

## 目标

从用户侧 payload 中提炼 `UserPersonalizationArtifact`。该节点只处理用户画像、行为历史、上下文和轻量列表语境，不读取 target product 详情。产物应当能被后续多个商品复用，作为商品文案生成的用户侧 brief。

本节点追求少量高价值用户动机，不追求审计式覆盖。优先保留最能驱动文案承接的 2～3 条用户因子。

## 输入

- `user_state_summary`：画像、设备、活跃时间等稳定摘要。
- `user_state_signals`：点击、加购、收藏、下单、类目、品牌、价格偏好和行为序列等用户侧信号。
- `list_context`：当前 request/list group 的轻量语境，例如目标类目组合。

## Artifact

每个 `user_factor` 是一条用户侧转化假设：

- `user_factor_id`：用户因子 id。
- `signal_basis`：压缩后的用户信号簇。
- `need_or_pain`：显性需求、潜在诉求、现状不满或购买顾虑。
- `scene_trigger`：触发需求的时间、场景、任务或生活状态。
- `buying_heuristic`：用户判断“值不值得点/买”的方式。
- `expression_hooks`：可给文案使用的痛点词、场景词、利益方向。

## 方法

```text
粗扫用户信号 -> 选择最强动机 -> 写成可复用用户因子
```

- 先粗扫类目/品牌/近期行为、订单/加购/收藏、列表语境三类信号。
- 只选择最强的 2～3 个动机簇，例如护肤功效、儿童用品、家庭囤货、通勤穿搭、价格犹豫。
- 每条因子写成“用户为什么会被某类商品打动”，而不是复述所有信号。

把因子分成三种用途：

- **核心痛点**：可以直接形成短文案入口。
- **场景痛点**：由时间、地点、任务或生活状态触发，用于增强代入感。
- **决策痛点**：影响下单，用口碑、品牌、价值感、低门槛或活动感承接。

关键判断要交叉信号。单独的时间、年龄、会员等级只提供语境；当它们与类目、品牌、加购、收藏、价格或近期序列共同出现时，才形成更强的用户因子。

不要逐表遍历、不要列证据清单、不要为了覆盖所有类目扩写弱因子。宁可输出 2 条强因子，也不要输出 5 条重复或牵强因子。

## 可用工具

无。本节点在 DeepSeek JSON mode 下运行，不允许调用、请求或暗示任何工具。

## JSON 输出

不要在思考或草稿中展开 JSON 片段。最终只输出一个完整合法 JSON object，不输出 Markdown、解释文本、自然语言前后缀或工具调用。

根对象只能包含 `user_factors` 一个字段。`user_factors` 是对象数组，字段形状如下：

```json
{
  "user_factors": [
    {
      "user_factor_id": "UF_001",
      "signal_basis": "面部精华偏好rank=1；下单补水精华；加购美白淡斑精华；......",
      "need_or_pain": "皮肤干燥、暗沉、初老，想快速看到补水淡纹效果；......",
      "scene_trigger": "早晨出门前、换季干燥期、熬夜后急救；......",
      "buying_heuristic": "优先看功效成分、次抛形态、口碑品牌和套组性价比；......",
      "expression_hooks": ["急救补水", "淡纹", "次抛精华", "......"]
    },
    {
      "user_factor_id": "UF_002",
      "signal_basis": "儿童服装/玩具/洗护均有近期点击或订单；......",
      "need_or_pain": "为孩子挑选安全、舒适、有趣的用品，希望省心不踩雷；......",
      "scene_trigger": "换季添衣、夏季玩水、日常洗护补货；......",
      "buying_heuristic": "看儿童专用、材质温和、品牌口碑和价格是否划算；......",
      "expression_hooks": ["儿童专用", "温和安全", "换季新衣", "......"]
    },
    ...
  ]
}
```

类型约束适用于整个 JSON，而不是只适用于示例：

- `user_factor_id`、`signal_basis`、`need_or_pain`、`scene_trigger`、`buying_heuristic` 必须是字符串。
- `expression_hooks` 必须是字符串数组，不能写成一句自然语言。
- 除上述字段外不能增加未知字段。

## 数量要求

- 有可用用户信号时，默认产出 2～5 条彼此不同的用户因子。
- 只选择最强商业动机，不为覆盖所有行为表或所有目标类目扩写弱因子。
- 信号较少但仍可解释时，至少产出 1 条可复用用户因子。
- 只有在没有任何可用用户信号时，才输出空数组。
- 每个 `user_factor_id` 在同一 JSON artifact 内唯一。

## 工程硬门

- 不写商品承接、不写 copy。
- 每个因子必须有 `user_factor_id`、`signal_basis`、`need_or_pain`、`scene_trigger`、`buying_heuristic` 和 `expression_hooks`。
- `need_or_pain` 必须是可复用购买动机，不是画像标签或行为字段改名。
- id 原样保留。
- 输出使用输入语言；中文输入产出中文 prose。

## 输出

生成 `UserPersonalizationArtifact`。
