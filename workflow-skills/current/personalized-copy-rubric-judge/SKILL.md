---
name: personalized-copy-rubric-judge
description: Use when scoring personalized ecommerce copy candidates against user factors, product facts, and export decisions.
---

# 个性化文案评审

## 目标

根据 `user_factors`、商品上下文和候选文案，评审每个 candidate。评审结果用于 evolution 比较，不用于暗中重写文案。

评审标准以转化有效性为中心：好文案应当在事实边界内制造点击或购买动机。营销感、痛点前置、活动感、价值感、口碑感、场景感和适度功效表达都可以成为优势，只要它们能被用户因子和商品事实承接。

## 输入

- `candidates`：候选文案，包含 `copy_text`、`user_factor_id`、商品身份，以及可用时的 `commercial_angle`、`product_binding`、`fact_binding`。
- `user_factors`：上游用户侧因子。
- `products` 与 `derived_features_by_product`：商品事实和用户-商品关系。

## 五个评分维度

每个维度打 0 到 5 分。证据足够时使用完整分布，让强弱差异在分数上可见。

- `user_factor_grounding`：用户因子和文案是否由输入信号支撑。
- `product_binding`：商品是否自然承接该用户因子。
- `personalized_conversion`：文案是否命中点击/购买动机。
- `commercial_sharpness`：文案是否短、锐利、有记忆点，并通过痛点、场景、体验结果或价值感表达商品。
- `expression_boundary`：表达是否守住事实、线上一致性和隐私边界。

## 工作流程

对每个 candidate：

1. **重建 brief。** 阅读 user factor、商品事实、derived relation 和可见文案。
2. **检查链路。** 看 `user_factor -> product_binding -> fact_binding -> text` 是否连贯。
3. **给五个维度打分。** 每个分数都写简短 diagnostic，并使用 candidate 的输入语言。
4. **计算 `total_score`。** 五个维度相加，得到 0 到 25。
5. **推出 decision。** `total_score >= 21` 且没有任何维度 `<= 2` 为 `admit`；`15-20` 或高分但有维度 `<= 2` 为 `hold`；`< 15` 或任一关键维度为 `0` 为 `reject`。关键维度是 `user_factor_grounding`、`product_binding` 和 `personalized_conversion`。
6. **记录诊断。** 写 `main_strength`、`main_weakness`、`failure_tags`。
7. **记录结果。** 通过 `judge_candidate` 记录，最后调用 `submit_judgments_final`。

如果 `candidates` 为空或 `candidate_count` 为 0，仍然调用 `submit_judgments_final({"judgments":[]})`。

## Failure Tags

- `missing_user_factor`
- `weak_user_factor_grounding`
- `invented_persona`
- `generic_user`
- `weak_conversion_pull`
- `product_invisible`
- `product_mismatch`
- `overclaimed_effect`
- `unstable_numeric_fact`
- `private_trace`
- `not_commercial_copy`
- `awkward_language`
- `duplicate_angle`
- `repeated_product_name`

## 工程硬门

- 分数评估“绑定到 user factor 和商品事实的可见文案”。
- diagnostic 使用 candidate 的输入语言。
- decision 只按本 skill 的总分与关键维度规则推出。
- 可见文案重复商品名、品牌名或同一商品关键词时，降低 `commercial_sharpness`，并添加 `repeated_product_name`。
- 最后一次工具调用必须是 `submit_judgments_final`。

## 输出

生成 `PersonalizedCopyRubricArtifact`。
