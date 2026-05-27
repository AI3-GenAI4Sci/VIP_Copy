---
finding_id: F-08-02
status: confirmed
severity: case-analysis observation (non-blocking)
phase: 08
batch_id: 20260527T123110Z
discovered: 2026-05-27T15:30Z
---

# F-08-02: factor 数量在 5 / 8 双峰分布

## 现象

11 个完成 req(1 stage1 + 10 stage2)的 factor_count 分布:

| factor_count | 频次 |
|---|---|
| 5 | 7 个 |
| 8 | 4 个 |
| 其他 (3/4/6/7/9/10+) | 0 |

`FactorDiscoveryArtifact.factors` schema **没设 min/max 约束**(`seers_harness/domain/models.py`)。pydantic field 只是 `list[PersonalizationFactor] = Field(default_factory=list)`,任意长度合法。

## 推断

5/8 二极分化是 **SKILL prose 引导的 emergent behavior**,不是 schema 锁的。可能机制:

- SKILL 反思工具 (`reflect_completion`) 询问 LLM "do you have at least N? do you have unmined signals?"
- LLM 第一轮挖 5 个达到"完成基线",第二轮反思后或继续挖到 8 个(再次反思",或在 5 处停
- 5 vs 8 反映两种内部"够了"判断模式

## 影响

- M2 `factor_diversity_score` 在 5-factor batch 与 8-factor batch 上不可比较 — diversity score 跟 count 强相关
- 当前 stage 1 batch_summary 的 M2=0.114 是 n=1 单点,无统计意义
- 待 batch 完成后看 stage 2 (n=20) 的 M2 分布是否仍二极化

## 案例:同 user 跨 stage 不同表现

`user_id = 294379371` 出现 3 次:

| 出现 | factor 数 | 同 SKILL,同 user,不同输出 |
|---|---|---|
| stage 1 | 8 | reasoning_tokens=132 |
| stage 2 第 1 次 | 8 | reasoning_tokens=2,658 (×20) |
| stage 2 第 4 次 | 5 | reasoning_tokens=1,326 |

> **暗示**:reasoning model 输出受 prompt cache 命中率影响 — cache miss 时 reasoning 更深可能挖更多 factor;但本案例 cached_tokens 都 16k+,反例。可能因 candidate / scenario_id 微差 让 LLM 内部分支 divergent。

## 建议

仅记录,不修补。Phase-7 case_analysis.md 应在 F1 dimension(factor_count 与 user complexity 相关性)用此数据点。

