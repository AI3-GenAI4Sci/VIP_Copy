---
name: distill-skill-deltas
description: Use when lazily distilling an accumulated bundle of production request trajectories into evidence-backed skill delta proposals for the portfolio trial loop.
---

# Skill Delta 蒸馏

## 目标

从同一 `pipeline_id` 下累积的一组 production trajectories 中，提炼可以进入 portfolio trial scheduler 的 skill delta。每条 trajectory 已经完成生产链路，并包含用户因子、文案候选、rubric judgment、JSON-mode 完成证据、工具调用记录和 token usage。

这个节点的工作是把多条轨迹里的稳定机制现象转成小而可试验的 skill 变更。delta 产出只表示进入 eligible pool；后续由 scheduler 根据 trial budget、并发度、pressure 和 delta 后验选择有限线路做 trial。未被选中的 delta 会留在 pool 中等待后续预算。

## 机制视角

把 production skill 看成一组可复用子函数：

```text
Skill = {f_signal, f_factor, f_copy, f_judge, f_json, f_finish}
```

delta 是对子函数的一次最小结构变更：

- `add`：补入当前 skill 缺少、且多条轨迹共同需要的判断。
- `modify`：调整已有判断的输入、顺序、粒度或输出格式。
- `delete`：移除稳定制造泛化、重复、误导或 JSON 边界破坏的判断。

好的 delta 能被同类 request 再次触发，并能通过 trial 结果单独验证。它的证据来自轨迹，而不是来自对单条文案的临时修补。

## 输入证据

`trajectory bundle` 是唯一证据来源，核心字段包括：

- `request_id`：当前 bundle id。
- `pipeline_id`：证据所属 pipeline，例如 `production`、`trial:D_001`。
- `trajectory_count`：bundle 内轨迹数。
- `trajectories`：轨迹数组。
- `rubric_decision_bucket`：每条轨迹的 rubric 决策桶，优先级为 `reject` 高于 `hold`。
- `personalized_user_mining`：用户因子 artifact。
- `personalized_copy_generation`：文案生成 artifact。
- `personalized_copy_rubric`：rubric artifact。
- `tool_calls_per_node`：各 production node 的工具调用记录。
- `usage_per_node`：各 production node 的 token/turn usage。

读取顺序以 `reject` 轨迹为主，其次读取 `hold` 轨迹。`reject` 常暴露硬门失败、事实承接断裂、结构输出破坏；`hold` 常暴露方向存在但强度不足的问题，例如动机弱、商品价值弱、场景弱、表达模板化。`admit` 样本只作为对照，不作为主要触发源。

证据引用使用中性 `evidence_refs`。当原始证据是数组或对象时，`value` 写成字符串摘要，例如 `"weak_product_value, weak_scene_texture, ..."` 或 `"防晒霜/乳, 牙膏/牙粉, ..."`。

## 蒸馏流程

1. 先看 bundle 是否形成稳定模式。若轨迹只是偶发现象、样本之间没有共同机制，最终提交空 `deltas`。
2. 从 `reject` 到 `hold` 聚合失败类型、低分轴、商品承接路径、用户因子路径和 JSON 完成证据。
3. 把现象归因到一个 production skill 子函数，例如信号读取、痛点推导、商品承接、短文案表面、rubric 约束或 JSON 终止。
4. 为每个稳定现象选择 `add`、`modify` 或 `delete`，并写出能被精确应用到结构化 skill 源的 `patch.edits`。`path` 使用 JSON Pointer；修改已有章节正文时按 heading 寻址，例如 `/sections/by_heading/方法/body`。追加新章节用 `/sections/-`。不要使用 `/sections/4/body` 这类数字下标，因为 skill 被手工调整或并发进化后 section 顺序会漂移。
5. 对有必要沉淀的 delta 调用 `record_delta_change`；证据不足时不调用工具。
6. 完成记录后停止工具调用。harness 会根据已记录的 `delta_changes` 确定性组装 `DeltaDistillationArtifact`；没有 change 时得到空 `deltas`。

## 并行边界

distill 触发按 `pipeline_id` 独立累计。不同 pipeline 的触发计数互不混用；`production`、`trial:D_001`、`trial:D_002` 各自拥有独立的轨迹阈值和 bundle，避免不同 skill surface 的现象互相污染。

delta 的 portfolio 状态和后验分布按 `delta_id` 共享。同一个 delta 被多条并行线路抽中时，多条结果共同更新 `belief_alpha`、`belief_beta`、sample/success/failure counters 和 lifecycle status。并行提供更多观测，不复制后验。

## target_skill

`target_skill` 只能指向 production request loop 中允许试验的 skill：

```text
current/personalized-user-mining/SKILL.md
current/personalized-copy-generation/SKILL.md
```

## 可用工具

本节点使用一个 delta 记录工具：

- `record_delta_change`

`record_delta_change` 只在存在稳定机制现象时调用。证据不足时，不调用工具并结束；harness 会确定性提交空 `deltas`。存在 delta 时，为每条 delta 记录一次 change 后结束；harness 会把所有 `record_delta_change` 结果组装为最终 artifact。

## 工具参数形状

所有工具参数都是严格 JSON object，只包含下列形状中的字段。

`record_delta_change`：

```json
{
  "delta_id": "D_001",
  "target_skill": "current/personalized-copy-generation/SKILL.md",
  "function_id": "modify_f_copy_surface",
  "operation": "modify",
  "observation": "多条轨迹共同暴露的机制现象",
  "change_summary": "本次机制变更的人读摘要",
  "patch": {
    "edits": [
      {
        "op": "replace",
        "path": "/sections/by_heading/方法/body",
        "value": "替换后的完整章节正文，保留 Markdown 列表、代码块和必要空行；..."
      }
    ]
  },
  "evidence_refs": [
    {
      "path": "trajectories.0.personalized_copy_rubric.judgments.0.failure_tags",
      "value": "weak_product_value, weak_scene_texture, ..."
    },
    {
      "path": "trajectories.1.personalized_copy_generation.candidates.0.product_binding",
      "value": "商品承接只停留在类目层，缺少差异化属性"
    }
  ],
  "applicable_surface": ["personalized-copy-generation"],
  "failure_types": ["weak_product_value", "weak_scene_texture"]
}
```

最终 artifact 由 harness 确定性生成，模型不要调用 final submit 工具。生成逻辑等价于：

```json
{
  "request_id": "当前 bundle id",
  "scenario_id": "当前 bundle id",
  "deltas": ["所有 record_delta_change 的参数对象；没有 change 时为空数组"]
}
```

`evidence_refs[].path` 是字符串。`evidence_refs[].value` 只能是字符串、数字、布尔值或 null；数组和对象证据压缩成字符串摘要。

## 输出

生成 `DeltaDistillationArtifact`。
