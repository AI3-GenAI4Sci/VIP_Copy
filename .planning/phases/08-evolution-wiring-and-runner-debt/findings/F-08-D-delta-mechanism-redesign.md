# F-08-D: Delta 演化机制重设计 (Agent D)

> 状态：草稿骨架 → 增量填充中
> 目的：把 06-02 的孤儿函数接到生产路径上，并补齐 8 个 critical gap，使 delta 演化成为"真机制"而非"假阳性闭环"。

---

## 1. Executive summary

**诊断**：06-02 已经把 bandit / trial isolation / sedimentation 的所有纯函数原语写好并跑通单测，但 08-05 把它们 wire 错了——production 路径上的 trial loop 是「对 portfolio 每一行确定性跑一次」（plan 08-05 truth #3 字面要求如此），完全绕过 `select_trial_delta`；同一处 `_patch_from_portfolio_row` 因 `target_skill` 字段没有跨 (distill SKILL prose) ↔ (record_delta_change tool spec) ↔ (patch helper) 三处的格式合约，真实 LLM 在零格式引导下 100% 填错路径，4 条 delta 全部被静默 skip（F-08-01）。08-06/07 后续添加的 `token_cost_observed` 与 behavioral metrics 仅观察 trial 内部状态，未流回 portfolio。trajectory buffer / sedimentation / distill artifact 持久化 / delta status 状态机 全部为孤儿。

**修复形状**：把现有原语接入 production 真路径，并补三块缺失件——
- (A) **call-site 替换**：`_run_one_request` 的 deterministic loop → 单次 `select_trial_delta` 调用；信号源接 production rolling window。
- (B) **target_skill 三处格式合约**：SKILL prose 给规则与例子；tool spec 加 `pattern` 与 `description`；`_patch_from_portfolio_row` 同时接受规范路径与逻辑名（fuzzy 收敛后归一化）。
- (C) **trajectory buffer + 异步 sedimentation**：每个完成的 request 写一条 `TrajectoryRecord`；buffer size 触发或时间窗到期触发 distill；distill 跑成功路径 + 失败路径双 prompt。
- (D) **post-trial uplift evaluator 与文案打分解耦**：paired control（同 scenario 跑一次 baseline、一次 trial），uplift 用「成功率差 + token 成本差 + behavioral metric 差」三轴，rubric 打分本身只作为 success 判据之一不参与 uplift 公式。
- (E) **portfolio 并发**：journal-then-fold——每个 request 写自己的 trial outcome 到 per-request append-only 行；scenario 末尾或 batch 末尾单线程 fold。
- (F) **delta status 状态机**：基于 (sample_count, posterior_lcb, token_cost_p95, failure_pattern_repetition) 四量做硬阈值 + soft 阈值组合判定。

**LOC 估计**：生产 ~580 LOC，测试 ~380 LOC，跨 6 个独立 plan（09-01..09-06）。第一个 ship-able plan（09-01 target_skill 合约）~80 LOC，可独立解锁 F-08-01 让 batch 跑通；其余 5 个 plan 沿 trajectory buffer → uplift evaluator → bandit call-site → status 机 → concurrency 顺序串行依赖。

---

## 2. Orphan map

| 函数 / 类型 | 位置 | 单测 | 生产调用现状 |
|---|---|---|---|
| `belief_mean(row)` | `evolution/delta_portfolio.py:181` | `tests/evolution/test_delta_portfolio.py`（06-02-T01）| **死代码**：仅 `select_trial_delta` 内部用；外部无调用。 |
| `update_after_trial(row, success, token_cost_delta)` | 同上 L193 | 同上 | **死代码**：runner 里的 trial loop 调过一次（08-05 wire 时引入），但因 `_patch_from_portfolio_row` 静默 skip 永不执行到。 |
| `select_trial_delta(...)` | 同上 L228 | 同上 | **完全 orphan**：runner 用了 deterministic loop 没调。 |
| `buffer_trajectory(buffer, rec)` | 同上 L358 | 06-02-T03 单测 | **完全 orphan**：runner 没在任何地方累积 buffer。 |
| `sediment_trajectories(buffer, max_rows)` | 同上 L453 | 同上 | **完全 orphan**：从未被触发。 |
| `trajectory_signature(rec)` | 同上 L336 | 同上 | **完全 orphan**：仅 `sediment_trajectories` 内部用。 |
| `assemble_portfolio(existing, new_proposals, *, events)` | 同上 L395 | 07-01 单测 | **半 orphan**：runner 在 stage 1 distill 成功时调过；但因 distill 自己未持久化 artifact，调用链可观测性为零。 |
| `SkillDeltaPatch` / `apply_delta_patch_temporarily` | `evolution/trial_runner.py` | 06-02-T02 单测 | **代码到达，但运行时永不执行**——`_patch_from_portfolio_row` 因 target_skill 路径不存在 100% 返回 None。 |
| `run_request_trial(...)` | 同上 | 06-02-T02 单测 | 同上。 |
| `DeltaStatus = experimental \| held \| rejected \| ready_for_review` | `delta_portfolio.py:44` | 仅类型校验 | **状态机不存在**：没有任何代码把 `experimental` 推进到其它状态。所有 row 永远停在 `experimental`。 |
| `DeltaDistillationArtifact` | 同上 L123 | submit-tool 单测 | distill 跑通后 artifact 留在 in-memory `_distill_after_stage1` 局部变量，**不落盘**（F-08-01 三因里点出的次 bug）。 |

**缺失生产调用站点（必须新建）**：
1. `_run_one_request` 末尾：append `TrajectoryRecord` 到共享 buffer。
2. scenario / batch 边界：触发 `sediment_trajectories` → 异步 distill agent → `assemble_portfolio`。
3. `_run_one_request` 中段：把 deterministic loop 换成 `select_trial_delta(...)` 单次调用（核心修复）。
4. trial 完成后：`update_after_trial` 通过 journal 写盘，单线程 fold 进 portfolio。
5. fold 之后：跑 status transition 函数（新增）决定 `experimental → held / rejected / ready_for_review`。
6. distill agent 落盘 distill_evidence/<batch_id>/<request_id>/{messages,tool_calls,artifact}.json，否则永远无法离线重放。

---

## 3. End-to-end flow diagram

```
            ┌─────────────────────────────────────────────────────────────────┐
            │                    SEERS request loop (c=20)                    │
            └───────────────────────────────┬─────────────────────────────────┘
                                            │
                                  ┌─────────▼─────────┐
                                  │ _run_one_request  │
                                  └─────────┬─────────┘
                                            │
                       (1) 计算 applicable_surface / inflight
                                            │
                  ┌─────────────────────────▼─────────────────────────┐
                  │  ProductionSignalWindow (rolling 50 baseline)     │
                  │  → recent_failure_rate / token_pressure /          │
                  │     production_pressure                            │
                  └─────────────────────────┬─────────────────────────┘
                                            │
                                (2) select_trial_delta(...)
                                            │
                       ┌────────────────────┴─────────────────────┐
                       │                                          │
                  (3a) None                                  (3b) delta_id
                       │                                          │
              run baseline only                       (4) run baseline + run trial
                       │                                  (paired control)
                       │                                          │
                       │                              (5) compute_uplift(baseline, trial)
                       │                                          │
                       │                              (6) append portfolio_journal.jsonl
                       │                                          │
                       └───────────────┬──────────────────────────┘
                                       │
                       (7) 写 TrajectoryRecord 到 trajectory_buffer
                                       │
                       (8) record_baseline_outcome 到 ProductionSignalWindow
                                       │
                                  ┌────▼────┐
                                  │ buffer  │
                                  └────┬────┘
                                       │
                       (9) SedimentationOrchestrator.should_fire?
                                       │
                  ┌────────────────────┴───────────────────┐
                  │ no (主线继续)                            │ yes
                  │                                        │
                  ▼                                  (10) D-13 main pause:
            下个 request                              产品 trial_prob = 0 in window
                                                            │
                                          (11) sediment_trajectories → 子集
                                                            │
                                          (12) dual-track distill:
                                              success_patterns + failure_patterns
                                                            │
                                          (13) persist_distill_evidence(...) 落盘
                                                            │
                                          (14) assemble_portfolio(existing, new)
                                                            │
                                          (15) fold_portfolio_journal(journal, portfolio)
                                                            │
                                          (16) apply_status_transitions(portfolio, journal)
                                                            │
                                          (17) write_portfolio_jsonl(snapshot)
                                                            │
                                          (18) main pause clear → 恢复 trial
```

每条转移已编号 (1)–(18)。关键 fork：(3a)/(3b) 是 trial gate；(9) 是 sedimentation gate；(10)+(18) 是 D-13 同步暂停的 enter/exit。

---

## 4. 八个 Gap 的设计

### Gap 5 — `target_skill` 格式合约

**问题陈述**：
F-08-01 已确认这是 batch 0 trial 的根因。`target_skill` 字段在三处都没有规约：
1. `distill-skill-deltas/SKILL.md` prose：0 hits for "target_skill"。
2. `RECORD_DELTA_CHANGE_SPEC` (`evolution_tools.py:290`)：`{"type": "string"}`，无 description / pattern / 例子。
3. `_patch_from_portfolio_row`：硬要求是 `LIVE_SKILL_ROOT` 之下的相对路径（`current/<dir>/SKILL.md`）。

LLM 在零格式引导下必然填逻辑名（`discover-personalization-factors`、`copy_generation`），三层全部错位。

**设计 — 三处合约统一**：

**A. SKILL prose 规则（distill-skill-deltas/SKILL.md）**：

新增段落，明确两种合法形态：
- **规范路径**（推荐）：`current/<skill-dir>/SKILL.md`（必须以 `current/` 开头、以 `/SKILL.md` 结尾）。
- **逻辑名**（fallback）：`<skill-dir>` 或 `<skill-dir>.md`，会被运行时解析为 `current/<skill-dir>/SKILL.md`。

附 3 个完整 example proposal payload 演示。

**B. tool spec 加 pattern + description**（`RECORD_DELTA_CHANGE_SPEC.target_skill`）：

```python
"target_skill": {
    "type": "string",
    "description": (
        "Path to the live skill, relative to workflow-skills/. "
        "Preferred: 'current/<skill-dir>/SKILL.md'. "
        "Logical name '<skill-dir>' is also accepted; "
        "runtime normalizes to 'current/<skill-dir>/SKILL.md'."
    ),
    "pattern": r"^(current/[a-z0-9_-]+/SKILL\.md|[a-z0-9_-]+(\.md)?)$",
}
```

**C. `_patch_from_portfolio_row` 路径归一化（runtime gate）**：

```python
def _normalize_target_skill(target: str) -> str:
    """Resolve logical name to canonical 'current/<dir>/SKILL.md' form."""
    target = target.strip()
    if target.startswith("current/") and target.endswith("/SKILL.md"):
        return target
    # strip optional trailing .md
    base = target[:-3] if target.endswith(".md") else target
    return f"current/{base}/SKILL.md"

def _patch_from_portfolio_row_v2(
    row: DeltaPortfolioRow, live_skill_root: Path
) -> SkillDeltaPatch | None:
    if row.change_type != "modify_skill":
        return None
    canonical = _normalize_target_skill(row.target_skill)
    live_target = live_skill_root / canonical
    if not live_target.exists():
        # 显式 log,不再 silent
        log.warning(
            "delta_patch.unresolved",
            extra={
                "delta_id": row.delta_id,
                "target_skill_raw": row.target_skill,
                "target_skill_normalized": canonical,
                "live_skill_root": str(live_skill_root),
            },
        )
        return None
    ...
```

**Trade-offs**：
- 选「fallback 逻辑名」而非「LLM 必须填规范路径」：先解锁 batch；后续可逐步收紧，等 success rate 稳定后强制 pattern 仅匹配规范路径。
- pattern 用宽松正则（接受逻辑名），不用 strict regex；strict 会让 distill 重跑，目前没有那个回退预算。

### Gap 1 — 异步轨迹累积 / sedimentation 触发条件

**问题陈述**：
06-02 给了 `buffer_trajectory` / `sediment_trajectories` 但没给触发条件。08-05 干脆没接 buffer。"每 100 个 request distill 一次" 是 plan-level 假阳性条件——它假设 batch 大小 = 100、且失败模式均匀分布；真实场景里 stage 1 distill 已经在 batch 头部跑过一次，stage 2/3 内是否需要再次 distill 取决于产生的新模式数。

**设计**：

触发条件改为「**信号驱动 + 安全网**」：
1. **信号驱动**：每完成一个 trial，统计 `unbucketed_signature_count`（buffer 中未在 portfolio 反映的 trajectory_signature 数量）。当 `unbucketed >= 8` 触发 sedimentation + distill。
2. **安全网**：`elapsed_since_last_distill > 30 min` 或 `buffer_size > 200` 也触发。
3. **冷却**：触发后强制 cooldown 5 min（D-13 distill fires → main pause）。

**异步执行**：
- distill 在独立 task 内跑，不阻塞 production；结果通过 `assemble_portfolio` fold 进 portfolio。
- D-13 "main pause"：当 distill 在跑，新启动的 request 在 trial gate 处临时把 `production_pressure` 置 1（trial_prob = 0），其它 production 正常。

**代码形状**：
```python
class SedimentationOrchestrator:
    def __init__(self, *, buffer: list[TrajectoryRecord],
                 unbucketed_threshold: int = 8,
                 buffer_size_cap: int = 200,
                 elapsed_cap: timedelta = timedelta(minutes=30),
                 cooldown: timedelta = timedelta(minutes=5)): ...
    def should_fire(self, now: datetime, portfolio: list[DeltaPortfolioRow]) -> str | None: ...
    async def fire(self, *, distill_runner, portfolio_lock) -> list[DeltaProposal]: ...
```

**Trade-offs**：
- 不用「每 N request」固定阈值：违反 D-12 / D-14（"不是每条都进 durable evidence"）。
- 不用 cron（每小时）：与 D-13 同步暂停语义冲突。
- unbucketed_threshold = 8：单测里掌握；可暴露为 settings。

### Gap 2 — 同时从成功与失败模式 distill

**问题陈述**：
现 distill SKILL prose 偏向"找文案不好的失败模式"；用户明确要求双轨——成功路径 distill 出"高分演化模式"，失败路径 distill 出"反思模式"（rubric 全打一样无判别力 / 同一 stuck reasoning loop）。当前 SKILL 不具备双轨语义。

**设计**：

distill agent 调度改为两段：
1. **success-pattern distill**：buffer 里 success=True 且 quality_bucket="high" 的 trajectory 子集，prompt 偏向"找促成高分的稳定 pattern"。
2. **failure-pattern distill**：success=False 或 (success=True 但 quality_bucket="low") 的子集，prompt 偏向"找反复触发的反模式：同质化打分、推理循环、错位 surface"。

每段独立产 `DeltaProposal` list，合并后去重并加 `source: "success_distill" | "failure_distill"` tag（新加 `DeltaProposal.distill_source` 字段，pydantic 模型 Literal）。

**代码形状**：
```python
async def run_distill_dual_track(
    buffer: list[TrajectoryRecord],
    *,
    distill_runner,
) -> list[DeltaProposal]:
    success_subset, failure_subset = _split_buffer_by_outcome(buffer)
    success_proposals = await distill_runner.run(
        skill="distill-skill-deltas",
        prompt_variant="success_patterns",
        trajectories=success_subset,
    )
    failure_proposals = await distill_runner.run(
        skill="distill-skill-deltas",
        prompt_variant="failure_patterns",
        trajectories=failure_subset,
    )
    return _merge_and_dedupe(success_proposals, failure_proposals)
```

SKILL prose 加两个 prompt_variant 段：success_patterns + failure_patterns，由 distill_runner 选段渲染。

**Trade-offs**：
- 双调用 ~2× distill token：可接受；distill 频率本身受 Gap 1 cooldown 控制。
- 不在单 prompt 里要求 LLM 自分类：违反 D-08，让 LLM 自标 success/failure 轨迹会引入自报偏差。

### Gap 4 — Post-trial uplift evaluator（与文案打分解耦）

**问题陈述**：
当前 trial 把"rubric 给的 quality_score"直接当 success 信号。这有两层混淆：
1. quality 是 absolute 而非 relative，无 baseline 对照。
2. "delta 是否有效"≠"这次跑的文案好不好"——后者是 scenario-level noise dominate。

用户明确要求"把文案打分和 delta 测评分析分开"。

**设计 — paired control on same scenario**：

每次开 trial 时，跑两遍同 scenario：一遍 baseline（live skill tree，no patch），一遍 trial（patched tree）。两遍共享：
- 同 scenario data
- 同 LLM provider seed（如可控；DeepSeek 不支持则各跑一次接受方差）
- 同 trajectory prompt sequence

**Uplift 三轴公式**：
```
uplift = {
    "success_lift": int(trial.success) - int(baseline.success),  # ∈ {-1, 0, 1}
    "token_cost_delta": trial.token_cost - baseline.token_cost,  # int
    "behavioral_metric_lift": trial.M_axis - baseline.M_axis,    # dict per M
}
```

**bandit success 判据**（喂给 `update_after_trial(success=...)`）改为：
```python
success = (
    uplift["success_lift"] >= 0           # 不退步
    and uplift["token_cost_delta"] <= +budget_tolerance  # token 不爆
    and any(uplift["behavioral_metric_lift"][m] > 0 for m in M)  # 至少一项行为指标改善
)
```

**与文案打分的解耦**：
- 文案 rubric_score 只参与 baseline.success / trial.success 的判定（rubric 通过线 = success）。
- "delta 是否有效"的最终结论看 uplift 三轴组合，**不直接看 absolute rubric_score**——这就是用户说的"分开"。

**代码形状**：
```python
# evolution/uplift.py
@dataclass
class TrialUplift:
    success_lift: int
    token_cost_delta: int
    behavioral_metric_lift: dict[str, float]
    is_positive: bool

def compute_uplift(baseline: TrialOutcome, trial: TrialOutcome,
                   *, budget_tolerance: int) -> TrialUplift: ...

# trial_runner.py
def run_request_baseline(...) -> TrialOutcome: ...  # 同 run_request_trial 但 patch=None
```

**为何不选其他方案**：
- (b) 历史 baseline：跨 scenario 噪声大，dilution effect 严重。
- (c) rolling-window similar：similarity 度量本身需要再造，工作量翻倍。
- (d) cached score distribution：rubric 自身打分稳定性差，cache 反而引入 stale。
- (a) paired control：~2× token，但信号是真的；并发预算保护已通过 Gap 3 的 trial_prob 收紧。

### Gap 6 — Distill 证据持久化

**问题陈述**：
F-08-01 三因里点出：`_distill_after_stage1` 创建的 `RecordingProvider` 第二个参数是空 list 且从未 flush，distill agent 的 messages.jsonl / tool_calls.jsonl / artifact.json 全部不落盘。导致 batch 跑完后无法离线重放 distill 看 LLM 实际输出（这正是 F-08-01 主因被怀疑但不能直接确认的原因）。

**设计**：

在 `_distill_after_stage1` 与未来的 dual-track distill 调用处，把 RecordingProvider 的 request_log flush 到：

```
{output_dir}/distill_evidence/{batch_id}/{trigger_kind}/{trigger_id}/
    messages.jsonl
    tool_calls.jsonl
    artifact.json
    config.json   # prompt variant, buffer slice indices, trigger reason
```

`trigger_kind` ∈ {`stage1_seed`, `unbucketed_threshold`, `elapsed_safety_net`}。

**代码形状**：
```python
# evolution/distill_evidence.py
def persist_distill_evidence(
    *,
    output_dir: Path,
    batch_id: str,
    trigger_kind: str,
    trigger_id: str,
    request_log: list[RecordedExchange],
    artifact: DeltaDistillationArtifact | None,
    config: dict,
) -> Path: ...
```

**Trade-offs**：
- 落盘 = 离线重放可能；磁盘成本 ~50KB/distill。
- 不写到 sqlite/db：与现有 JSONL 风格一致；GSD 工具链全 file-based。

### Gap 7 — Portfolio 并发写：journal-then-fold

**问题陈述**：
Stage 3 c=20，runner 内多个 request 并发完成 trial 时同时调 `update_after_trial` 并把结果写回 `delta_portfolio[index]`。由于 list 不是 thread-safe + 每个 request 拿的 portfolio 是 snapshot，会出现 lost update（A 与 B 同时更新同一 row，B 的写覆盖 A）。当前实现 silent 数据损坏。

**设计 — journal-then-fold**：

每个 request 完成 trial 后，append 一行到 per-batch `portfolio_journal.jsonl`：
```json
{"request_id": "...", "delta_id": "d2_...", "success": true, "token_cost_delta": 312,
 "uplift": {...}, "ts": "2026-05-28T07:45:00Z"}
```

journal append 由 OS-level append-mode O_APPEND 保证 atomic write per line（POSIX 写 < PIPE_BUF 一次 write 不交错）。

scenario 末尾 / batch 末尾，单线程 fold：
```python
def fold_portfolio_journal(
    journal_path: Path,
    portfolio: list[DeltaPortfolioRow],
) -> list[DeltaPortfolioRow]:
    """Single-threaded fold; replays journal lines in order."""
    new_portfolio = list(portfolio)
    for line in journal_path.read_text().splitlines():
        entry = PortfolioJournalEntry.model_validate_json(line)
        idx = next(i for i, r in enumerate(new_portfolio)
                   if r.delta_id == entry.delta_id)
        new_portfolio[idx] = update_after_trial(
            new_portfolio[idx],
            success=entry.success,
            token_cost_delta=entry.token_cost_delta,
        )
    return new_portfolio
```

**race window 分析**：
- request 内 trial 拿的是 snapshot read；snapshot stale 的代价 = `select_trial_delta` 在略 stale 的 sample_count 上挑 row。这是可接受的——bandit 的 weight 对 1-step stale 不敏感。
- journal append 是 atomic（< PIPE_BUF）。
- fold 单线程，无 race。
- 极端：fold 失败（mid-write 进程死）→ 下次启动重放 journal 即可幂等恢复（`update_after_trial` 是纯函数）。

**Trade-offs vs CAS / 行锁**：
- CAS 重试：高并发下 retry 风暴，c=20 时退化成串行。
- 行锁：要么实现自己的 lock manager（复杂），要么用 fcntl（跨平台脆弱）。
- journal-then-fold：append-only + 单线程 fold，简单且 crash-safe。
- 缺点：portfolio 不是实时一致（trial gate 看到的 sample_count 比 journal 慢）。这是可接受的——D-25 明确说 selection 是 lightweight、容许近似。

### Gap 8 — Delta status 状态机

**问题陈述**：
`DeltaStatus` 枚举存在但**无任何代码做转移**。所有 row 永远 `experimental`。"if alpha > 10 → ready_for_review" 是假阳性公式（Beta 后验在 10 个样本时方差还很大，根本不该 promote）。

**设计 — 多轴硬阈值 + 软阈值组合**：

每次 fold portfolio 后，对每行计算：
1. `posterior_lcb = belief_alpha / (alpha + beta) - 1.96 * sqrt(p*(1-p)/n)`（Wilson 95% LCB）。
2. `token_cost_p95`：journal 内该 delta 所有 token_cost_delta 的 p95（不够 5 sample 时 = sum）。
3. `failure_pattern_repetition`：journal 内该 delta 失败时 trajectory_signature 的最高重复次数。

**转移规则（按优先级）**：
```python
def transition_status(row: DeltaPortfolioRow,
                      *, journal_summary: DeltaJournalSummary,
                      settings: StatusSettings) -> DeltaStatus:
    n = row.sample_count
    if n < settings.min_samples_for_decision:  # default 8
        return "experimental"

    # 硬 reject：失败率高且样本量足
    if (row.failure_count / n) > settings.reject_failure_rate:  # 0.7
        return "rejected"
    # 硬 reject：token 成本爆
    if journal_summary.token_cost_p95 > settings.reject_token_p95:  # +1500
        return "rejected"
    # 硬 reject：失败 pattern 高度重复(说明 delta 触发了 stuck loop)
    if journal_summary.max_failure_signature_repeat >= settings.reject_pattern_repeat:  # 5
        return "rejected"

    # ready_for_review：posterior LCB 越过阈值 + 样本量足
    if (row.posterior_lcb >= settings.ready_lcb  # 0.65
        and n >= settings.min_samples_for_promote  # 20
        and journal_summary.token_cost_p95 <= settings.ready_token_p95):  # +500
        return "ready_for_review"

    # held：信号微弱(LCB 在 0.4-0.65 区间)
    if 0.4 <= row.posterior_lcb < settings.ready_lcb:
        return "held"

    return "experimental"
```

**为何这套阈值不是又一组 magic number**：
- `min_samples_for_decision = 8`：来自 Beta(1,1) 后验在 8 个 sample 时 95% CI 宽度收敛到 0.3 左右，低于该数任何判定都是噪声。
- `reject_failure_rate = 0.7`：n=8 时 fail_count >= 6 才命中，对应 LCB ≈ 0.07 显著 < baseline 0.5。
- `min_samples_for_promote = 20`：Beta(1,1) + 20 sample → CI 宽度 ≈ 0.2，promote 决策风险可控。
- `ready_lcb = 0.65`：LCB > 0.65 说明真实成功率以 95% 置信高于 baseline 0.5 + 30% 缓冲。

**代码形状**：
```python
# evolution/status_machine.py
@dataclass
class StatusSettings: ...
@dataclass
class DeltaJournalSummary:
    token_cost_p95: int
    max_failure_signature_repeat: int

def summarize_journal_for_delta(journal: list[PortfolioJournalEntry], delta_id: str) -> DeltaJournalSummary: ...
def transition_status(row: DeltaPortfolioRow, *, journal_summary, settings) -> DeltaStatus: ...
def apply_status_transitions(portfolio: list[DeltaPortfolioRow], journal: list[...], settings) -> list[DeltaPortfolioRow]: ...
```

**Trade-offs**：
- LCB 计算需要标准库 math；不引依赖。
- 阈值集中到 `StatusSettings` dataclass，便于单测里覆盖、生产里 settings.toml 配置。
- 不用 Thompson sampling 做 promote 决策：promote 是 admin 行为，需要保守；LCB 是更严格 stop criterion。

### Gap 3 — 随机触发机制：信号源 + 并发安全

**问题陈述**：
现状随机触发的三个信号 (`recent_failure_rate` / `token_budget_pressure` / `production_pressure`) 在 08-05 的 plan 文里没指定数据来源，08-05 真实落地时被填成 `0.0` 三连——意味着 `trial_prob = 1`，每个 request 必开 trial（再叠加 deterministic loop = 每 request 跑 4 次），c=20 并发时压根没考虑预算保护。同时 `select_trial_delta` 是无状态纯函数，没人维护 rolling window；并发写 portfolio 也没有 lock。

**设计**：

新增 `seers_harness/evolution/trial_signal.py`：

```python
class ProductionSignalWindow:
    """Per-batch rolling window of production (baseline-only) outcomes.

    - 仅累积 trial=None 的 baseline 完成记录,trial 自身不污染信号源
      (否则正反馈：trial 失败 → recent_failure_rate ↑ → trial_prob ↓ → 信号
      被冻结)。
    - 线程安全：内部 threading.Lock 保护 deque。
    """
    def __init__(self, max_size: int = 50): ...
    def record_baseline_outcome(self, *, success: bool, total_tokens: int) -> None: ...
    def failure_rate(self) -> float:
        """fail / (success + fail);窗口 < 10 时返回 0.0(冷启动不施加压力)。"""
    def token_pressure(self, *, budget_per_request: int) -> float:
        """clip(mean_tokens / budget, 0, 1);窗口 < 5 时返回 0.0。"""

def concurrency_pressure(*, inflight: int, max_concurrent: int) -> float:
    """clip(inflight / max_concurrent, 0, 1);max_concurrent <= 0 返回 0.0。"""
```

**真实数据源（与"假阳性"对照）**：
| 信号 | 假阳性来源 | 真实来源 |
|---|---|---|
| recent_failure_rate | hardcoded 0.0 | rolling 50 baseline outcome → fail/(s+f) |
| token_budget_pressure | hardcoded 0.0 | rolling mean total_tokens / settings.token_budget_per_request |
| production_pressure | hardcoded 0.0 | runtime.inflight_count() / settings.max_concurrent |

**并发安全**：
- ProductionSignalWindow.record_baseline_outcome 在 `_run_one_request` 完成 baseline 后调用；因 `Lock` 保护 deque，c=20 时安全。
- `runtime.inflight_count()` 通过 asyncio Semaphore 计数器或 threadsafe atomic counter 暴露。

**c=20 高并发下的真实期望**：
- 冷启动（前 10 个 baseline）：所有信号 = 0 → trial_prob = 1，开放 trial。
- 稳态：假设 baseline 失败率 = 0.2, token usage = 0.7×budget, inflight = 0.5×max → trial_prob = 0.8 × 0.3 × 0.5 = 0.12，约每 8 个 request 开一个 trial。这是 D-11 "不是每个 trajectory 同步分析" 的真实约束。
- 失败潮：baseline 失败率突然 = 0.6 → trial_prob 立刻坠到 0.4 × 0.3 × 0.5 = 0.06，trial 自动减少（让 production 先稳）。

**代码形状（function signatures）**：
```python
# trial_signal.py
class ProductionSignalWindow: ...
def concurrency_pressure(*, inflight: int, max_concurrent: int) -> float: ...

# runner.py 改动
self._trial_signal_window = ProductionSignalWindow(max_size=50)
# in _run_one_request: 在 baseline 完成后
self._trial_signal_window.record_baseline_outcome(success=..., total_tokens=...)
```

**Trade-offs**：
- 选 rolling deque 而非 EWMA：deque 边界清晰、单测断言简单；EWMA 平滑但调参一项 alpha 又是 magic number。
- 冷启动返回 0：让 batch 头几次 trial 必开，加速早期 sampling；副作用是预算保护初期失效，可接受（cap by inflight 仍然 hold）。
- 不引入 cross-batch 记忆：每 batch 重新冷启动，避免 stale 状态。


---

## 5. The new `select_trial_delta` call site

替换位置：`seers_harness/validation/runner.py:_run_one_request`，目前 line ~634 的 `for index, portfolio_row in enumerate(delta_portfolio):` 整段循环（含 `_patch_from_portfolio_row` / `run_request_trial` / `update_after_trial` 三调用）。

**新代码形状**（仅签名 / 控制流，不写完整 body）：

```python
# --- pre-trial gate inputs (Gap 3 信号源) -----------------------------------
applicable_surface = _surface_for_request(scenario, nodes)
# = 集合 {"factor_discovery", "copy_generation", "rubric_judge"} 中
#   实际本次 request 会执行的 node 名

recent_failure_rate = trial_signal_window.failure_rate()
# = ProductionSignalWindow（rolling 50 个最近 production-only 记录）
#   .failure_rate() 返回 fail / (success + fail)，0..1。
#   注意：production 记录指 trial=None 的那条 baseline 通过，不混入 trial 结果。

token_budget_pressure = trial_signal_window.token_pressure(
    budget_per_request=settings.token_budget_per_request,
)
# = clip(rolling_mean_request_tokens / budget_per_request, 0, 1)

production_pressure = trial_signal_window.concurrency_pressure(
    inflight_requests=runtime.inflight_count(),
    max_concurrent=settings.max_concurrent,
)
# = clip(inflight_requests / max_concurrent, 0, 1)
#   c=20 时 inflight 接近 20 → pressure 接近 1 → 几乎不开 trial。

picked_delta_id = select_trial_delta(
    portfolio=delta_portfolio,
    applicable_surface=applicable_surface,
    recent_failure_rate=recent_failure_rate,
    token_budget_pressure=token_budget_pressure,
    production_pressure=production_pressure,
    rng=trial_rng,  # batch-level seeded Random for determinism
)
```

**两条分支**：

**分支 A — `picked_delta_id is None`（不开 trial）**：
- 仍跑 baseline production：正常 dag_runner.run，记录 baseline outcome 到 `TrajectoryRecord`，写入 trajectory_buffer。
- `record["trial_selected_delta_id"] = None`、`record["trial_skipped_reason"] = "no_trial_gate" | "no_eligible_delta" | "all_held_or_rejected"`（select 内部分支可暴露原因）。
- 不写 portfolio journal。

**分支 B — `picked_delta_id is not None`（开 trial）**：
1. 找到 row：`row = next(r for r in delta_portfolio if r.delta_id == picked_delta_id)`。
2. `patch = _patch_from_portfolio_row_v2(row, live_skill_root)`（Gap 5 修后的版本，路径归一化）。
3. 若 `patch is None`：写 `record["trial_skipped_reason"] = "patch_resolve_failed"`，落 explicit log（**不再 silent**），把 row 推入 `held` 状态（patch 不可解析视为软失败），更新 portfolio journal。
4. **paired control**（Gap 4）：先以 baseline skill tree 跑一遍，再以 patched tree 跑一遍。两次跑同 scenario / 同 prompt seed / 同 LLM call seed。`run_request_trial` 仅跑 patched 一遍，需要新加 `run_request_baseline` 跑 baseline 一遍。
5. 计算 uplift：成功率差、token 成本差、behavioral metric 差三轴。
6. 写 portfolio journal 一行：`{request_id, delta_id, success, token_cost_delta, uplift_axes}`。
7. trajectory_buffer append 一条带 `trial_delta_id` 的 record。

**为什么不在 selection 里复用 deterministic loop**：
- D-09 明确要求 trial 是 portfolio-adaptive 随机的，不是 round-robin。
- c=20 并发时 deterministic loop 会让每个 request 都跑 4×（baseline + 4 trials）= 5 倍 token，预算炸穿。
- bandit 收敛靠 sample scarcity 加权，deterministic loop 让 sample_count 同步线性增长，scarcity 信号失效。

**信号源真实数据来源**（驳"假阳性"）：
- `recent_failure_rate`：production rolling window，**不是**当前 batch 任意常数。窗口冷启动时（< 10 sample）默认返回 0.0。
- `token_budget_pressure`：rolling mean of `total_tokens` per request / `settings.token_budget_per_request`（user-configured 上限）。
- `production_pressure`：`runtime.inflight_count()` / `settings.max_concurrent`，**不是** batch_size。
- `applicable_surface`：scenario.flags / nodes 反推，不是 portfolio row 自报。

---

## 6. Test plan

### 单测（按 plan 拆分）

**U1. `_normalize_target_skill` (Gap 5)** — 给定 `["current/foo/SKILL.md", "foo", "foo.md", "  foo  "]` 全部归一为 `current/foo/SKILL.md`；空串 / `current/` 等异常输入返回明显失败的形态供 `live_target.exists()` short-circuit。
- Fail 条件：任何一种输入归一后路径不存在又不 log warning。

**U2. `_patch_from_portfolio_row_v2` resolve 路径** — fixture 写一个 `current/discover-personalization-factors/SKILL.md`，3 种填法（规范 / 逻辑名 / `.md` 后缀）全部成功 build patch。`add_skill` change_type 仍返回 None。
- Fail 条件：3 种填法任一返回 None。

**U3. `ProductionSignalWindow` failure_rate 冷启动** — 注入 5 条 baseline，仍返回 0.0；注入 10 条（4 fail）返回 0.4；并发 20 个 thread 各注入 50 条不丢失任何记录（`failure_count + success_count == 1000`）。
- Fail 条件：counter 漏写、冷启动返回非 0、并发丢数据。

**U4. `concurrency_pressure`** — `inflight=10, max=20 → 0.5`；`max=0 → 0.0`；`inflight=30, max=20 → 1.0`（clip）。
- Fail 条件：未 clip / div by zero。

**U5. `select_trial_delta` 三压力极端** — 三压力全 1.0 → 总返回 None；全 0.0 + 单 row → 返回该 row id；全 0.0 + 多 row 跑 1000 次随机：scarcity weight 让 sample_count=0 的 row 被选概率 > sample_count=10 的 row 概率（卡方）。
- Fail 条件：高压力下仍返回非 None；scarcity 失效。

**U6. `compute_uplift` is_positive** — paired (baseline=fail, trial=success, token+200, M+0.1) → is_positive=True；(baseline=success, trial=fail) → False；(baseline=success, trial=success, token+5000) → False（token 爆）。
- Fail 条件：success_lift 单调性破坏。

**U7. `SedimentationOrchestrator.should_fire`** — buffer 有 8 个新签名 → 返回 `"unbucketed_threshold"`；7 个 → None；buffer 200 但全部已 bucketed → 返回 `"buffer_size_cap"`；上次 fire 30 min 前且 buffer 1 → `"elapsed_safety_net"`；cooldown 内 → None。
- Fail 条件：阈值边界 off-by-one；cooldown 不生效。

**U8. `fold_portfolio_journal` 幂等** — 同一 journal 跑两次 fold 出来 sample_count 一致；journal 中混入 unknown delta_id 时 fold 跳过该行并 log warning。
- Fail 条件：sample_count 翻倍（说明 fold 不幂等）；unknown id raise。

**U9. `transition_status` 多轴硬阈值** — `(n=8, fail=6) → "rejected"`；`(n=20, posterior_lcb=0.7, token_p95=300) → "ready_for_review"`；`(n=12, lcb=0.5) → "held"`；`(n=4) → "experimental"`；`(n=20, token_p95=2000) → "rejected"`（token 爆）。
- Fail 条件：任意硬阈值未触发或越级。

**U10. `run_distill_dual_track` 双调用** — mock distill_runner 验证它被调用 2 次（success_patterns + failure_patterns）；buffer 全 success → failure_patterns 收到空 subset 但仍调用一次。
- Fail 条件：调用次数 != 2 或 prompt_variant 错传。

**U11. `persist_distill_evidence` 落盘** — 调用后 4 个 file 出现在预期路径；artifact=None 时 `artifact.json` 不写（不写空文件）。
- Fail 条件：缺文件或写空文件。

**U12. `trajectory_signature` 双轨签名** — success path / failure path 同 quality_bucket 时签名不同（success flag 区分）；同 success 同 quality 不同 failure_category 时签名不同。
- Fail 条件：碰撞（已有 06-02 测试，本测增量验证 dual-track 场景）。

### 集成测试

**I1. End-to-end with mock LLM, c=4, 50 requests** — fixture 一个固定 portfolio (4 行)；mock provider 让前 25 req baseline=success，后 25 req baseline=fail。验证：
- `recent_failure_rate` 在 req#26 起开始升高。
- trial 频率在 req#10 (冷启动结束) 之前 > 0.7，req#30 之后 < 0.3。
- 最终 portfolio status 至少有 1 个 row 推到 `held` 或 `ready_for_review` 或 `rejected`。
- portfolio_journal.jsonl 行数 = 实际 trial 次数 ≠ 50。
- Fail 条件：trial 频率不响应失败潮；status 全停留在 experimental。

**I2. Concurrency stress, c=20, 200 requests** — fixture 4 行 portfolio；并发 20 跑 200 req。验证：
- portfolio_journal.jsonl 行数 = trial 次数（无写丢失）。
- fold 后 sum(sample_count) == journal 行数。
- ProductionSignalWindow 计数无 race 损失。
- Fail 条件：行数不等；sample_count 损失。

**I3. F-08-01 回归** — 用 F-08-01 batch 的相同 portfolio 输入 (4 个含逻辑名 target_skill 的 row)、live_skill_root 真实结构。Stage 2 至少 50% req 触发 trial 且至少 1 个 trial 完成 paired control 并写 journal。
- Fail 条件：trial=0（即 F-08-01 复现）。



---

## 7. Plan-level breakdown (09-01..09-06)

按依赖顺序排：09-01 是 unblock 器，可独立先 ship；其余 plan 之间几乎线性依赖。

### Plan 09-01 — target_skill 三处格式合约（unblock F-08-01）
- **Scope**：SKILL prose 加 target_skill 规则 + 3 个 example；tool spec `target_skill` 加 description + pattern；`_patch_from_portfolio_row_v2` 加路径归一化 + explicit warning log。
- **Files**：
  - `workflow-skills/current/distill-skill-deltas/SKILL.md`（prose 段）
  - `seers_harness/tools/evolution_tools.py`（RECORD_DELTA_CHANGE_SPEC.target_skill）
  - `seers_harness/validation/runner.py`（`_patch_from_portfolio_row_v2` 替换原 `_patch_from_portfolio_row`）
  - `tests/validation/test_patch_helpers.py`（新增 U1+U2）
- **Depends on**: 无
- **Commit estimate**：1 atomic commit, ~80 LOC

### Plan 09-02 — ProductionSignalWindow + concurrency_pressure
- **Scope**：新建 `evolution/trial_signal.py`；runner.py 持有 `_trial_signal_window` 与 inflight counter；baseline 完成时 record。
- **Files**：
  - `seers_harness/evolution/trial_signal.py`（新）
  - `seers_harness/validation/runner.py`（field + record_baseline_outcome call）
  - `tests/evolution/test_trial_signal.py`（U3+U4）
- **Depends on**：09-01（path resolve 修了，trial 才能跑到 baseline 完成）
- **Commit estimate**：1 atomic commit, ~120 LOC

### Plan 09-03 — call-site 替换：select_trial_delta + paired control + uplift
- **Scope**：替换 `_run_one_request` deterministic loop；新加 `run_request_baseline`、`compute_uplift`；写 portfolio_journal.jsonl；显式 "trial_skipped_reason" log。
- **Files**：
  - `seers_harness/evolution/trial_runner.py`（`run_request_baseline` 添加）
  - `seers_harness/evolution/uplift.py`（新）
  - `seers_harness/evolution/portfolio_journal.py`（新；append helper + entry pydantic）
  - `seers_harness/validation/runner.py`（大改）
  - `tests/evolution/test_uplift.py`（U6）
  - `tests/evolution/test_select_trial_delta_integration.py`（U5）
- **Depends on**：09-02
- **Commit estimate**：2 atomic commits（先 helpers，再 call site）, ~180 LOC

### Plan 09-04 — Trajectory buffer + SedimentationOrchestrator + dual-track distill
- **Scope**：runner.py 持有 trajectory_buffer；每 req 完成 append；orchestrator 在 scenario 边界轮询 should_fire；fire 时 dual-track distill；落盘 distill_evidence。
- **Files**：
  - `seers_harness/evolution/sedimentation.py`（新；含 orchestrator + dual-track distill）
  - `seers_harness/evolution/distill_evidence.py`（新；persist helper）
  - `workflow-skills/current/distill-skill-deltas/SKILL.md`（加 prompt_variant 两段）
  - `seers_harness/validation/runner.py`（buffer 接线、main-pause 信号）
  - `tests/evolution/test_sedimentation.py`（U7+U10+U11+U12）
- **Depends on**：09-03（trajectory_record 含 trial_delta_id 需要 trial 已跑）
- **Commit estimate**：3 atomic commits（orchestrator / dual-track distill / persistence）, ~260 LOC

### Plan 09-05 — fold_portfolio_journal + apply_status_transitions
- **Scope**：scenario/batch 末尾跑 fold 与 status transitions；写 portfolio snapshot；evolution_snapshot 写出 status_transitions 段。
- **Files**：
  - `seers_harness/evolution/portfolio_journal.py`（fold 函数）
  - `seers_harness/evolution/status_machine.py`（新）
  - `seers_harness/validation/runner.py`（scenario_end hook）
  - `tests/evolution/test_portfolio_journal_fold.py`（U8）
  - `tests/evolution/test_status_machine.py`（U9）
- **Depends on**：09-03（journal 写入端）
- **Commit estimate**：2 atomic commits, ~150 LOC

### Plan 09-06 — Integration acceptance batch
- **Scope**：跑一个小规模真 batch (1 scenario, 10 stage1 + 30 stage2 req)，验证 F-08-01 不再复现且至少 1 个 delta 完成 status transition；新增 I1+I2+I3 集成测试。
- **Files**：
  - `tests/integration/test_evolution_e2e.py`（I1+I2+I3）
  - `.planning/phases/09-...../06-batch-evidence/`（artifact）
- **Depends on**：09-05
- **Commit estimate**：1 atomic commit, ~190 LOC

---

## 8. What we DON'T do in this phase

明确划出本次重设计**不覆盖**的范围，避免 scope creep：

1. **不引入 cross-batch portfolio 长期记忆**：portfolio_journal 与 status transition 仅在单 batch 内生效。跨 batch 状态如何继承（D-27 candidate）留给后续 phase。
2. **不实装 `ready_for_review` 之后的人审 + merge 流程**：本 phase 只把状态机推到 `ready_for_review`，不动 live skill 树。这与 06-02 / D-17 "trial isolation via temp git patch"一致——live tree 永远不被 commit 修改。
3. **不重写 `distill-skill-deltas` skill 的核心 prompt**：仅加 target_skill 规则段与 prompt_variant 两段；其余 prose 不动（属 phase 7 已收敛产物）。
4. **不实装 Thompson sampling**：`select_trial_delta` 当前的 scarcity × belief 加权简单且单测稳定；切到 TS 是 D-25 之后的优化项。
5. **不实装 PPO/RL 风格的轨迹回放**：D-13 同步暂停 + sedimentation 是当前妥协。replay-based fine-tune 留给未来的 phase。
6. **不解决 DeepSeek provider seed 不可控导致 paired control 残留方差**：Gap 4 接受这部分方差，靠 sample_count >= 20 推 ready_for_review 时降权。如改用 Anthropic / OpenAI seed-controllable provider，可在 09-06 后另起 plan 收紧。
7. **不在本 phase 内加 distill agent 的 streaming output**：distill_evidence 落盘是 batch-level 异步，足够离线重放；streaming 实时观测是 observability 优化项。
8. **不修 phase 8 的其它 F-08-02..F-08-C debt**：本 finding 仅修 F-08-01 与 D-08/09/11..17 的演化机制；其它 phase 8 debt 由 Agent A/B/C 报告处理。

