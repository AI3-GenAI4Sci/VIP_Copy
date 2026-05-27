---
finding_id: F-08-03
status: confirmed
severity: case-analysis observation (non-blocking)
phase: 08
batch_id: 20260527T123110Z
discovered: 2026-05-27T15:35Z
---

# F-08-03: rubric node 的 reasoning_tokens 在 cache miss 时暴涨 5-10x

## 现象

`personalized_copy_rubric` node 的 `completion_tokens_details.reasoning_tokens` 在 6 个抽样 req 上分布:

| req | cached_tokens | reasoning_tokens | 比 stage1 倍数 |
|---|---:|---:|---|
| stage1 | 3,968 | 915 | 1× (基线) |
| stage2-1 (16546825) | 1,152 | **7,199** | 7.9× |
| stage2-2 (366618992) | 11,008 | 471 | 0.5× |
| stage2-3 (294379371) | 3,840 | 447 | 0.5× |
| stage2-4 (294379371 同 user) | 3,968 | 1,330 | 1.5× |
| stage2-5 (568296523) | 1,152 | **8,643** | 9.4× |

`cached_tokens < 2,000` 的两个 case (stage2-1, stage2-5) reasoning_tokens 暴涨 7-9×。其余 cached_tokens >= 3,840 的 reasoning_tokens 都在 ~500-1,330 范围。

## 推断

DeepSeek `prompt_cache_hit_tokens` 取决于 prefix 重合度。rubric node 的 prompt 包含:
- SKILL_BODY (cacheable, 长 prefix)
- factor_discovery artifact (跨 req 不同)
- copy_generation artifact 5 个 candidate (跨 req 不同)

当 candidate 内容 / factor list / artifact 字段顺序与最近的 cache snapshot 偏差大时,cache miss → reasoning model 重新跑全部 reasoning 链 → reasoning_tokens 飙升。

具体可能因素:
- 某些 user(stage2-1, stage2-5)的 factor count = 5 + 5 candidate 但**内容更复杂**(护腰坐垫 vs 香水,产品类目跨度让 SKILL prose 推理不同)
- DeepSeek 端 cache shard 粒度 — 不同 user 落到不同 cache shard

## 影响

1. **Cost 估算修正**:phase-7 STATE.md 那条 "prompt-cache hit rate >99% per node"(基于 deepseek-chat)在 deepseek-v4-pro reasoning model + rubric node 不成立。
2. **Phase-8 budget 复核**:rubric reasoning_tokens 最坏 ~9,000(占单 req total 65%),budget 原估算严重低估。
3. **Latency tail**:reasoning_tokens 高 → 完成时间长 → 整 batch 拖尾(可能解释 req 6/8/9 单 req 接近 20 min)。

## 案例:user_id 16546825 (stage2-1) 完整 token 分布

| node | total | cached | miss | reasoning |
|---|---:|---:|---:|---:|
| factor_discovery | 23,167 | 17,792 | 5,375 | 3,044 |
| copy_generation | 17,581 | 13,696 | 3,885 | 2,597 |
| **personalized_copy_rubric** | **13,759** | **1,152** | **12,607** | **7,199** |
| 单 req total | 54,507 | 32,640 | 21,867 | 12,840 |

rubric 是该 req 唯一 cache miss 严重的 node — copy_generation cache 命中率 78%,factor_discovery 76.7%,但 rubric 只有 8.4%。

## 建议

仅记录,不修补。可能的后续动作(超出 phase 8 范围):
- Phase-9+ 在 rubric SKILL.md 把 `factor / candidate` 摘要前置(让 high-variance 段落落到 prompt 末尾,提升 cache prefix 命中率)
- 或者 batch_summary 加一个 `cache_efficiency` metric 监控

