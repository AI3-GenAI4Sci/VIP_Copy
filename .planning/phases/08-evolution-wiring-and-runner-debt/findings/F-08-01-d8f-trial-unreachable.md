---
finding_id: F-08-01
status: confirmed
severity: blocking-D8-ACC-2
phase: 08
batch_id: 20260527T123110Z
runner_commit: cbb6c5e
discovered: 2026-05-27T15:49Z
abort_signal: SIGTERM (10 reqs done, 0 trials)
---

# F-08-01: D8-F evolution wiring 在真实 batch 中"在场但未触发"

## 现象

Phase-8 plan 08-05 D8-F C4 路径在真实 DeepSeek batch 中验证失败:

| 阶段 | 状态 | 证据 |
|---|---|---|
| Stage 1 distill agent | ✅ 跑通 | `[runner] distill_after_stage1: produced 4 proposals` |
| 4 个 deltas 抽出 | ✅ 落 in-memory | `delta_ids=[d1_slogan_only_copy_format, d2_non_discriminating_rubric, d3_weak_gift_evidence_bridge, d4_missing_item_side_factor_in_copy]` |
| Stage 2 trial 执行 | ❌ **完全没跑** | 10/10 完成 req:`evolution_snapshot.trials = []`, `delta_portfolio_before/after = []`, 无 `trial_workspace/` 目录 |

## Stop 条件触发

按用户预设的"路径 B"停止条件:**累计 10 stage 2 完成 req,trial 始终为零 → 路径不通,SIGTERM 退出**。

实际触发时间:2026-05-27T15:49Z,batch elapsed 3:17:58。Stage 3 未启动。

## 根因(初步定位,待重放确认)

`seers_harness/validation/runner.py:_patch_from_portfolio_row` (L525-538):

```python
def _patch_from_portfolio_row(row, live_skill_root) -> SkillDeltaPatch | None:
    if row.change_type != "modify_skill":
        return None
    live_target = live_skill_root / row.target_skill
    if not live_target.exists():
        return None
    ...
```

trial 调度循环 (`_run_one_request` L634-637):

```python
for index, portfolio_row in enumerate(delta_portfolio):
    patch = _patch_from_portfolio_row(portfolio_row, live_skill_root)
    if patch is None:
        continue   # <-- 4 个 row 全部走这里 silently skip
    ...
```

可能根因(按概率排序):

### 主因(最可能):target_skill 路径不解析

- `LIVE_SKILL_ROOT = workspace/workflow-skills/`(L183)
- `_patch_from_portfolio_row` 期望 `target_skill` 是 LIVE_SKILL_ROOT 之下的 **相对路径**(如 `current/discover-personalization-factors/SKILL.md`)
- 但 `distill-skill-deltas/SKILL.md` 与 `record_delta_change` tool spec 都**没规定 target_skill 格式**:
  - SKILL prose: 0 hits for "target_skill"
  - Tool spec L290-291: `{"type": "string"}` 无 description / pattern / 例子
- LLM 极可能填逻辑名(`discover-personalization-factors`、`copy_generation`),而非 LIVE_SKILL_ROOT-相对路径
- `live_target = workflow-skills/discover-personalization-factors`(缺 `current/` 与 `/SKILL.md`)→ 不存在 → return None

### 次因(可能):change_type 全部走 add_skill

- LLM 看到 enum `["modify_skill", "add_skill"]` 无引导
- 4 个 delta_id 字面意义偏向"改进现有 skill"应是 modify_skill,但 LLM 也可能保守选 add_skill
- `add_skill` 直接 short-circuit return None

### 三因(不太可能但需排除):distill 产出未持久化导致无法验证

- `_distill_after_stage1` 创建的 `RecordingProvider(provider_factory(), [])` 第二个参数是空 list,但**从未传给 `flush_evidence`**
- distill agent 的 messages.jsonl / tool_calls.jsonl / artifact.json 在 disk 上**没有任何记录**
- 这本身是 plan 08-05 的次要 bug:distill trace 无审计 evidence

## 数据规模

- batch_id: 20260527T123110Z
- runner commit: cbb6c5e (= plan 08-08..08-11 已落 + pre-batch fix)
- elapsed at abort: 3:17:58
- stage 1 完成: 1/1, batch_summary VAL-01/02/04 全 pass
- stage 2 完成: 10/20, 全部 trial=0 (req 11 在 SIGTERM 时被 cancel)
- stage 3 未启动

## 已抽样的 stage 2 完成 req(10 个)

| rid | user_id | factor 数 | 单 req total tokens | trials | trial_workspace |
|---|---|---|---|---|---|
| -6833651210813617137 | 16546825 | 5 | 54,507 | 0 | ✗ |
| -6833721702418762089 | 366618992 | 5 | 54,749 | 0 | ✗ |
| -6833791596394007611 | (待抽样) | (待抽样) | (待抽样) | 0 | ✗ |
| -6834003288630524187 | (待抽样) | (待抽样) | (待抽样) | 0 | ✗ |
| -6834284436948759098 | (待抽样) | (待抽样) | (待抽样) | 0 | ✗ |
| -6834355323411419079 | (待抽样) | (待抽样) | (待抽样) | 0 | ✗ |
| -6834635816105165003 | 294379371 | 8 | 56,422 | 0 | ✗ |
| -6834636343439087307 | 294379371 (同) | 5 | 53,717 | 0 | ✗ |
| -6834706508028200887 | 568296523 | 8 | 60,412 | 0 | ✗ |
| -6834635848893206135 | (待抽样) | (待抽样) | (待抽样) | 0 | ✗ |

## 验证下一步

为定位主因 vs 次因,需要看 distill agent **实际产出的 4 个 DeltaProposal 完整 JSON**。两条路径:

A. **重放离线 distill**(成本 ~5-10min reasoning model 调用):
   - 用 `_build_trajectory_payload` 重建 stage 1 输入
   - 直接调 `run_skill_via_tools(skill="distill-skill-deltas", ...)` 拿 result.artifact
   - inspect `change_type` / `target_skill` 字段

B. **next-batch 加 evidence persistence**(plan 08-05 的次要 bug 修):
   - 修 `_distill_after_stage1` 让它 flush distill RecordingProvider 的 request_log 到 stage1 同级 `distill_evidence/` 目录
   - 下次跑 batch 时直接 inspect

A 更快,但要花 reasoning model token。B 是结构修补,但需重跑全 batch。**推荐 A 先**。

## 不修补的现有 trial 数据

10 个 stage 2 req 已落地的 evidence 仍是合法 case-reading 材料 ——
- factor_discovery / copy_generation / personalized_copy_rubric 三 node 全跑通
- VAL-01/02/04 全绿(non-trial 行为)
- M1-M4 行为指标可计算
- 唯一缺的是 M5(delta diversity / belief update)及 trial-based VAL-05 dimension

batch_summary.json 虽未生成(stage 没完成),但 index.json 与 per-req artifacts 完整。这些是 phase-7 case_analysis 的真实材料。

## 阻塞影响

- **D8-ACC-2 (evolution wiring 真闭环) BLOCKED**:必须先修 root-cause 才能再跑 phase-8 final batch
- **D8-ACC-1 (Stage 1+2+3 clean batch) BLOCKED**:依赖 ACC-2
- **08-12 audit BLOCKED**:其前置条件是 phase-8 final batch 跑通(本 batch 算 partial / abort)
- **08-13 closeout BLOCKED**:依赖 08-12

## 解锁路径(候选,需用户决定)

1. **gap-closure plan 08-14**:在 distill SKILL prose + tool spec 给 target_skill 加格式说明 + repro 实际 LLM 产出
2. **代码修补**:`_patch_from_portfolio_row` 加 fuzzy 路径解析(在 LIVE_SKILL_ROOT 下递归搜 `target_skill` 名)— 这是 surface fix,违反 .continue-here.md 反 surface-patching 约束,**不推荐**
3. **重新跑 distill** — 如已知 LLM 保守选 add_skill,改 SKILL prose 引导 modify_skill 偏好

## 结论

D8-F 接线在 plan 08-05 落地时 **结构正确但 contract 缺失**:portfolio 的 `target_skill` 字段没有跨 distill SKILL / tool spec / patch helper 三处的格式合约。pytest 单测靠 mock portfolio (手填正确路径) 跑过,真实 LLM 在零格式引导下没填对路径。这是 phase-7 0526 batch 之后又一例"smoke-test green / real-LLM red"的具体案例,完美印证 .continue-here.md 那条 blocking anti-pattern。

