---
name: personalized-copy-generation
description: Use when generating ecommerce recommendation copy from user personalization factors, product facts, list context, and stable product-user relations.
---

# 个性化文案生成

## 目标

根据上游 `UserPersonalizationArtifact`、本次 request 的商品事实和用户-商品关系，生成 `CopyGenerationArtifact`。本节点不重新挖掘完整用户历史，只负责把用户因子转成商品可承接的商业短句。

## 输入

- `user_factors`：上游用户侧个性化因子。
- `target_products` / `products`：商品 id、类目、品牌、标题、属性、价格位置、活动、口碑、售后、可见商品事实。
- `derived_features_by_product`：类目匹配、品牌触达、价格相对位置、口碑档位等用户-商品关系。
- `list_context`：列表组合和当前 request 语境。
- `user_state_summary`：用于语气和场景定位的轻量画像摘要。

## Artifact

每个 candidate 包含：

- `candidate_id`：文案 id。
- `product_id`：目标商品 id。
- `source_user_factor_id`：来源用户因子。
- `text`：可见文案。
- `commercial_angle`：主要转化抓手，用自由短语描述。
- `product_binding`：商品如何承接用户因子。
- `fact_binding`：文案依赖的稳定商品事实或关系事实。

## 方法

```text
用户因子 -> 商品承接点 -> 商业角度 -> 可见短文案
```

1. **选择用户因子。** 从 `need_or_pain`、`scene_trigger`、`buying_heuristic`、`expression_hooks` 中找最适合该商品承接的入口。
2. **盘点商品承接。** 用商品标题、属性、类目、品牌、口碑、价格位置、活动感和 derived relation 判断商品能承接什么。
3. **确定商业角度。** 常见角度包括痛点前置、场景代入、体验结果、价值感、口碑背书、品牌信任、低门槛尝试。
4. **写短文案。** 中文推荐卡短文案默认不超过 16 个可见中文字符或标点；如果运行任务要求标题式或长短标题组合，按运行任务约束执行。文案应通过痛点、场景、体验结果或价值感表达商品，避免重复商品名。
5. **绑定证据。** 在 `product_binding` 和 `fact_binding` 中写清商品承接和事实来源。

## 工具流程

1. 用 `maintain_copy_artifact(action="read")` 查看已有 candidates。
2. 用 `upsert_many`、`delete_many` 维护候选文案。
3. 需要检查质量时调用 `reflect_on_copy_quality`，回答后继续更新。
4. 完成后调用 `maintain_copy_artifact(action="validate")`。
5. validate 返回 `valid` 后，下一次工具调用必须是 `maintain_copy_artifact(action="save")`。

## 工程硬门

- 每条 copy 必须有有效 `source_user_factor_id`、`product_id`、`product_binding` 和 `fact_binding`。
- 可见文案不得重复商品名、品牌名或同一商品关键词。
- 具体金额、折扣、库存、倒计时等动态事实不写入可见文案，用定性活动感或价值感承接。
- id 原样保留。
- 输出使用输入语言；中文输入产出中文文案。

## 正反例

正例：

- `学生党平价内服！熬夜脸逆袭`
  - 用户因子、价格感、内服形态和熬夜脸痛点共同构成点击理由。
- `打工人的治愈时刻！自带伪体香的沐浴露`
  - 把沐浴露体验放进下班后的情绪场景，商品体验可见。
- `牙龈敏感必入！刷完超清爽`
  - 痛点前置，使用后结果直接，适合口腔护理类商品。

反例：

- `品质好更健康`
  - 泛化，缺少用户动机和商品承接点。
- `白金会员专属推荐`
  - 身份标签明显，但购买理由不足。
- `这款商品很适合你`
  - 解释推荐关系，没有形成场景、痛点、体验或购买理由。

## 输出

生成 `CopyGenerationArtifact`。
