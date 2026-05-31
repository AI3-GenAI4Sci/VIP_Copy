---
name: personalized-user-mining
description: Use when mining reusable user-side personalization factors from profile, behavior history, context, and list-level signals.
---

# 用户侧个性化挖掘

## 目标

从用户侧 payload 中提炼 `UserPersonalizationArtifact`。该节点只处理用户画像、行为历史、上下文和轻量列表语境，不读取 target product 详情。产物应当能被后续多个商品复用，作为商品文案生成的用户侧 brief。

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
- `evidence_refs`：中性证据引用。

## 方法

```text
行为事实 -> 显性需求/潜在诉求 -> 现状不满或购买顾虑 -> 用户因子
```

- **显性需求**：用户主动浏览、点击、加购、收藏、购买的类目和品牌。
- **潜在诉求**：跨类目关联、高点击低下单、收藏未购买、深夜活跃、价格相对位置和列表组合。
- **现状不满**：用户为什么现在可能需要被改善，例如熬夜脸、牙龈敏感、通勤疲惫、选品纠结。
- **购买顾虑**：用户为什么还在犹豫，例如怕踩雷、陌生品类、价格门槛、效果不确定。

把因子分成三种用途：

- **核心痛点**：可以直接形成短文案入口。
- **场景痛点**：由时间、地点、任务或生活状态触发，用于增强代入感。
- **决策痛点**：影响下单，用口碑、品牌、价值感、低门槛或活动感承接。

关键判断要交叉信号。单独的时间、年龄、会员等级只提供语境；当它们与类目、品牌、加购、收藏、价格或近期序列共同出现时，才形成更强的用户因子。

## 工具流程

1. 用 `maintain_user_factors_artifact(action="read")` 查看已有状态。
2. 用 `upsert_many` 或 `delete_many` 维护用户因子。
3. 需要检查覆盖时调用 `reflect_on_user_factor_coverage`，回答后继续更新。
4. 完成后调用 `maintain_user_factors_artifact(action="validate")`。
5. validate 返回 `valid` 后，下一次工具调用必须是 `maintain_user_factors_artifact(action="save")`。

## 工程硬门

- 不写商品承接、不写 copy。
- 每个因子必须有 `user_factor_id` 和 `evidence_refs`。
- id 原样保留。
- 输出使用输入语言；中文输入产出中文 prose。

## 输出

生成 `UserPersonalizationArtifact`。
