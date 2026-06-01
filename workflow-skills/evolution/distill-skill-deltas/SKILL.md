---
name: distill-skill-deltas
description: Use when distilling one request trajectory into evidence-backed skill delta proposals for the portfolio trial loop.
---

# Skill Delta 蒸馏

## 目标

读取一个完整 request trajectory：payload、factor artifact、copy artifact、rubric judgment、工具调用序列和 token cost。输出一组可试验的 skill delta，交给后续 portfolio trial loop 临时应用、运行对比、再由真实结果决定是否保留。

这个 skill 不直接改生产 skill。它只把一次轨迹中的成功或失败，蒸馏成可复用、可验证、足够小的机制变更提案。

## 核心定义

把一个 production skill 看成某种机制和方法论的抽象。它不是一段普通文本，而是一族复杂函数：

```text
Skill = {f_signal, f_factor, f_copy, f_judge, f_tool, f_finish, ...}
```

每个子函数负责一种可复用行为，例如：

- 如何读信号。
- 如何从行为推导用户痛点。
- 如何压缩 factor artifact。
- 如何把 factor 转成文案。
- 如何评审文案。
- 如何调用 validate/save/finalize 工具。

**delta** 是对这族函数中某个子函数的最小结构变更：

- `add`：增加一个当前 skill 缺少的子函数。
- `modify`：修改一个已有子函数的输入、判断、输出或执行顺序。
- `delete`：删除一个会稳定制造错误、重复或干扰的子函数。

delta 不是文本润色，不是一次候选文案修补，也不是把整份 skill 重写。它必须能在同类 trajectory 中再次触发，并能由 trial loop 单独检验。

## 输入证据

trajectory 是唯一证据来源。当前输入 payload 只包含这些结构化上下文：

- `request_id`：当前被蒸馏的 request 标识。
- `personalized_user_mining`：用户因子挖掘 artifact，包含 user factors、信号依据、需求/痛点、场景触发、购买启发和 evidence refs。
- `personalized_copy_generation`：copy 生成 artifact，包含候选 copy、对应 factor、商品承接、事实承接和商业角度。
- `personalized_copy_rubric`：rubric artifact，包含每条 copy 的分项评分、总分、admit/hold/reject 决策、强弱点和失败标签。
- `tool_calls_per_node`：三个 production node 的工具调用记录，用于判断 validate/save/finalize 是否完成，以及工具参数是否结构化。
- `usage_per_node`：三个 production node 的 token/turn usage，用于定位重复推理、无效循环或 artifact 冗余。

当前输入不直接包含原始表格 payload、完整用户画像原文、完整商品列表原文、messages 全文或 private reasoning。若需要引用用户、商品或场景事实，只能引用上述 artifact 和 tool call 中已经结构化保存的字段。

读取时关注：

- 用户信号、商品事实和列表上下文。
- factor 如何建立，是否抓住了可复用转化假设。
- copy 如何从 factor 生成，是否形成点击/购买动机。
- rubric 如何评分，是否暴露了稳定失败类型或成功机制。
- 工具调用是否完成 validate/save/finalize。
- token cost 是否显示出重复推理、冗余 artifact 或无效循环。

引用证据时只使用 neutral `evidence_ref`。不要把原始私有轨迹、用户字段、private reasoning 或 runtime-only labels 抄进 observation/proposed_change。

## 蒸馏流程

1. **重建当前函数族。** 先判断目标 production skill 当前实际包含哪些子函数：信号读取、痛点推导、factor 压缩、copy 生成、评审、工具终止等。

2. **定位轨迹现象。** 从 trajectory 中找成功路径和失败路径。成功路径说明某个子函数值得保留或增强；失败路径说明某个子函数缺失、过弱、过强、顺序错位或产生干扰。

3. **归因到单个子函数。** 每个 delta 只瞄准一个子函数。若一个现象涉及多个机制，拆成多个 delta，让 trial loop 能分辨哪个变化真的有效。

4. **选择 delta 类型。**
   - `add`：轨迹显示某个必要判断完全缺位。
   - `modify`：轨迹显示已有判断方向对，但粒度、顺序、输入或输出不够好。
   - `delete`：轨迹显示某个判断稳定导致重复、泛化、误导或工具卡住。

5. **写 observation。** 用一两句话描述 trajectory 中可复用的现象，并引用 evidence_ref。

6. **写 proposed change。** 描述对子函数的最小变更：触发条件、应读取的输入、应产生的输出、影响的 artifact 或工具调用。

7. **提交 artifact。** 通过 delta 工具记录 observation 和 change，最后走 final submit。

## Delta 粒度

好的 delta 像对子函数签名或函数体的一次小改：

- `add f_behavior_to_painpoint`：在 factor mining 中加入“行为事实 -> 显性需求/潜在诉求 -> 痛点/顾虑”的推导函数。
- `modify f_copy_surface`：把 copy 输出从“重复商品名”改成“痛点/场景/体验结果承接商品价值”。
- `modify f_finish`：在 copy validate 通过后，下一次工具调用必须 save。
- `delete f_identity_label_surface`：移除把会员等级、年龄、身份标签直接写进可见文案的路径。

弱 delta 通常有这些形态：

- 只改某一句候选文案。
- 只说“加强个性化”“更自然”“更精准”。
- 把多个无关机制打包成一个大改动。
- 没有 evidence_ref。
- 目标 skill 路径无法解析。

## 成功路径与失败路径

**成功路径**：factor、copy、rubric 和工具调用形成连贯链路。此时 delta 应提炼可复用机制，例如某种信号交叉验证、某种痛点前置、某种商品承接、某种终止协议。

**失败路径**：链路在某处坍缩。常见失败包括：

- factor 只是信号改名，没有转化假设。
- copy 复述商品名，缺少用户场景或痛点。
- 文案有营销感但商品事实承接不足。
- rubric 放过了泛化文案。
- reflection 后没有继续 validate/save/finalize。
- artifact 字段保存了重复思考，增加 token cost。

失败路径 delta 应指向造成失败的 skill 子函数，而不是指责单次输出。

## target_skill 格式

`target_skill` 必须是允许自动试验的 production skill，且只能从以下两个值中选择：

```text
current/personalized-user-mining/SKILL.md
current/personalized-copy-generation/SKILL.md
```

不要输出 rubric、evolution、portfolio、trial runner 或其他工程代码作为 target。当前 evolution 只优化用户因子挖掘和 copy 生成两类生产 skill。

旧的拆分 generation skills 是归档参考，不是 production target。Evolution skills 本身也不是 production request loop 的目标 skill。

## 工具调用

- 对每个值得记录的观察调用 `record_delta_observation`。
- 对每个 proposed change 调用 `record_delta_change`，使用同一个 canonical `target_skill` 格式。
- 最后调用 `submit_delta_distillation_final`。

submit handler 会校验 `DeltaDistillationArtifact`、evidence、privacy gate 和 target path，然后交给 portfolio writer。live skill 文件不会在本阶段被修改。

## 工程硬门

- 每个 delta 必须有 evidence_ref。
- 每个 delta 只修改、增加或删除一个子函数。
- 每个 delta 必须指向可解析的 production target skill。
- 输出不增加描述模型自我判断的元评价字段。
- observation 和 proposed_change 使用可复用机制语言，不复制私有轨迹文本。
