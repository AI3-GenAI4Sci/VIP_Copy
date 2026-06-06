# VIP COPY

VIP COPY 是一个面向电商推荐文案实验的生产级 harness。它把一次 `request_id`
曝光请求中的合规商品整体打包处理，经过用户个性化挖掘、文案生成、rubric 打分、
确定性校验、离线落表和 skill 进化链路，形成可审计、可断点续传、可逐步进化的实验系统。

核心原则：

- 一个 `request_id` 就是一次曝光请求，也是请求级金标准 key。
- 同一个请求里的多个合规商品属于同一个用户和同一次曝光上下文，必须一起进生产链路。
- 生产节点只使用 JSON mode，不调用工具。
- 进化节点只在懒触发时使用 delta 记录工具，patch 校验、试跑、posterior 更新和 promotion 都由 harness 确定性完成。
- 每次 runner 拥有独立产物目录，除非显式指定 `--state-dir`，否则不会借用旧实验产物。

## 系统流程

```text
CSV request/list_group
  -> personalized-user-mining
  -> personalized-copy-generation
  -> personalized-copy-rubric-judge
  -> 确定性校验与证据导出
  -> offline_copy_table 落表
  -> 懒触发 skill delta distillation
  -> 生产流量 holdout trial
  -> delta posterior 更新与 promotion
```

生产 DAG 包含三个节点：

1. `personalized-user-mining`：从用户历史、行为和上下文中挖掘稳定个性化因子。
2. `personalized-copy-generation`：把用户因子、商品事实和 request 列表语境转成候选文案。
3. `personalized-copy-rubric-judge`：只输出结构化评分，harness 根据分数和确定性校验决定是否 admit/hold/reject。

最终业务落表是离线文案表，而不是审计表：

```text
request_id,user_id,item_id,copy
```

审计信息、评分、证据、轨迹和进化状态保存在 `index.json`、`batch_summary.json`、
`evidence/`、`portfolio.jsonl` 和 `portfolio_journal.jsonl` 中，不混入最终离线表。

## 快速开始

默认跑一个小批量：

```bash
vip-copy \
  --env-file .env.local
```

指定 15 条 request、3 并发、DeepSeek 超时 300 秒：

```bash
vip-copy \
  --env-file .env.local \
  --out-dir .runs/demo_15x3 \
  --num-requests 15 \
  --concurrency 3 \
  --timeout 300 \
  --call-deadline 300 \
  --max-inflight-calls 3
```

断点续传：

```bash
vip-copy \
  --env-file .env.local \
  --out-dir .runs/demo_15x3 \
  --resume
```

没有安装 console script 时，也可以使用模块方式：

```bash
.venv/bin/python -m seers_harness.validation.runner --env-file .env.local
```

如果不传 `--resume`，runner 会拒绝写入非空 `--out-dir`，防止新实验误借用旧请求产物。

## 产物结构

每次运行拥有一个独立目录：

```text
.runs/<run_id>/
├── run_manifest.json
├── completed_records.jsonl
├── index.json
├── batch_summary.json
├── failed_requests.json
├── offline_copy_table.csv
├── offline_copy_table.jsonl
├── portfolio.jsonl
├── portfolio_journal.jsonl
├── _evolution_distill/
├── _trial_skill_workspaces/
└── <request_id 或 trial_execution_id>/
    ├── _artifacts/
    ├── evidence/
    ├── request_factor_copy_index.json
    └── evolution_snapshot.json
```

关键文件：

- `offline_copy_table.csv` / `offline_copy_table.jsonl`：最终离线落表，只包含
  `request_id,user_id,item_id,copy`。
- `run_manifest.json`：记录本次运行的 request 列表、并发、provider 压力参数、进化策略、resume 状态和输出契约。
- `completed_records.jsonl`：运行中追加写入，成功收尾时重写为最终记录；`--resume` 用它跳过已完成 slot。
- `index.json`：请求级索引。trial 行会同时记录 holdout `request_id` 和被替换的 `original_request_id`。
- `batch_summary.json`：批量结果摘要、失败统计、进化状态和极端样本入口。
- `failed_requests.json`：最终未恢复失败请求及失败原因，用于后续重跑。
- `portfolio.jsonl`：本次运行结束时的 delta portfolio 快照。
- `portfolio_journal.jsonl`：本次运行新增的 posterior 更新 journal。

## 持久进化状态

默认情况下：

```text
state_dir == out_dir
```

这意味着每次实验天然隔离，不会自动借用旧 portfolio 或旧 journal。

如果你希望跨 runner 保留已经验证有效的进化结果，显式指定 `--state-dir`：

```bash
vip-copy \
  --env-file .env.local \
  --out-dir .runs/batch_001 \
  --state-dir .runs/evolution_state
```

持久状态目录包含：

```text
.runs/evolution_state/
├── portfolio.jsonl
└── portfolio_journal.jsonl
```

即便使用共享 `state_dir`，每个 run 仍会写自己的本地 `portfolio.jsonl` 快照和
`portfolio_journal.jsonl` 切片，方便事后分析“这一次 run 结束时到底使用了什么状态”。

promotion 只在 delta 状态机判定 ready 且满足 `VIP_COPY_PROMOTION_MIN_READY` 后触发。
触发后会修改 `workflow-skills/current/`，并把旧 skill 内容和 promotion manifest 写入运行时归档目录。

## 进化机制

进化是懒触发、管线内统计、生产流量小比例探索。

- scheduler 按 `pipeline_id` 累积成功轨迹。
- 主要分析成功轨迹里的 `reject`，其次使用 `hold`，`admit` 更多作为对照。
- 达到阈值后才调用 evolution skill 做一次 delta distillation。
- delta 使用结构化 JSON edit 描述 `add/delete/modify`。
- harness 对 delta 做 patchability 校验，只有能确定性应用到 live skill 的 delta 才进入 portfolio。
- trial selection 会用历史 holdout request 替换少量生产 slot，并在临时 skill root 中应用 delta。
- posterior 由 canonical delta id 共享维护；并行 slot 即使选中同一个 delta，也共同更新同一个后验分布。

当前 canonical delta id 由 `target_skill`、`function_id`、`operation` 和 `patch` 内容寻址，
避免模型输出的局部 id 互相冲突。

## 超参数

常用参数：

| 参数 | 默认值 | 设置方式 | 含义 |
|---|---:|---|---|
| request 数 | `15` | `--num-requests` 或多个 `--request-id` | 本次运行的生产 slot 数 |
| 并发 | `3` | `--concurrency` | 并行生产管线数 |
| 节点重试 | `3` | `--node-max-attempts` 或 `VIP_COPY_NODE_MAX_ATTEMPTS` | 每个 DAG 节点的 JSON 输出重试预算 |
| provider 超时 | `300s` | `--timeout` 或 `DEEPSEEK_TIMEOUT_SECONDS` | SDK/read timeout |
| 流式 deadline | `300s` | `--call-deadline` 或 `DEEPSEEK_CALL_DEADLINE_SECONDS` | 单次流式调用墙钟 deadline |
| 最大 inflight call | `20` | `--max-inflight-calls` 或 `DEEPSEEK_MAX_INFLIGHT_CALLS` | 全局 provider API semaphore |
| trial 比例 | `0.02` | `--trial-budget-fraction` 或 `VIP_COPY_TRIAL_BUDGET_FRACTION` | 每个 wave 允许分给 delta trial 的比例 |
| distill 阈值覆盖 | 派生 | `--distill-min-trajectories` 或 `VIP_COPY_DISTILL_MIN_TRAJECTORIES` | 固定懒触发阈值 |
| promotion 最小数 | `3` | `VIP_COPY_PROMOTION_MIN_READY` | 至少多少个 ready delta 才允许 promotion |

进化预算高级环境变量：

| 环境变量 | 默认值 | 含义 |
|---|---:|---|
| `VIP_COPY_EVOLUTION_MIN_DISTILL_ELIGIBLE` | `5` | 单管线至少累积多少条 eligible 轨迹才允许 distill |
| `VIP_COPY_EVOLUTION_TARGET_DISTILL_CALLS` | `5` | 单 batch 目标 distill 调用预算 |
| `VIP_COPY_EVOLUTION_MAX_TRIAL_SLOTS` | 未设置 | 单 wave delta trial slot 硬上限 |
| `VIP_COPY_TRIAL_RNG_SEED` | 未设置 | 固定 trial 随机采样种子，便于复现实验 |

旧版 `SEERS_*` 环境变量仍作为兼容 fallback 被识别，但新配置建议统一使用
`VIP_COPY_*`。

当前 DeepSeek 默认推理强度是 `xhigh`。

## 失败与恢复

运行中：

- 节点 JSON 输出失败会在节点内最多重试 3 次。
- request 级业务输出失败会记录并跳过，不阻塞整个生产任务。
- 主批次结束后，失败 request 会再重跑最多 3 次。
- 最终仍失败的 request 会写入 `failed_requests.json`，包含失败原因和可重跑上下文。

中断后：

1. 保留同一个 `--out-dir`。
2. 重新运行并加 `--resume`。
3. runner 从 `completed_records.jsonl` 识别已完成 slot。
4. 未完成 slot 按原 request 顺序继续运行。

如果某个 trial 用 holdout request 替换了生产 slot `R4`，记录中的
`original_request_id=R4` 会标记 `R4` 这个生产 slot 已完成。

## 验证

发布包不携带开发测试目录。最小发布态 smoke：

```bash
python -m seers_harness.validation.runner --help
python -c "import seers_harness, seers_harness.validation.runner as r; print(r.DEFAULT_BATCH_REQUESTS)"
```

真实外发验证建议从小批量开始，例如 15 request、3 并发，通过后再逐步扩大到
50 并发 canary 和百万 request 压测。当前版本已经完成小批量真实外发、50 request
/ 10 并发真实批量和全量单测验证，可以进入大规模离线压测与灰度实验阶段。

最近已验证的工程面：

- request 级多商品打包。
- user-mining 缓存复用。
- JSON-mode 生产节点重试。
- DeepSeek flash / xhigh / 300s timeout 路径。
- 懒触发 distillation。
- content-addressed delta id。
- current-batch holdout trial。
- posterior journal 更新。
- trial skill workspace 隔离。
- `SKILL.md` 与 `SKILL.json` 同步后的结构化编辑路径。
- run-local portfolio 快照。
- `completed_records.jsonl` 断点续传。
- `offline_copy_table.csv/jsonl` 四列离线落表。
- terminal dashboard 进度条、并发运行态、trial 计数和失败计数。

仍未完全生产认证的面：

- 百万 request 长时间压力。
- 50 并发外部 provider 限流与恢复。
- 人工校准后的 rubric 稳定性。
- 长周期 promotion rollback 演练。

## 大规模压测建议

建议按以下节奏上线压测：

```bash
# 1. 小规模真实链路
vip-copy --env-file .env.local --out-dir .runs/canary_15x3 --num-requests 15 --concurrency 3

# 2. 常用子集
vip-copy --env-file .env.local --out-dir .runs/canary_50x10 --num-requests 50 --concurrency 10

# 3. 高并发 canary
vip-copy --env-file .env.local --out-dir .runs/canary_500x50 --num-requests 500 --concurrency 50 --max-inflight-calls 50

# 4. 百万级离线压测
vip-copy --env-file .env.local --out-dir .runs/million_001 --num-requests 1000000 --concurrency 50 --max-inflight-calls 50
```

生产压测时建议单独设置共享进化状态目录：

```bash
vip-copy \
  --env-file .env.local \
  --out-dir .runs/million_001 \
  --state-dir .runs/vip_copy_evolution_state \
  --num-requests 1000000 \
  --concurrency 50 \
  --max-inflight-calls 50
```

这样每次 runner 的证据目录仍然隔离，而已经被 trial 验证的 delta posterior 可以跨 run
持续积累。

## 代码结构

```text
workspace/
├── seers_harness/
│   ├── agentic/
│   ├── evolution/
│   ├── intake/
│   ├── provider_runtime/
│   ├── validation/
│   └── workflow/
├── workflow-skills/
│   ├── current/
│   └── evolution/
└── pyproject.toml
```

## 工程约束

- 保持一条生产路径，不恢复旧 staged validation 或兼容包装。
- 生产节点保持 JSON-only，进化节点保持 tool-only。
- 除非现有 JSON edit 无法表达必要操作，不新增 LLM-facing delta 工具。
- `out_dir` 是一次运行的证据目录，完成后应视为不可变。
- `state_dir` 只用于有意保留跨 run 进化记忆。
- 解析、校验、patch、promotion、产物写入尽量由 deterministic harness 完成。
