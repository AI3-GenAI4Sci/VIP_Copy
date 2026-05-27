---
phase: 08-evolution-wiring-and-runner-debt
plan: G4
type: execute
wave: 4
gap_closure: true
depends_on:
  - 08-G3
files_modified:
  - seers_harness/evolution/trial_signal.py
  - seers_harness/evolution/uplift.py
  - seers_harness/evolution/portfolio_journal.py
  - seers_harness/evolution/status_machine.py
  - seers_harness/evolution/trial_runner.py
  - seers_harness/validation/runner.py
  - tests/test_trial_signal.py
  - tests/test_uplift.py
  - tests/test_portfolio_journal.py
  - tests/test_status_machine.py
  - tests/test_trial_runner_baseline.py
  - tests/test_validation_runner.py
autonomous: true
requirements: []
must_haves:
  goal: "把 deterministic loop 替换为真 bandit + paired control + journal-then-fold + ProductionSignalWindow + Wilson 95% LCB 状态机。**复用** 06-02 已有的 orphan code(`select_trial_delta` / `belief_mean` / `update_after_trial` / `buffer_trajectory` / `sediment_trajectories` / `trajectory_signature`),NOT rewrite。修复 F-08-D Gap 3 (random trigger 真信号源) + Gap 4 (paired control uplift 与文案打分解耦) + Gap 7 (并发 portfolio 写) + Gap 8 (status 转移)。Real-LLM evidence target:Stage 3 c=20 batch 至少 5/20 reqs trigger trial,evolution_snapshot.trials[] 非空,至少 1 个 delta 完成 status 转移。"
  truths:
    - "(F-08-D Gap 3)信号源 SHALL be runtime-observable, NEVER hardcoded:`recent_failure_rate` from `ProductionSignalWindow.failure_rate()` rolling 50 baseline outcomes;`token_budget_pressure` from `ProductionSignalWindow.token_pressure(budget_per_request)`;`production_pressure` from `concurrency_pressure(inflight, max_concurrent)` 其中 inflight 来自 Semaphore counter。三个信号在 cold start (< 10 baseline) return 0.0 让早期 trial 必触发"
    - "(F-08-D Gap 7)portfolio mutation 是 fold-only at scenario boundary:mid-scenario 写只 append 到 per-batch `portfolio_journal.jsonl` 通过 POSIX O_APPEND;fold 单线程在 scenario 末尾跑 `fold_portfolio_journal(...)` 把 journal entries 还原成 portfolio 增量。c=20 并发下无 lost update"
    - "(F-08-D Gap 4)post-trial bandit success uses uplift triple, NOT raw rubric score:`success = uplift.success_lift >= 0 AND token_cost_delta <= +budget_tolerance AND any(behavioral_metric_lift > 0)`。文案打分(rubric)只参与 baseline.success / trial.success 各自的判定,NOT 直接喂 bandit"
    - "(F-08-D Gap 8)status transitions use Wilson 95% LCB + 多轴硬阈值:promotion to `ready_for_review` 要求 LCB ≥ 0.6 AND sample_count ≥ 5 AND token_cost_p95 ≤ +budget_tolerance × 2;demotion to `rejected` 要求 LCB ≤ 0.2 AND sample_count ≥ 10;否则保持 `experimental`"
    - "(D8-F locked, anti-rewrite)06-02 functions(`select_trial_delta` / `buffer_trajectory` / `sediment_trajectories` / `belief_mean` / `update_after_trial` / `trajectory_signature`)wired-through, NOT rewritten — `git diff seers_harness/evolution/delta_portfolio.py` 显示只 import / 无 body 修改这些函数"
    - "(F-08-D Gap 4)paired control 配对发生在同 scenario:trial 触发时,先跑 baseline (no patch) 再跑 trial (with patch),共享 same scenario data + same nodes;两次 LLM 调用代价 ~2x token,通过 trial_prob 收紧补偿"
    - "(F-08-01 fix verification)trial_workspace 真创建当且仅当 select_trial_delta return 非 None;_patch_from_portfolio_row 拒绝时 select_trial_delta 调用前已被 G3 的 pattern gate 拦下"
  artifacts:
    - path: seers_harness/evolution/trial_signal.py
      provides: "ProductionSignalWindow class (rolling deque + threading.Lock) + concurrency_pressure(inflight, max_concurrent) → float ∈ [0,1]"
      contains: "ProductionSignalWindow"
    - path: seers_harness/evolution/uplift.py
      provides: "@dataclass TrialUplift + compute_uplift(baseline, trial, *, budget_tolerance) → TrialUplift; is_positive 决定 bandit success"
      contains: "TrialUplift"
    - path: seers_harness/evolution/portfolio_journal.py
      provides: "PortfolioJournalEntry pydantic + append_journal_entry POSIX O_APPEND + fold_portfolio_journal 单线程 reduce"
      contains: "fold_portfolio_journal"
    - path: seers_harness/evolution/status_machine.py
      provides: "apply_status_transitions(portfolio) using Wilson 95% LCB + 多轴硬阈值"
      contains: "apply_status_transitions"
    - path: seers_harness/evolution/trial_runner.py
      provides: "新增 run_request_baseline(*, runtime, scenario, nodes, ...) 同 run_request_trial 但 patch=None,用于 paired control"
      contains: "run_request_baseline"
    - path: seers_harness/validation/runner.py
      provides: "_run_one_request 替换 deterministic loop:select_trial_delta gate → 若返 delta_id 跑 paired (baseline + trial) → compute_uplift → append journal;scenario 末尾 fold + apply_status_transitions"
      contains: "select_trial_delta"
  key_links:
    - from: _run_one_request trial gate
      to: select_trial_delta
      via: "06-02 orphan function 接通到 production loop"
      pattern: "select_trial_delta\\("
    - from: _run_one_request paired control
      to: run_request_baseline + run_request_trial
      via: "trial 触发时跑两次同 scenario,baseline patch=None / trial patch=non-None"
      pattern: "run_request_baseline\\("
    - from: _run_one_request post-trial
      to: append_journal_entry
      via: "uplift 算完后 append 到 per-batch portfolio_journal.jsonl"
      pattern: "append_journal_entry\\("
    - from: scenario boundary
      to: fold_portfolio_journal + apply_status_transitions
      via: "stage 末尾或 batch 末尾单线程 fold + 状态转移;portfolio 直接 mutate"
      pattern: "fold_portfolio_journal\\("
  forbid_list:
    - "禁止 hardcoded 0.0 信号:`recent_failure_rate=0.0` / `token_budget_pressure=0.0` / `production_pressure=0.0` 三常量调用是反模式 — 必须从 ProductionSignalWindow / Semaphore counter 取"
    - "禁止 重写 06-02 的 select_trial_delta / buffer_trajectory / sediment_trajectories / belief_mean / update_after_trial / trajectory_signature — git diff seers_harness/evolution/delta_portfolio.py 在 G4 commit 中只能 import 改动,函数体不动"
    - "禁止 用 raw rubric score 直接喂 bandit:bandit success 必须走 uplift triple"
    - "禁止 mid-scenario 直接 mutate portfolio:所有写必须 append 到 portfolio_journal.jsonl;fold 在 scenario 边界单线程跑"
    - "禁止 在 _run_one_request 加 try/except 把 baseline 失败转 trial_failure — baseline 失败是 D-19 路由 provider_error / infra_error fail-fast 信号,不能掩盖"
    - "禁止 status 转移用单轴判据(只看 LCB / 只看 sample_count / 只看 token_cost):必须多轴 AND 组合 per Gap 8 设计"
---

<objective>
落地 F-08-D 的 5 个深层 Gap(3 信号源 / 4 解耦 uplift / 7 并发 portfolio / 8 status 转移),把 06-02 已写好的 bandit 接线到 _run_one_request,完整闭环 distill→portfolio→trial→uplift→bandit→status。这是 phase 8 gap-closure 的 *primary deliverable*,体量最大(~4 个新模块 + runner 主循环替换 + 11+ 单测 + 1 集成测试),复杂度最高。

Purpose: F-08-01 表层 bug + 0526 batch 的 deterministic loop 已经表明 plan 08-05 设计绕过了 06-02 的 bandit。本 plan 是把 select_trial_delta / buffer_trajectory / sediment_trajectories / belief_mean / update_after_trial / trajectory_signature 真接到 production,同时补 ProductionSignalWindow + uplift + journal + status_machine 四个新模块,补足 06-02 没设计的边界(信号源、解耦评估、并发安全、状态转移)。
Output: 4-5 个 atomic commit:(1) trial_signal + 单测;(2) uplift + 单测;(3) portfolio_journal + status_machine + 单测;(4) trial_runner.run_request_baseline + 单测;(5) runner.py:_run_one_request 替换 deterministic loop + 集成测试。
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/08-evolution-wiring-and-runner-debt/08-CONTEXT.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-D-delta-mechanism-redesign.md
@.planning/phases/06-evolution-chain-production-hardening/06-02-SUMMARY.md
@seers_harness/evolution/delta_portfolio.py
@seers_harness/evolution/trial_runner.py
@seers_harness/validation/runner.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: ProductionSignalWindow + concurrency_pressure(新模块 trial_signal.py)+ 4 个单测</name>
  <files>seers_harness/evolution/trial_signal.py, tests/test_trial_signal.py</files>
  <read_first>
    - seers_harness/evolution/delta_portfolio.py(`select_trial_delta` 签名 — 看本模块产出的信号要喂给哪些参数)
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-D-delta-mechanism-redesign.md §Gap 3 完整伪代码
  </read_first>
  <behavior>
    模块 `seers_harness/evolution/trial_signal.py` 新建,内容:

    ```
    """Real-source trial signal window for select_trial_delta inputs."""
    from __future__ import annotations
    from collections import deque
    from threading import Lock
    from dataclasses import dataclass

    @dataclass
    class _BaselineRecord:
        success: bool
        total_tokens: int

    class ProductionSignalWindow:
        """Per-batch rolling window of baseline-only outcomes.
        Trial outcomes are NEVER recorded here (would create positive feedback)."""
        def __init__(self, max_size: int = 50) -> None: ...
        def record_baseline_outcome(self, *, success: bool, total_tokens: int) -> None: ...
        def failure_rate(self) -> float: ...
        def token_pressure(self, *, budget_per_request: int) -> float: ...

    def concurrency_pressure(*, inflight: int, max_concurrent: int) -> float: ...
    ```

    实现细节:
    - `ProductionSignalWindow.__init__`:`self._buf: deque[_BaselineRecord] = deque(maxlen=max_size)`,`self._lock = Lock()`
    - `record_baseline_outcome`:`with self._lock: self._buf.append(_BaselineRecord(success, total_tokens))`
    - `failure_rate()`:`with self._lock: ... ` 复制 buf;若 len < 10 return 0.0(冷启动);否则 `fails / (success + fails)`
    - `token_pressure(*, budget_per_request)`:`with self._lock: ... ` 复制;若 len < 5 return 0.0;否则 `min(1.0, mean_tokens / budget_per_request)`
    - `concurrency_pressure`:纯函数,`if max_concurrent <= 0: return 0.0; else: return min(1.0, max(0.0, inflight / max_concurrent))`

    单测 `tests/test_trial_signal.py`:
    - `test_failure_rate_cold_start_returns_zero`:< 10 records 全 fail,assert == 0.0
    - `test_failure_rate_steady_state`:30 records,12 fail / 18 success,assert == 0.4
    - `test_token_pressure_clipped_to_one`:5 records 都 total_tokens=10000, budget=5000,assert == 1.0
    - `test_concurrency_pressure_handles_zero_max`:max_concurrent=0,assert == 0.0;inflight=10/max=20,assert == 0.5
    - `test_record_baseline_outcome_thread_safe`:开 20 个线程 each append 100 records,assert len(buf) == 50(maxlen),无数据损坏
  </behavior>
  <action>
    新建 `seers_harness/evolution/trial_signal.py` 按 behavior 段实现。
    新建 `tests/test_trial_signal.py` 5 个测试。
  </action>
  <verify>
    <automated>pytest -q tests/test_trial_signal.py -x 2>&1 | tail -15 ; grep -c "ProductionSignalWindow" seers_harness/evolution/trial_signal.py</automated>
    <human-check>5 测全绿;ProductionSignalWindow 出现 ≥ 2(class def + class body 引用)</human-check>
  </verify>
  <done>
    - trial_signal.py 模块完整
    - 5 单测全绿
    - 全套 pytest 不回归
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: TrialUplift + compute_uplift(新模块 uplift.py)+ 5 个单测</name>
  <files>seers_harness/evolution/uplift.py, tests/test_uplift.py</files>
  <read_first>
    - seers_harness/evolution/trial_runner.py(TrialOutcome 字段:success / failure_category / token_cost_observed / artifact_paths / tool_call_count / trial_delta_id)
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-D-delta-mechanism-redesign.md §Gap 4
  </read_first>
  <behavior>
    模块 `seers_harness/evolution/uplift.py`:

    ```
    """Paired-control uplift evaluator — decoupled from rubric copy scoring."""
    from __future__ import annotations
    from dataclasses import dataclass, field
    from seers_harness.evolution.trial_runner import TrialOutcome

    @dataclass
    class TrialUplift:
        success_lift: int          # int(trial.success) - int(baseline.success), ∈ {-1, 0, 1}
        token_cost_delta: int      # trial.token_cost_observed - baseline.token_cost_observed
        behavioral_metric_lift: dict[str, float] = field(default_factory=dict)
        is_positive: bool = False

    def compute_uplift(
        baseline: TrialOutcome,
        trial: TrialOutcome,
        *,
        budget_tolerance: int = 1000,
        behavioral_metrics_baseline: dict[str, float] | None = None,
        behavioral_metrics_trial: dict[str, float] | None = None,
    ) -> TrialUplift: ...
    ```

    `is_positive` 计算:
    ```
    is_positive = (
        success_lift >= 0
        and token_cost_delta <= budget_tolerance
        and any(metric_lift > 0 for metric_lift in behavioral_metric_lift.values())
    )
    ```
    若 behavioral_metric_lift 为空 dict,is_positive = (success_lift > 0 AND token_cost_delta <= budget_tolerance)(避免 vacuous true)。

    单测 `tests/test_uplift.py`:
    - `test_uplift_strict_positive`:success_lift=1, token_cost_delta=-200, behavioral_metrics={"M1": 0.1} → is_positive=True
    - `test_uplift_token_blow_up_blocks`:success_lift=1, token_cost_delta=2000(超 tolerance), → is_positive=False
    - `test_uplift_no_behavioral_lift_blocks`:success_lift=0, behavioral_metrics={"M1": -0.05, "M2": 0.0} → is_positive=False
    - `test_uplift_regression_blocks`:success_lift=-1 → is_positive=False
    - `test_uplift_empty_metrics_falls_back_to_strict_lift`:behavioral_metric_lift 全空 dict;success_lift=0 → is_positive=False(不 vacuous true)
  </behavior>
  <action>
    新建 `seers_harness/evolution/uplift.py` 按 behavior 段。
    新建 `tests/test_uplift.py` 5 测。
  </action>
  <verify>
    <automated>pytest -q tests/test_uplift.py -x 2>&1 | tail -15 ; grep -c "compute_uplift" seers_harness/evolution/uplift.py</automated>
    <human-check>5 测全绿;compute_uplift 在 uplift.py 出现 ≥ 1(def)。</human-check>
  </verify>
  <done>
    - uplift.py 模块完整
    - 5 单测全绿
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: portfolio_journal + status_machine 两模块 + 9 单测</name>
  <files>seers_harness/evolution/portfolio_journal.py, seers_harness/evolution/status_machine.py, tests/test_portfolio_journal.py, tests/test_status_machine.py</files>
  <read_first>
    - seers_harness/evolution/delta_portfolio.py(DeltaPortfolioRow 字段;`update_after_trial`签名;DeltaStatus enum)
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-D-delta-mechanism-redesign.md §Gap 7 + §Gap 8
  </read_first>
  <behavior>
    `seers_harness/evolution/portfolio_journal.py`:
    - pydantic `PortfolioJournalEntry`:fields(`request_id: str` / `delta_id: str` / `success: bool` / `token_cost_delta: int` / `behavioral_metric_lift: dict[str, float]` / `ts: str`)
    - `def append_journal_entry(journal_path: Path, entry: PortfolioJournalEntry) -> None`:open mode=`"a"`(POSIX O_APPEND atomic per-line);写 entry.model_dump_json() + `"\n"`
    - `def fold_portfolio_journal(journal_path: Path, portfolio: list[DeltaPortfolioRow]) -> list[DeltaPortfolioRow]`:single-threaded;读所有 lines;每行 model_validate_json;按 entry.delta_id find row in portfolio;调 `update_after_trial(row, success=entry.success, token_cost_delta=entry.token_cost_delta)` → new_row;`new_portfolio[i] = new_row`;return new_portfolio。journal 不存在 return 原 portfolio。

    `seers_harness/evolution/status_machine.py`:
    - `def wilson_lcb(success: int, total: int, *, z: float = 1.96) -> float`:Wilson 95% LCB 公式 — n=0 return 0;否则 `((p + z²/(2n)) - z·sqrt(p·(1-p)/n + z²/(4n²))) / (1 + z²/n)`
    - `def apply_status_transitions(portfolio: list[DeltaPortfolioRow], *, lcb_promote: float = 0.6, lcb_reject: float = 0.2, samples_promote: int = 5, samples_reject: int = 10, token_cost_p95_max: int = 2000) -> list[DeltaPortfolioRow]`:
      - 每行 compute lcb / token_cost_p95(若 sample_count==0 用 sum;否则 sorted token_costs[int(0.95 * len)] 近似 — 简化版)
      - status==`"experimental"`:lcb >= lcb_promote AND sample_count >= samples_promote AND token_cost_p95 <= token_cost_p95_max → promote `ready_for_review`
      - status==`"experimental"`:lcb <= lcb_reject AND sample_count >= samples_reject → demote `rejected`
      - 否则保持 status

    单测 `tests/test_portfolio_journal.py`:
    - `test_append_journal_entry_atomic`:并发 20 个线程 each append 10 entries,文件 line count == 200,无 corruption
    - `test_fold_portfolio_journal_replays_in_order`:portfolio 有 row delta_id="d1" sample=0;journal 3 entries: success/fail/success;fold 后 sample_count==3 success_count==2 fail_count==1
    - `test_fold_portfolio_journal_missing_journal_returns_original`:journal_path 不存在 → return 原 portfolio
    - `test_fold_portfolio_journal_unknown_delta_id_skipped`:journal entry delta_id 不在 portfolio → 跳过(不 raise)
    - `test_journal_entry_extra_fields_forbidden`:pydantic model_config extra="forbid";额外字段 raise

    单测 `tests/test_status_machine.py`:
    - `test_wilson_lcb_zero_total`:wilson_lcb(0, 0) == 0
    - `test_wilson_lcb_high_success`:wilson_lcb(95, 100) ≈ 0.89
    - `test_apply_status_transitions_promote`:row sample=10 success=8 alpha=9 beta=3 token_cost_p95=500 → status="ready_for_review"
    - `test_apply_status_transitions_reject`:row sample=15 success=2 alpha=3 beta=14 → status="rejected"
    - `test_apply_status_transitions_holds_when_insufficient_samples`:row sample=3 success=3(LCB ≈ 0.43)→ status 保持 experimental
  </behavior>
  <action>
    新建两个模块 + 两个测试文件。pydantic 用 `model_config = {"extra": "forbid"}`。journal append 用 `Path.open("a")` 默认 buffered text mode + 写 `\n` — POSIX 单行 < PIPE_BUF write 是 atomic。
  </action>
  <verify>
    <automated>pytest -q tests/test_portfolio_journal.py tests/test_status_machine.py -x 2>&1 | tail -20 ; grep -c "fold_portfolio_journal" seers_harness/evolution/portfolio_journal.py ; grep -c "apply_status_transitions" seers_harness/evolution/status_machine.py</automated>
    <human-check>9 测全绿;fold_portfolio_journal / apply_status_transitions 各 ≥ 1 def</human-check>
  </verify>
  <done>
    - portfolio_journal + status_machine 两模块完整
    - 9 单测全绿
    - 全套 pytest 不回归
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: trial_runner.run_request_baseline + 2 单测</name>
  <files>seers_harness/evolution/trial_runner.py, tests/test_trial_runner_baseline.py</files>
  <read_first>
    - seers_harness/evolution/trial_runner.py(`run_request_trial` 现有签名 + body;TrialOutcome 字段)
  </read_first>
  <behavior>
    在 `seers_harness/evolution/trial_runner.py` 新增:

    ```
    def run_request_baseline(
        *,
        runtime: WorkflowRuntime,
        scenario: dict,
        nodes: list,
        live_skill_root: Path,
        workspace_dir: Path,
        request_id: str,
        scenario_id: str,
        events: list[dict] | None = None,
    ) -> TrialOutcome:
        """Same shape as run_request_trial but patch=None — for paired control.

        Runs full DAG without any delta patch. TrialOutcome.trial_delta_id will
        be None. Used by runner.py:_run_one_request when select_trial_delta picks
        a delta_id — runs baseline + trial back-to-back on same scenario.
        """
        return run_request_trial(
            runtime=runtime, scenario=scenario, nodes=nodes,
            live_skill_root=live_skill_root, workspace_dir=workspace_dir,
            patch=None, request_id=request_id, scenario_id=scenario_id,
            events=events,
        )
    ```

    单测 `tests/test_trial_runner_baseline.py`:
    - `test_run_request_baseline_no_patch_returns_outcome`:fake provider + dummy DAG,跑 baseline,assert outcome.trial_delta_id is None,outcome.artifact_paths 三 node 各有 1
    - `test_run_request_baseline_does_not_modify_live_skill_root`:跑 baseline 后 live_skill_root 文件 byte-identical
  </behavior>
  <action>
    在 trial_runner.py 顶部 import 段下方,run_request_trial 函数旁加 run_request_baseline。
    新建 tests/test_trial_runner_baseline.py 2 测。
  </action>
  <verify>
    <automated>pytest -q tests/test_trial_runner_baseline.py -x 2>&1 | tail -15 ; grep -c "run_request_baseline" seers_harness/evolution/trial_runner.py</automated>
    <human-check>2 测全绿;run_request_baseline 在 trial_runner.py 出现 ≥ 1 def</human-check>
  </verify>
  <done>
    - run_request_baseline 函数加完
    - 2 单测全绿
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 5: runner.py:_run_one_request 替换 deterministic loop + 集成测试</name>
  <files>seers_harness/validation/runner.py, tests/test_validation_runner.py</files>
  <read_first>
    - seers_harness/validation/runner.py(`_run_one_request` line ~480-700 全文;特别 line ~634 的 deterministic for-loop 段)
    - seers_harness/evolution/delta_portfolio.py(select_trial_delta / belief_mean / update_after_trial 签名)
    - seers_harness/evolution/trial_signal.py(Task 1 产出)
    - seers_harness/evolution/uplift.py(Task 2 产出)
    - seers_harness/evolution/portfolio_journal.py(Task 3 产出)
    - seers_harness/evolution/status_machine.py(Task 3 产出)
    - seers_harness/evolution/trial_runner.py(Task 4 产出 run_request_baseline)
  </read_first>
  <behavior>
    `runner.py` 顶部 import 段加(line ~150-160 附近):

    ```
    from seers_harness.evolution.delta_portfolio import select_trial_delta, belief_mean
    from seers_harness.evolution.trial_signal import ProductionSignalWindow, concurrency_pressure
    from seers_harness.evolution.uplift import compute_uplift, TrialUplift
    from seers_harness.evolution.portfolio_journal import (
        PortfolioJournalEntry, append_journal_entry, fold_portfolio_journal,
    )
    from seers_harness.evolution.status_machine import apply_status_transitions
    from seers_harness.evolution.trial_runner import run_request_baseline
    import random
    import threading
    ```

    runner.py 顶部模块状态(line ~990 附近 `delta_portfolio` 初始化旁):

    ```
    _signal_window = ProductionSignalWindow(max_size=50)
    _signal_lock = threading.Lock()
    _inflight_counter = threading.BoundedSemaphore(value=20)  # mirror max_concurrent
    _trial_rng = random.Random(0)  # seed for determinism in tests; production reseed via env
    _DEFAULT_TOKEN_BUDGET_PER_REQUEST = 30000  # baseline observed avg ~25k from 0526 batch
    ```

    `_run_one_request` 替换 line ~634 的 deterministic for-loop(`for index, portfolio_row in enumerate(delta_portfolio):` 整段直到 `delta_portfolio[index] = update_after_trial(...)`)为新 trial gate 块:

    ```
    # === New trial gate (G4) ===
    applicable_surface = [n.skill_name for n in nodes]  # 本 request 实际跑的 skill names

    rfr = _signal_window.failure_rate()
    tbp = _signal_window.token_pressure(budget_per_request=_DEFAULT_TOKEN_BUDGET_PER_REQUEST)
    inflight_now = 20 - _inflight_counter._value  # approx; OK for signal
    pp = concurrency_pressure(inflight=inflight_now, max_concurrent=20)

    selected_delta_id = select_trial_delta(
        portfolio=delta_portfolio,
        applicable_surface=applicable_surface,
        recent_failure_rate=rfr,
        token_budget_pressure=tbp,
        production_pressure=pp,
        rng=_trial_rng,
    )

    if selected_delta_id is None:
        # baseline-only this request; record outcome to signal window
        baseline_outcome = ...  # the host request already ran above this gate; reuse its outcome shape
        record["trial_selected_delta_id"] = None
        _signal_window.record_baseline_outcome(
            success=(record.get("exception") is None),
            total_tokens=...  # sum from runtime.trace tool_loop_summary usage
        )
    else:
        # paired control on same scenario
        portfolio_row = next(r for r in delta_portfolio if r.delta_id == selected_delta_id)
        patch = _patch_from_portfolio_row(portfolio_row, live_skill_root)
        if patch is None:
            # G3 已 print trial_skipped 到 stderr;回退到 baseline-only
            _signal_window.record_baseline_outcome(success=..., total_tokens=...)
            record["trial_selected_delta_id"] = None
        else:
            trial_workspace = request_dir / "trial_workspace" / portfolio_row.delta_id
            try:
                baseline_workspace = request_dir / "trial_workspace" / "_baseline"
                baseline_outcome = run_request_baseline(
                    runtime=WorkflowRuntime(provider=proxy, output_dir=baseline_workspace / "_artifacts"),
                    scenario=scenario, nodes=list(nodes),
                    live_skill_root=live_skill_root, workspace_dir=baseline_workspace,
                    request_id=request_id, scenario_id=str(scenario.get("scenario_id", "")),
                    events=events,
                )
                trial_outcome = run_request_trial(
                    runtime=WorkflowRuntime(provider=proxy, output_dir=trial_workspace / "_artifacts"),
                    scenario=scenario, nodes=list(nodes),
                    live_skill_root=live_skill_root, workspace_dir=trial_workspace,
                    patch=patch, request_id=request_id,
                    scenario_id=str(scenario.get("scenario_id", "")), events=events,
                )
                uplift = compute_uplift(baseline_outcome, trial_outcome, budget_tolerance=1000)
                journal_entry = PortfolioJournalEntry(
                    request_id=request_id, delta_id=selected_delta_id,
                    success=uplift.is_positive, token_cost_delta=uplift.token_cost_delta,
                    behavioral_metric_lift=uplift.behavioral_metric_lift,
                    ts=_utc_now_iso(),
                )
                journal_path = out_dir / "portfolio_journal.jsonl"
                append_journal_entry(journal_path, journal_entry)
                record["trial_selected_delta_id"] = selected_delta_id
                _signal_window.record_baseline_outcome(
                    success=baseline_outcome.success,
                    total_tokens=baseline_outcome.token_cost_observed or 0,
                )
            except Exception as exc:
                # baseline / trial 异常上浮(D-19):auth/rate/transient → fail-fast;TrialFailure → trial_failed event by trial_runner
                raise
    ```

    `_run_stage` 在 stage 末尾(`return StageResult(...)` 之前)加 fold + status:

    ```
    journal_path = stage_dir.parent / "portfolio_journal.jsonl"
    if journal_path.exists():
        delta_portfolio[:] = fold_portfolio_journal(journal_path, delta_portfolio)
        delta_portfolio[:] = apply_status_transitions(delta_portfolio)
    ```

    `_run_stage` 把 `delta_portfolio` 参数从 `list[DeltaPortfolioRow]` 改为 `list[DeltaPortfolioRow]`(no change in type),但调用 fold 时用 `[:]` 切片 mutation 让 caller 拿到新 list。

    `run()` 函数把 `delta_portfolio` 全程作为 mutable list 维护,fold 在每 stage 末尾跑一次,最终 `apply_status_transitions` 在 batch 末尾再跑一次(确保 cross-stage journal 都被 fold 进去后做最后转移)。

    集成测试(追加到 `tests/test_validation_runner.py`):
    - `test_select_trial_delta_gate_skips_when_signals_high`:portfolio 含 1 row,signal_window 内置高失败率 record(模拟),run _run_one_request,assert record["trial_selected_delta_id"] is None
    - `test_select_trial_delta_gate_fires_paired_when_signals_low`:portfolio 含 1 row valid target_skill,fake provider 让 baseline 与 trial 都成功,跑 _run_one_request,assert trial_workspace/{_baseline,delta_id} 两 dir 都存在,journal_path 文件存在且含 1 entry
    - `test_fold_portfolio_journal_at_stage_boundary`:end-to-end fake-provider stage 跑 3 reqs 触发 1 trial,assert stage 末尾 portfolio[0].sample_count == 1
    - `test_apply_status_transitions_at_batch_end`:portfolio 经过 fold 后,有 1 row sample=10 success=8;batch 末尾应触发 promote → status_count("ready_for_review") == 1
  </behavior>
  <action>
    1. 顶部加 7 个 import + 4 个 module-level 状态变量。
    2. `_run_one_request` 删 line ~634 的 deterministic loop,换上述 trial gate 块(完整代码 ~50 行,在原 loop 位置)。
    3. `_run_stage` 末尾加 fold + status_transitions 调用。
    4. `run()` 全程维护 delta_portfolio mutable list 不变(已是这样),batch 末尾追加 1 次 apply_status_transitions。
    5. 集成测试 4 个追加。
  </action>
  <verify>
    <automated>pytest -q tests/test_validation_runner.py -k "select_trial_delta_gate or fold_portfolio_journal or apply_status_transitions" -x 2>&1 | tail -25 ; pytest -q 2>&1 | tail -5 ; grep -c "select_trial_delta(" seers_harness/validation/runner.py ; grep -c "run_request_baseline(" seers_harness/validation/runner.py ; grep -c "append_journal_entry(" seers_harness/validation/runner.py ; grep -c "fold_portfolio_journal(" seers_harness/validation/runner.py ; grep -c "apply_status_transitions(" seers_harness/validation/runner.py</automated>
    <human-check>4 集成测试全绿;全套 pytest 全绿(预期 ~340 tests after G1+G2+G3+G4);所有 5 个新函数在 runner.py 各出现 ≥ 1 次</human-check>
  </verify>
  <done>
    - deterministic loop 删除,select_trial_delta gate 落地
    - paired control(baseline + trial)在 trial 触发时跑
    - portfolio_journal append 到 per-batch jsonl
    - stage / batch 末尾 fold + status_transitions
    - 4 集成测试全绿
    - 全套 pytest 全绿
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| select_trial_delta ↔ ProductionSignalWindow | signal window 是 baseline-only,trial 不污染 — 防止正反馈 |
| append_journal_entry ↔ disk | POSIX O_APPEND 单行 < PIPE_BUF atomic;c=20 并发安全 |
| fold ↔ portfolio mutation | 单线程 in scenario boundary;mid-scenario 不写 portfolio |
| paired control ↔ token cost | 2x token / trial; trial_prob 通过信号收紧补偿 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-G4-01 | DoS | trial_prob 永远 1.0(信号都 0)→ 每 req 都跑 paired = 2x token | mitigate | cold-start < 10 baseline 接受 trial 必触发(早期 sampling 需要);稳态信号自然收紧 |
| T-08-G4-02 | Tampering | journal 行被部分写入(PIPE_BUF 越界)| mitigate | 单 entry JSON 长度 ~300 bytes < PIPE_BUF 4096;实际 atomic |
| T-08-G4-03 | Repudiation | trial / baseline 哪个先跑混淆 → 因果链不清 | mitigate | code 顺序固定:先 baseline 后 trial;test 覆盖 |
| T-08-G4-04 | Information Disclosure | journal 含 token_cost_delta 但不含 message 内容 | accept | journal 仅 metric,不含 LLM trace;evidence 单独路径 |
</threat_model>

<verification>
- pytest -q 全绿(预期 ~340 tests after G1+G2+G3+G4)
- grep gates(select_trial_delta / run_request_baseline / append_journal_entry / fold_portfolio_journal / apply_status_transitions 在 runner.py 各 ≥ 1)
- 06-02 orphan functions 不重写:`git diff seers_harness/evolution/delta_portfolio.py` 在 G4 commit 中只显示 import 行被引用(无函数体修改)
- 实测证据(post-batch G5):Stage 3 c=20 batch 至少 5/20 reqs trigger trial;evolution_snapshot.trials[] 非空;portfolio_journal.jsonl 至少 1 entry;至少 1 delta status 转移
</verification>

<success_criteria>
G4 ship 当且仅当:(a) 5 个新模块 / 函数全部接通;(b) deterministic loop 替换为 select_trial_delta gate + paired control + journal;(c) 06-02 orphan 函数全部 wired-through 不重写;(d) 信号源全部 runtime-observable;(e) pytest 全绿。Real-LLM 验证延后到 G5。
</success_criteria>

<output>
Create `.planning/phases/08-evolution-wiring-and-runner-debt/08-G4-SUMMARY.md` when done.
</output>
