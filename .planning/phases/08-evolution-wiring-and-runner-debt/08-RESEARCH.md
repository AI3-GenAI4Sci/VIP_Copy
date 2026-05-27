# Phase 08: 阶段研究 — Runner ↔ Evolution 接线 + Runner-Debt 清扫 + 阶段7实测硬化

**Phase:** 08-evolution-wiring-and-runner-debt
**生成时间:** 2026-05-27
**作者:** 主上下文研究(researcher 子代理两次上游断连后接管)
**消费者:** `gsd-planner`(产出 PLAN.md 集)、`gsd-pattern-mapper`、步骤 5.5(materialise VALIDATION.md)

> **范围红线**(由 `08-CONTEXT.md` 的 `<scope_fence>` 决定):
> 本研究 **不** 重新打开 Phase 7 验收讨论,**不** 重新设计 Phase 6 演化策略,**不** 修改 capture 层(`recording_provider` / `evidence_writer` / `machine_judges`)除了 E 项追加的 `failure_class` 列。所有结论都服务于在 `runner.py` 一次性扫掉 Groups A-G,然后让 Phase 7 的 Stage 1+2+3 实测能干净跑通。

---

## 1. 执行摘要

- **核心改动面积出乎意料地小。** 7 个文件被触碰,主战场是 `seers_harness/validation/runner.py`。所有外部接口(provider、`assemble_portfolio`、`run_request_trial`、`classify`)都已就绪,Phase 8 是把 *已经长好的零件* 用一根线连起来 + 顺手填几个洞,不是新设计。
- **不能 fail-fast 跳过实测层。** Phase 7 重新打开的根本原因就是 *单元/烟囱测试全绿但实测跑不通*。Phase 8 验收硬挂在一次 Stage 1+2+3 实测 batch 上(`D8-VAL-REAL`),pytest 通过只是必要条件、不是充分条件。计划每一个 Group 的任务都要给出 *它在哪条实测 trace 上被观察到 firing*,否则该任务无法 `completed`。
- **三组失败模式都有 0526 trace 锚点,可以精确根因追溯。**
  - 60s 超时:`.run-logs/runner-20260526T183141Z.log:76` `httpx.ReadTimeout → ProviderTransientError`
  - shell-env 漂移:`.run-logs/runner-20260526T174546Z.log:25` `401 Authentication Fails, ****92c7`
  - tool_args 截断:`07-VERIFICATION.md` 记录的 Stage 2 req2 第 940 char `evidence_refs:` 截断
- **每组最高风险:**
  - Group 1 高风险 = **D**(`--env-file`,安全敏感:绝不能把 key 写日志);
  - Group 2 高风险 = **F 种子 delta 选择**(选错 → `token_cost_observed` 仍然是 0 → 验收 ACC-2 不成立);
  - Group 3 高风险 = **WR-05**(过早收紧 `except Exception` 可能在 F 真正接线之前掩盖接线 bug — 见 §7 测序复核)。
- **测序 *已锁* 但需要一处微调:** 在 F 落地 *之前* 不要执行 WR-05。详见 §7。

---

## 2. Group 1 — 实测硬化(A-E)

### A. 超时默认 60s → 180s

**修改点:** `seers_harness/provider_runtime/openai_compatible.py:141`

```python
# 当前(D-03 + D-22):
timeout = timeout_seconds if timeout_seconds is not None else float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "60"))

# 目标:
timeout = timeout_seconds if timeout_seconds is not None else float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "180"))
```

同步更新 `deepseek_runtime_facts()` 第 131 行 `"default_timeout_seconds": 60` → `180`(此函数被 PROD-02 fact-recording 探针读)。

**测试锚点:**
- 现有:`tests/test_provider_openai_compatible.py`(grep `DEEPSEEK_TIMEOUT_SECONDS` 或 `deepseek_runtime_facts`)。
- 新增:断言 `deepseek_provider_from_env()` 不设 env 时 `provider.client.timeout == 180.0`。

**实测证据(D8-VAL-REAL):**
- *证明 A 生效的最低标准*:Phase-8 batch 的某一个请求 trace 显示 TTFB 在 60s-180s 之间,且该请求成功而非以 `ProviderTransientError(APITimeoutError)` fail-fast。
- 数据位置:`tests/smoke/.runs/<phase-8-ts>/stage{N}/<rid>/evidence/<node>/usage.json` 的请求总耗时,以及 `index.json` `exception == null`。
- 对照锚点:`.run-logs/runner-20260526T183141Z.log:76`(60s 默认下该请求在 60s 处死了)。

**陷阱:**
- 不要把 180 写成同一行的 magic number。`runtime_facts` 和 `deepseek_provider_from_env` 用同一个常量来源(可以新增一个 `_DEFAULT_TIMEOUT_SECONDS = 180` 模块级常量),避免 future drift。
- 不影响 `OpenAI` SDK 内部的 *connect* 超时;DeepSeek beta 在 TLS 握手阶段从未观察到 >5s。

### B. 请求级 transient 重试

**修改点:** `seers_harness/validation/runner.py:425-535` `_run_one_request` 体内 *或* 其调用点的薄层(更倾向于 *调用点的薄层*,见下方陷阱)。

**目标行为:**
- 仅在 `ProviderTransientError` 上重试。`ProviderAuthError` / `ProviderRateLimitError` / `ProviderResponseError` / `TrialFailure` / `SchemaError` / `AssertionError` 一律不重试,沿用 D-02 / D-19。
- 重试预算 = 2 次额外尝试(总共 3 次)。
- 回退序列 = 5s, 15s(常量化,不要硬编码进 sleep 调用)。
- D-03 不变:SDK 侧 `max_retries=0` 默认值保持,这是 *请求级* 重试不是 *HTTP 级* 重试。

**伪代码(推荐:wrapper 函数而非 `_run_one_request` 内层 `try/except` 循环):**

```python
_REQUEST_TRANSIENT_BACKOFFS = (5.0, 15.0)  # 两次额外尝试

def _run_one_request_with_transient_retry(**kwargs) -> dict:
    last_exc: ProviderTransientError | None = None
    for attempt, backoff in enumerate([0.0, *_REQUEST_TRANSIENT_BACKOFFS]):
        if backoff > 0:
            time.sleep(backoff)
        try:
            return _run_one_request(**kwargs)
        except ProviderTransientError as exc:
            last_exc = exc
            print(f"[runner] req {kwargs['request_id']} transient (attempt {attempt+1}/3); backoff={_REQUEST_TRANSIENT_BACKOFFS[attempt] if attempt < 2 else 'none'}", file=sys.stderr)
            continue
    assert last_exc is not None
    raise last_exc
```

调用点:`_run_stage` 内的 `record = _run_one_request(...)` 改成 `record = _run_one_request_with_transient_retry(...)`,并发分支(`pool.submit(_run_one_request, ...)`)同样改为 submit wrapper。

**测试锚点:**
- 现有:`tests/test_validation_runner.py` 必须有 `provider_factory` 注入故障注入 provider 的模式 —— 沿用之。
- 新增:
  - `test_runner_retries_transient_twice_then_succeeds` —— 注入一个 provider 前 2 次 raise `ProviderTransientError`、第 3 次成功 → 整个请求 record 成功,无 fail-fast。
  - `test_runner_does_not_retry_auth_error` —— 注入 `ProviderAuthError` → 第一次就 fail-fast,无第二次 attempt。
  - `test_runner_exhausts_transient_budget` —— 注入连续 3 次 transient → fail-fast 路径走 D-19 `provider_error`。
  - 监视:5s + 15s 回退总和 = 20s,Stage 3 c=20 的 worst case 增量 ≤ 20s × 20 = 400s,可接受。

**实测证据:**
- 计划应包含一个 **故障注入实测请求**(在 batch 中标注 `fault_inject=true`,使得它不计入"honest"通过率),以便保证 transient 路径在 phase-8 batch 中至少 firing 过一次。理由:`.run-logs/runner-20260526T183141Z.log:125` 显示真实 transient 不一定每次 batch 都自然出现;不主动注入就可能没证据。
- 自然 transient 出现时:`.run-logs/runner-<phase-8-ts>.log` 含 `transient (attempt N/3); backoff=Ns` 文本 + 最终请求成功(或 budget 耗尽 fail-fast)。

**陷阱:**
- *不要* 在 `_run_one_request` 的 `try:` 块内部加 retry —— `finally:` 块(flush_evidence + write_evolution_snapshot)每次重试会重复 flush,文件被覆盖。Wrapper 在 `_run_one_request` 外面才能保证 evidence 只 flush 最后一次的状态。
- *不要* 把 `time.sleep` 写在 wrapper 内部 *且* 让它阻塞 ThreadPool worker —— sleep 期间该 worker 不能 progress 其他请求。Stage 3 c=20 的并发模型可以容忍(每个 worker 独立),但要在测试里 mock `time.sleep` 否则单测会真睡 20s。
- *不要* 把 wrapper 移到 `_run_stage` 的 future submission 之外(批级)—— Stage 3 的并发模型要求每个请求独立。Wrapper 必须按 *请求* 包,不能按 batch 包。

### C. CR-05 审计(verify-only)

**这不是代码修改任务,是"读 trace 然后判定"的审计任务。**

**前置:** Phase-8 batch 必须至少包含 1 个 `tool_call.arguments` 截断事件。如果 Stage 1+2+3 自然 batch 中未出现截断,则等待直至自然出现(*不要* 主动注入截断 —— CR-05 路径已经在 `openai_compatible.py:73-103` 落地,审计就是确认它在 *真实* DeepSeek 截断面前的行为,故障注入证明不了这一点)。

**审计步骤(planner 应写成一个 task 的 `<action>`):**
1. 在 phase-8 batch 的 `.run-logs/runner-<ts>.log` 中搜索 `parse_retry` 文本(`openai_compatible.py:_parse_max_retries` 控制的循环,目前没有显式 log 行 —— 见下方陷阱)。
2. 如果未观察到 `parse_retry` 文本但 batch 中确实出现了截断:这是 *审计失败信号 1* —— `openai_compatible.py:73-103` 没有打 log,审计无法用 log 验证。需要 **新增一条 log**(单行,审计性质,非业务变更):在 `except ProviderResponseError as exc:` 分支添加 `print(f"[provider] parse_retry node={node_id} attempt={_attempt+1}/{_parse_max_retries()+1}", file=sys.stderr)`。这一行视为 C 项的 *附带修改*,并在 task 注释里标明"为了让审计本身可观测"。
3. 审计通过判定:
   - (a) batch 中至少 1 个请求的 trace 显示截断;
   - (b) 该请求最终返回了 valid `tool_calls_out`(`openai_compatible.py:93-101` 的 `return` 分支被命中)或在 budget 耗尽后 raise 了 `ProviderResponseError`(`:102-103` 的 `raise last_parse`);
   - (c) D-19 路由把 `ProviderResponseError` 标 `provider_error` → fail-fast(`exception_classifier.py:90-95`),而不是默默吞掉。
4. 审计失败时:不要在 phase 8 修补,记录到 `08-VERIFICATION.md` 的 Findings,作为新 WR/IN 项归档,phase 8 仍以"审计完成"收尾。

**实测证据:** 见审计步骤 (a)(b)(c)。

**陷阱:**
- *不要* 把 `_parse_max_retries` 默认值从 3 改成更大 —— D-22 / CR-05 已经定型,审计不动 contract。
- C 项是 *唯一* 在 phase 8 内"可以接受不修代码"的 deliverable;但它有一个 *显式* 失败出口(发现真问题 → 新 WR 项),不是"看一眼就过"的 cargo cult。

### D. Runner `--env-file <path>` 标志

**修改点:** `seers_harness/validation/runner.py:823-871` `main` argparse 块 + `_run_stages` 之前的 env 加载块。

**目标行为:**
- 新 CLI 参数:`--env-file PATH`(optional,default `None`)。
- 当提供时,在 *构造任何 provider 之前* 解析文件:
  - 接受格式:`KEY=VALUE` 每行一条,允许空行,允许 `#` 开头的整行注释(不允许行内 `#` —— 简单优先)。
  - 不做 shell expansion(不展开 `$VAR`、不去 quote 包裹)。
  - 文件不存在 → `RuntimeError` 退出码非 0。
- merge 进 `os.environ`:**只覆盖** 当前 process 未设置的 key,以保留 CI 时手动设的 env;*或* **覆盖所有**(下方决策)。
- 日志输出 *仅* 两行:
  - `[runner] env-file: loaded N keys from <path>` (N = 实际 merge 进去的 key 数)
  - `[runner] env-file: DEEPSEEK_API_KEY suffix=****<last4>` (只展示最后 4 字符)
- **绝对禁止** 把 value 写日志,即使是 INFO 级别 ——`safe_exc` 这种 trace 也不行。

**Env merge 策略决策:**
- **推荐"覆盖":** 文件优先于已有 env。理由:`D8-CONTEXT` 的 D8-D 明确要"消除 stale shell env"故障模式 —— 如果用户 shell 中还有过期 key,我们以文件为权威。命令行场景就是为了 *不再依赖* `export`,不能让 stale `export` 反过来 override 文件。
- 但要 **保留一个 escape hatch**:如果文件不含某个 key,该 key 的现有 env 值保留。这是最自然的 merge。

**伪代码:**

```python
def _load_env_file(path: Path) -> int:
    """Parse KEY=VALUE lines, merge into os.environ. Return count of merged keys."""
    if not path.exists():
        raise RuntimeError(f"--env-file path not found: {path}")
    merged = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        # 不做 shell expansion;不剥 quote
        os.environ[key] = value
        merged += 1
    return merged

# main() 内,argparse 解析后,run() 调用前:
if args.env_file is not None:
    count = _load_env_file(args.env_file)
    suffix = os.environ.get("DEEPSEEK_API_KEY", "")[-4:] if os.environ.get("DEEPSEEK_API_KEY") else "<unset>"
    print(f"[runner] env-file: loaded {count} keys from {args.env_file}", file=sys.stderr)
    print(f"[runner] env-file: DEEPSEEK_API_KEY suffix=****{suffix}", file=sys.stderr)
```

**测试锚点:**
- 新增:
  - `test_env_file_overrides_existing_env` —— monkeypatch.setenv("FOO", "old") + 写 tmp 文件含 `FOO=new` → 加载后 `os.environ["FOO"] == "new"`。
  - `test_env_file_does_not_log_values` —— capsys 检查 stderr 不含 value 字符串,只含 `loaded N keys` 和 `suffix=****<4chars>`。
  - `test_env_file_handles_comments_and_blank` —— 文件含 `#`、空行、`FOO=bar` → 只 merge 1 key。
  - `test_env_file_missing_raises` —— path 不存在 → `RuntimeError`。
  - `test_env_file_no_shell_expansion` —— `BAR=$FOO` → `os.environ["BAR"] == "$FOO"` 字面值。

**实测证据:**
- 唯一证据:phase-8 batch 必须用 `python -m seers_harness.validation.runner --env-file .env.local ...` *无 shell `export`* 启动,运行日志中两行 `env-file:` log 应该出现,且 `DEEPSEEK_API_KEY` 后 4 字符与 `.env.local` 当时的值一致。
- 对照锚点:`.run-logs/runner-20260526T174546Z.log:25` `****92c7` 401 fail —— phase-8 batch 不应该再出现 stale suffix mismatch。

**安全陷阱(逐项检查清单):**
- 不在任何 `traceback.print_exc` / `safe_exc` 输出里间接泄露 value(`_secrets.safe_exc` 已处理 provider error 中的 key,但 `--env-file` 路径下的错误也要走 `safe_exc`)。
- 不把 `args.env_file` 路径本身写进 `index.json` / `batch_summary.json` —— path 本身可能含 PII(如 `/home/<user>/.env.local`)。Path 仅写到 stderr log,且只在 runner 进程内部。
- 不支持 nested env files(`SOURCE_OTHER_ENV=other.env`)—— scope creep。
- 不解析 `export FOO=bar` shell 语法 —— scope creep,且会让"不做 shell expansion"原则模糊。

### E. `failure_class` 列 + 聚合

**修改点 1:** `seers_harness/validation/exception_classifier.py` 新增一个 `failure_class(exc)` 函数(*不要* 修改现有 `classify(exc)` —— D-19 的 3 标签 contract 锁定不动)。

```python
# 新增,与 classify 并列:
def failure_class(
    exc: BaseException | None,
) -> Literal["auth", "rate_limit", "transient", "malformed_tool_args", "schema_violation", "runner_bug", "ok"]:
    """E 项:细粒度 failure 分类,用于 index.json 一列展示。

    与 classify(exc) 并存;classify 决定 fail-fast 路由(3 标签),
    failure_class 决定可读性聚合(7 标签)。

    None / 成功 → "ok"。
    """
    if exc is None:
        return "ok"
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, ProviderAuthError):
            return "auth"
        if isinstance(cur, ProviderRateLimitError):
            return "rate_limit"
        if isinstance(cur, ProviderTransientError):
            return "transient"
        if isinstance(cur, ProviderResponseError):
            return "malformed_tool_args"
        # SchemaError 不在 core/errors 里 —— 是 pydantic.ValidationError
        from pydantic import ValidationError as _PydanticVE
        if isinstance(cur, _PydanticVE):
            return "schema_violation"
        cur = cur.__cause__ or cur.__context__
    return "runner_bug"
```

**注意:** `08-CHARTER.md` 写的是 `SchemaError` —— 但 grep 全 repo 发现没有显式名为 `SchemaError` 的类。`pydantic.ValidationError` 是 schema 校验失败时实际抛的类型(`runner.py:484, 513` 调用 `model_validate`),映射应当指向它。这是 RESEARCH 阶段发现的 *charter 文本与代码的微小漂移*,planner 应在 PLAN 任务中明确 `SchemaError == pydantic.ValidationError` 的 alias 决策。

**修改点 2:** `seers_harness/validation/runner.py` `_run_stage` 在构建 `fail_record` 时附加 `failure_class`:

```python
# 当前:
fail_record: dict[str, Any] = {
    "node_id": _safe_request_dirname(rid),
    "request_id": rid,
    "artifact": None,
    "reflow_triggered": False,
    "trial_selected_delta_id": None,
    "exception": safe_exc(exc),
}
# 目标:在 dict 中加一行
"failure_class": failure_class(exc),  # E
```

成功路径下,`_run_one_request` 返回的 record 也加 `"failure_class": "ok"`。

**修改点 3:** `seers_harness/validation/index_writer.py` `write_index` 在 row dict 中加一行:

```python
row["failure_class"] = record.get("failure_class", "ok") if isinstance(record, dict) else "ok"
```

**修改点 4:** `seers_harness/validation/batch_summary_writer.py` 聚合块新增 `by_failure_class` dict:

```python
# totals 块附近:
by_failure_class: dict[str, int] = {}
for row in rows:
    cls = row.get("failure_class", "ok")
    by_failure_class[cls] = by_failure_class.get(cls, 0) + 1

# summary dict 顶层添加:
"by_failure_class": by_failure_class,
```

**测试锚点:**
- 新增 `test_failure_class_mapping.py`:每个枚举值至少一个 isinstance case + `runner_bug` default case + cause-chain 包裹的 `RuntimeError(ProviderAuthError) → "auth"` case。
- 修改 `test_index_writer.py` 断言 row 含 `failure_class` key。
- 修改 `test_batch_summary_writer.py` 断言 summary 含 `by_failure_class` key,且各 value 之和等于 `totals.requests`。

**实测证据:**
- Phase-8 batch 的 `index.json` 每个 row 都有 `failure_class` 字段。
- `batch_summary.json` 的 `by_failure_class` dict 的 value 之和 = `totals.requests`(完整性自校验)。
- 如果 batch 全成功:`by_failure_class == {"ok": 20}`(Stage 2 / Stage 3)和 `{"ok": 1}`(Stage 1)。
- 如果 batch 含故障注入的 B 项(transient → 最终成功):仍记 `"ok"`(failure_class 看的是 *最终* outcome);如果 transient budget 耗尽:`"transient"`。

**陷阱:**
- *不要* 把 `failure_class` 加到 capture 层(`recording_provider` / `evidence_writer`)—— D-22d 禁止。它属于 writer 层。
- *不要* 把 `failure_class` 加到 `classify(exc)` 返回值 —— 那是 D-19 的 3 标签 contract,锁定。新函数并列共存。

---

## 3. Group 2 — Runner ↔ 演化接线(F)

### 3.1 `_run_one_request` 当前形状

`seers_harness/validation/runner.py:425-535`,80 行函数。当前职责:
1. 用 `provider_factory()` 构造一个 fresh inner provider。
2. 用 `RecordingProvider` proxy 包装,attach `request_log: list[dict]`。
3. 构造 `WorkflowRuntime(provider=proxy, output_dir=request_dir/_artifacts)`。
4. `runtime.run_request(scenario=scenario, nodes=list(nodes))` 跑 3-node DAG。
5. 解析 `factor_discovery` artifact,promote first factor 进 record["artifact"]。
6. 校验 `copy_generation` + `personalized_copy_rubric` artifacts(pydantic `model_validate`)。
7. `finally:` 块:
   - `_cv.reset(token)`(WR-04 callsite)
   - `flush_evidence(request_log, evidence_dir)`
   - `write_evolution_snapshot(events, request_dir / "evolution_snapshot.json")`

**关键观察:**
- `events` 参数已经存在(`runner.py:432`),由 caller `_run_stage` 创建 `events: list[dict] = []`,目前 *被传入但从未被 append*。
- `write_evolution_snapshot` 在 `finally` 中调用,这意味着即使 `run_request` raise,*已经收集的 events* 也会被 flush。F 接线产生的 `portfolio_assembled` / `trial_started` / `trial_succeeded` / `trial_failed` events 都会自动落盘。
- `_delta_portfolio_empty: list[Any] = []`(`runner.py:786`)是 D-18 锚点 —— phase 8 的 F 项需要把这个空 list 替换成一个含 *seed delta* 的非空 list。

### 3.2 `assemble_portfolio` / `run_request_trial` 接口

**`assemble_portfolio`**(`seers_harness/evolution/delta_portfolio.py:395-450`):
- 入参:`existing_portfolio: list[DeltaPortfolioRow]`, `new_proposals: list[DeltaProposal]`, `events: list[dict] | None = None`
- 出参:新的 `list[DeltaPortfolioRow]`(merge,delta_id 去重)
- 副作用:当 `events is not None` 时 append 一个 `{"type": "portfolio_assembled", ...}` event。
- **F 接线场景:** 我们在 process start 时 *已经* 构造好 portfolio(单个 seed delta);每次请求开始时调用 `assemble_portfolio(seed_portfolio, [])` 仅用于产生 `portfolio_assembled` event。或者:跳过此调用,直接调用 `run_request_trial`。**推荐:** 跳过 —— `assemble_portfolio` 是 *演化 distillation* 的合并点,phase 8 不做 distillation,无新 proposals,没必要每请求 emit `portfolio_assembled`。该事件应该每 *batch* 一次,在 `_run_stage` 启动时由 runner emit。

**`run_request_trial`**(`seers_harness/evolution/trial_runner.py:155-255`):
- 入参签名:
  ```python
  run_request_trial(
      *,
      runtime: WorkflowRuntime,
      scenario: Any,
      nodes: list[NodeSpec],
      live_skill_root: Path,
      workspace_dir: Path,
      patch: SkillDeltaPatch | None = None,
      request_id: str = "",
      scenario_id: str = "",
      events: list[dict] | None = None,
  ) -> TrialOutcome
  ```
- 行为:
  - 创建 `temp_root = workspace_dir / "skills"`,把 `live_skill_root` 复制进去
  - 若 `patch is not None`:校验 hash + 写 replacement_text 到 temp 副本
  - 调用 `runtime.run_request(scenario=scenario, nodes=nodes)`(在 temp 上下文中)
  - 异常时 outcome.success=False,success 时收集 `tool_call_count`(从 `runtime.trace` 里的 `tool_loop_summary` events)
  - 当 `events is not None`:append `trial_started` → (`trial_succeeded` | `trial_failed`)
- **重要:** `run_request_trial` 本身 *复制整个 skill root*。Stage 3 c=20 时这意味着 20 个并发请求 × 复制整个 `workflow-skills/current/`(20 个目录,目前 ~3 个 SKILL.md 每个 < 200 行 + 多个 handler 文件)。`shutil.copytree` 不是 cheap operation,但远低于一次 DeepSeek round-trip(秒级 vs 分钟级)—— OK。
- **关键:** `token_cost_observed` 字段默认 0,目前 *没人写它*。这是 IN-01 的死字段。F 接线 *不负责* 让它非零,IN-01 才负责(见 §4-IN-01)。

### 3.3 `events` 流向 `evolution_snapshot.json`

`seers_harness/validation/evolution_snapshot.py` 的 `write_evolution_snapshot(events, path)`:
- 输入:per-request `events: list[dict]`。
- reducer 行为(根据 07-01 SUMMARY):
  - 提取所有 `trial_*` 事件 → `trials: list[dict]`
  - 提取 `portfolio_assembled` 事件(如果有)→ `portfolio` 字段
  - 提取 `reflow_*` 事件(如果有)→ `reflow_events`
- **F ACC-2 要求:** `trials[]` 非空。这意味着 `events` 必须含至少一个 `trial_started` + 一个 `trial_succeeded`(或 `trial_failed`)对。
- `run_request_trial` 内部已经 append 这些 event(`trial_runner.py:204-212, 229-242, 247-254`)—— F 接线只需要 *实际调用* `run_request_trial` 并传入 `events=events` 即可。

### 3.4 种子 delta 选择 — 候选与决策

**Constraint(charter Q1 + D8-VAL-REAL):** seed delta 必须使 `TrialOutcome.token_cost_observed > 0`(或者至少让 `trials[]` 非空可观测)。No-op patch 不满足 charter 用户的"实际工作"要求。

**Candidates 调研:**

`grep -rn 'DeltaProposal\|target_skill' tests/ workspace-skills/` 找现成 delta fixtures:

| 候选 | 来源 | target_skill | proposed_change 性质 | `token_cost_observed > 0`? |
|---|---|---|---|---|
| C1 | 测试 fixture:`tests/test_trial_runner_smoke.py` 的 patch(若存在)| 某个 SKILL.md | 通常是 marker text 插入 | 由 IN-01 决定;F 项本身让 trial fire 即可 |
| C2 | `.planning/intel/decisions.md` 中描述的 P-10/P-11 修订意图 | `discover-personalization-factors/SKILL.md` | "在 transferable_disposition 描述中插入一句强化用户信号去映射的句子" | 真实 prompt-level 改动,token cost 可能微增 |
| C3 | 手工构造一个 minimal 真 delta:在 `generate-copy-candidates/SKILL.md` 第 1 行后插入一个空注释 | `generate-copy-candidates/SKILL.md` | `"<!-- phase-8 seed trial -->\n" + 原文` | Token cost 极小但非 0(skill bundle 多了 ~20 token);trial fires |

**推荐:C3。** 理由:
1. 不依赖任何外部 fixture(测试 fixture 可能不存在或与 phase 6 测试耦合)。
2. *最小语义改动* —— 只插入一个 HTML 注释,运行时行为不会因为这个注释而出现 quality 波动,这意味着 trial outcome 的 `success` 标记可信反映 *runner 是否正确接线*,不被 prompt 漂移污染。
3. token_cost > 0 由 IN-01 接线保证(本项 only 负责"让 trial fire"),C3 满足 trials[] 非空的弱约束。

**位置:** 在 `runner.py` 的 `run()` 函数中,`_delta_portfolio_empty: list[Any] = []`(line 786)替换为:

```python
# F 接线:phase 8 种子 delta。Phase 6 演化设计要求 delta_portfolio 起始为空(D-18),
# 但 phase 7 acceptance ACC-2 要求 trials[] 非空。一颗 seed 同时满足两者:
# delta_portfolio 起始空 → 此处 *附加* 一颗 seed → portfolio 有 1 个 row。
from seers_harness.evolution.delta_portfolio import DeltaProposal, assemble_portfolio
from seers_harness.evolution.trial_runner import SkillDeltaPatch, sha256_of_text

_SEED_TARGET = "generate-copy-candidates/SKILL.md"  # 相对 live_skill_root
_live_skill_root = Path(__file__).resolve().parents[2] / "workspace-skills" / "current"  # 验证路径,可能需调整
_original_text = (_live_skill_root / _SEED_TARGET).read_text(encoding="utf-8")
_seed_patch = SkillDeltaPatch(
    target_path=_SEED_TARGET,
    original_text_sha256=sha256_of_text(_original_text),
    replacement_text="<!-- phase-8 seed trial -->\n" + _original_text,
)
# delta_portfolio 起始非空(F 接线种子)
_seed_proposal = DeltaProposal(
    delta_id="phase-8-seed-001",
    target_skill=_SEED_TARGET,
    change_type="modify_skill",
    observation="phase-8 seed delta for evolution wiring smoke",
    proposed_change="prepend HTML comment marker",
    evidence_refs=[{"path": "08-CONTEXT.md#D8-F2", "snippet": "seed delta"}],
    applicable_surface=[_SEED_TARGET],
    failure_types=[],
)
_initial_portfolio = assemble_portfolio([], [_seed_proposal])
# 注:_initial_portfolio 现在含 1 个 DeltaPortfolioRow
```

**Planner 注意:** 上述路径 `workspace-skills/current/` 需要 planner 在写 PLAN 任务 `<read_first>` 时 *先 grep 确认* —— 当前 repo 的 skill root 实际在 `workflow-skills/current/`(已 verified):

```
$ ls workflow-skills/current/
discover-personalization-factors/SKILL.md
generate-copy-candidates/SKILL.md
personalized-copy-rubric-judge/SKILL.md
```

修正 `_live_skill_root` 应该指向 `workflow-skills/current/` 而非 `workspace-skills/current/`。这是 RESEARCH 阶段发现并校正的一处路径细节。

### 3.5 F 接线伪代码

```python
# _run_one_request 接收一个新参数 delta_portfolio_for_trial:
def _run_one_request(
    *, request_id, scenario, nodes, provider_factory, request_dir,
    events: list[dict],
    delta_portfolio: list[DeltaPortfolioRow] = (),  # F 新增
    live_skill_root: Path,                          # F 新增
) -> dict:
    inner_provider = provider_factory()
    request_log: list[dict] = []
    proxy = RecordingProvider(inner_provider, request_log)
    request_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = request_dir / "_artifacts"
    runtime = WorkflowRuntime(provider=proxy, output_dir=artifacts_dir)
    record = {... existing fields ..., "failure_class": "ok"}  # E

    token = set_current_node_id(request_id)
    try:
        # F 接线:host request 跑常规路径
        result_paths = runtime.run_request(scenario=scenario, nodes=list(nodes))
        # ... 现有 artifact 解析逻辑 ...

        # F 接线:host 成功后,对 portfolio 中每个 row 跑一次 trial
        for portfolio_row in delta_portfolio:
            from seers_harness.evolution.trial_runner import run_request_trial, SkillDeltaPatch
            patch = _patch_from_portfolio_row(portfolio_row, live_skill_root)
            trial_workspace = request_dir / "trial_workspace" / portfolio_row.delta_id
            trial_outcome = run_request_trial(
                runtime=WorkflowRuntime(provider=proxy, output_dir=trial_workspace / "_artifacts"),
                scenario=scenario,
                nodes=list(nodes),
                live_skill_root=live_skill_root,
                workspace_dir=trial_workspace,
                patch=patch,
                request_id=request_id,
                scenario_id=str(scenario.get("scenario_id", "")),
                events=events,  # ← trial_started / trial_succeeded events 都 append 进同一个 events list
            )
            # 把 outcome 的 delta_id 浮到 record(D-10 列)
            if trial_outcome.trial_delta_id is not None:
                record["trial_selected_delta_id"] = trial_outcome.trial_delta_id
    finally:
        # existing finally: _cv.reset, flush_evidence, write_evolution_snapshot
        ...
    return record
```

**`_patch_from_portfolio_row`** 是一个新 helper:从 portfolio row(`target_skill` + `proposed_change`)读 live file 算 sha → 构造 `SkillDeltaPatch`。或者更简单:在 process start 时和 `_seed_proposal` 一起构造 `SkillDeltaPatch` 并把它 *直接挂在 portfolio row* 之外作为旁路。两种都可行,planner 选 simpler 一种。

**`_run_stage` 调用点更新:**
```python
record = _run_one_request_with_transient_retry(  # B 包裹
    request_id=rid,
    scenario=scenario,
    nodes=nodes,
    provider_factory=provider_factory,
    request_dir=request_dir,
    events=events,
    delta_portfolio=delta_portfolio,    # F 接线传入
    live_skill_root=live_skill_root,    # F 接线传入
)
```

`run()` 函数需要把 `delta_portfolio` 和 `live_skill_root` 一路传到 `_run_stage` 再传到 `_run_one_request`。

### 3.6 F 接线测试锚点

- 现有:`tests/test_trial_runner_smoke.py`(如果存在)—— 模拟 portfolio 中 1 颗 delta,跑一个请求,断言 `events` 含 `trial_succeeded`,outcome.success=True。
- 新增:
  - `test_runner_fires_trial_when_portfolio_nonempty` —— inject seed portfolio + fake provider → 跑 1 个请求 → `evolution_snapshot.json` 解析后 `trials` 列表非空。
  - `test_runner_skips_trial_when_portfolio_empty` —— inject empty portfolio → `trials` 列表为空,host request 仍成功(D-18 保护)。
  - `test_runner_trial_failure_does_not_abort_host` —— inject portfolio + provider 在 trial 中 raise → host record.exception is None, evolution_snapshot 含 `trial_failed`。
  - `test_seed_patch_hash_validation_drift` —— modify live skill file → seed patch hash mismatch → process start 时 raise(fail-fast on stale phase-8 fixture)。

### 3.7 F 接线实测证据

**ACC-2 verbatim:** `evolution_snapshot.json` 含至少 1 个非空 `trials[]`。

Phase-8 batch 完成后:
```bash
find tests/smoke/.runs/<phase-8-ts>/ -name evolution_snapshot.json \
  -exec python -c "import sys,json; d=json.load(open(sys.argv[1])); print(sys.argv[1], 'trials:', len(d.get('trials',[])))" {} \;
```
期望:每个请求(20 + 20 + 1 = 41 个请求 across 3 stages)的 snapshot 都有 `trials: 1`(seed delta 每个请求都试一次)或 `trials: 0`(如果 planner 决定 trial cadence 按 N 个 host requests 一次)。**至少一个 stage 的至少一个请求 trials 数 > 0** 是 ACC-2 的最低门槛。

---

## 4. Group 3 — Runner-Debt(G)

### WR-01 — Stage 3 fail-fast 在退出前 drain in-flight futures

**当前**(`runner.py:679-683`):
```python
records.append(fail_record)
failure_exc = exc
print(... "fail-fast", file=sys.stderr)
traceback.print_exc(file=sys.stderr)
# Cancel the remaining futures (best-effort) and break — partial artifacts on disk are kept.
for other in future_to_rid:
    other.cancel()
break
```

`future.cancel()` 仅取消 *未开始* 的 future;已经在跑的 worker 会继续(`concurrent.futures.Future.cancel` 文档原话)。结果:`index.json` 记录 `n=20` 但 disk 上可能有 19 个或 21 个 request_dir(20 个 submit 完成 + 1 个仍在跑随后失败),WR-01 的"disk-vs-index 不一致"由此而来。

**目标:**
- `cancel()` 后,*等待已运行* 的 future complete(或抛出),收集这些 future 的 record(无论成功失败)再 break。
- 已经 fail-fast 的失败原因 `failure_exc` 已记录,新增的 in-flight 完成不应覆盖它。

**伪代码:**
```python
# 替换 cancel + break:
records.append(fail_record)
failure_exc = exc
print(... "fail-fast", file=sys.stderr)
traceback.print_exc(file=sys.stderr)
# WR-01: drain in-flight futures so disk and index.json agree.
# 1) 取消未开始的(已经在跑的不能 cancel)
remaining = [f for f in future_to_rid if not f.done()]
for f in remaining:
    f.cancel()
# 2) 等已开始未完成的跑完,收集其 record(成功/失败一律记)
for f in as_completed(remaining):
    rid_drain = future_to_rid[f]
    if f.cancelled():
        continue  # 未开始的,disk 上也没有 artifact
    try:
        record = f.result()
        records.append(record)
    except BaseException as drain_exc:
        records.append({
            "node_id": _safe_request_dirname(rid_drain),
            "request_id": rid_drain,
            "artifact": None, "reflow_triggered": False,
            "trial_selected_delta_id": None,
            "exception": safe_exc(drain_exc),
            "failure_class": failure_class(drain_exc),  # E
        })
break
```

**实测证据:** 在 phase-8 batch 中 *若 Stage 3 自然 fail-fast*:验证 `len(index.json["requests"]) == 20`(在 c=20 配置下),且 disk 上的 `stage3/<rid>/` 目录数 = 20。**自然 fail-fast 可能不发生**,所以 WR-01 的实测证据是 **可选**:planner 应在 PLAN 中标注"若 Stage 3 fail-fast 触发,验证 disk-vs-index 一致;否则,以单元测试为唯一证据"。

### WR-02 — `finally` 块 best-effort 包装

**当前**(`runner.py:515-533`):
```python
finally:
    try:
        from ... import _current_node_id as _cv
        _cv.reset(token)
    except Exception:
        pass
    evidence_dir = request_dir / "evidence"
    flush_evidence(request_log, evidence_dir)
    write_evolution_snapshot(events, request_dir / "evolution_snapshot.json")
```

**问题:** `flush_evidence` / `write_evolution_snapshot` 如果在 finally 中 raise,会 *覆盖原始 try 块的异常*(Python `finally` 语义),掩盖真因。

**目标:** 两个 writer 调用都用 `try/except` 包,记日志但 swallow,以保护原始 exception。

**伪代码:**
```python
finally:
    try:
        _cv.reset(token)
    except Exception:
        pass
    # WR-02: best-effort 包装,避免清理失败掩盖原始异常
    try:
        flush_evidence(request_log, request_dir / "evidence")
    except Exception as cleanup_exc:
        print(f"[runner] flush_evidence failed for {request_id}: {safe_exc(cleanup_exc)}", file=sys.stderr)
    try:
        write_evolution_snapshot(events, request_dir / "evolution_snapshot.json")
    except Exception as cleanup_exc:
        print(f"[runner] write_evolution_snapshot failed for {request_id}: {safe_exc(cleanup_exc)}", file=sys.stderr)
```

**实测证据:** 不易在自然 batch 中触发 —— writer 已经在 IN-04 fix 后 defensive。证据是 *单元测试*:注入一个 `flush_evidence` raise,确认原始 try 块的 ProviderError 仍然 propagate 到 caller。

### WR-03 — 删除 `runner.py` 中重复的 `_detect_delimiter`

**当前:**
- `runner.py:350-358` 自己实现了 `_detect_delimiter`。
- `runner.py:273` 已经 `from seers_harness.intake.request_preprocessor import detect_delimiter, preprocess_request_from_csv` —— **detect_delimiter 已经被 import 但没被用**。

**目标:** 删除 `runner.py:350-358`,把 `_build_scratch_csv` 中 `delimiter = _detect_delimiter(csv_path)` 改为 `delimiter = detect_delimiter(csv_path)`(去掉 `_` 前缀,改用 import 的版本)。

**实测证据:** N/A —— pure cleanup,grep 验证 `_detect_delimiter` 在 `runner.py` 中 0 occurrences。

### WR-04 callsite — 改用 `reset_current_node_id` 公开 helper

**当前**(`runner.py:518-524`):
```python
try:
    from seers_harness.validation.recording_provider import (
        _current_node_id as _cv,
    )
    _cv.reset(token)
except Exception:
    pass
```

**目标:**
```python
try:
    from seers_harness.validation.recording_provider import reset_current_node_id
    reset_current_node_id(token)
except Exception:
    pass
```

`reset_current_node_id` 在 `aa49f06` 提交中已经落地为公开 API(参见 STATE.md)。

**实测证据:** N/A;grep 确认 `_current_node_id as _cv` 在 `runner.py` 中 0 occurrences。

### WR-05 — 收紧 `trial_runner` 的 `except Exception`

**当前**(`trial_runner.py:226-242`):
```python
except Exception as exc:
    outcome.success = False
    outcome.failure_category = type(exc).__name__
    if events is not None:
        events.append({"type": "trial_failed", ...})
```

**问题:** `Exception` 同时 catch 了 `ProviderAuthError` / `ProviderRateLimitError` / `ProviderTransientError` —— 这些应该 re-raise 让 runner 的 D-19 路由跑 fail-fast,而不是被 *trial* 标记为 failure 然后默默 swallow。

**目标:**
```python
except (ProviderAuthError, ProviderRateLimitError, ProviderTransientError):
    # D-19:provider errors 必须 fail-fast,不是 trial failure
    raise
except (TrialFailure, AssertionError, SchemaError) as exc:  # SchemaError = pydantic.ValidationError
    outcome.success = False
    outcome.failure_category = type(exc).__name__
    if events is not None:
        events.append({"type": "trial_failed", ...})
```

需要新 import:
```python
from seers_harness.core.errors import (
    ProviderAuthError, ProviderRateLimitError, ProviderTransientError,
)
from seers_harness.validation.exception_classifier import TrialFailure
from pydantic import ValidationError as SchemaError
```

**实测证据:** 实测 batch 中,如果 trial 期间 DeepSeek 返回 401(stale env 还残留或 key 被中途 rotate),trial 不应记 `trial_failed` 然后让 host 继续;应该让 ProviderAuthError 上浮,runner D-19 标 `provider_error` → fail-fast。这是 negative path,**很可能在 phase-8 batch 中不会自然触发**;主要证据是单元测试 + WR-05 narrow patch 本身。

**陷阱(§7 测序复核):** WR-05 必须在 F *之后* 落地。在 F 接线前,`trial_runner` 不被任何 runtime 路径调用(只有单测覆盖),收紧异常无副作用;但是如果 F 接线 *也* 在同一个 commit 里 land,如果 F 接线本身有 bug 让 trial 抛了 *不在 narrowed 集合中* 的非常规 exception,那个 exception 现在会 *上浮* 到 runner 然后 D-19 走 infra_error 路径 fail-fast。这是 *好事* —— 真实 bug 会浮现,不是被掩盖。因此 WR-05 在 F 之后立即落地是 *安全* 的,反而保护 F 接线的可观测性。

### IN-01 — `TrialOutcome.token_cost_observed` 接入 `runtime.trace[*].usage`

**当前:** `TrialOutcome.token_cost_observed: int = 0`,在 `run_request_trial` 中从未被赋值(`trial_runner.py:217-225` 只赋值 `tool_call_count`,没赋值 token cost)。

**`runtime.trace` 数据形状:** 从 `dag_runner` 推断(读 `WorkflowRuntime.run_request` 应该会向 `runtime.trace` 追加 events),每个 `tool_loop_summary` event 形如 `{"type": "tool_loop_summary", "node_id": ..., "tool_calls_made": N, "usage": {...}}` —— planner 应在 PLAN task 中 `<read_first>` 含 `seers_harness/workflow/dag_runner.py` 以确认 usage 字段的精确形状。

**目标:**
```python
# trial_runner.py:217-225 之后:
outcome.tool_call_count = sum(
    int(ev.get("tool_calls_made") or 0)
    for ev in runtime.trace
    if ev.get("type") == "tool_loop_summary"
)
# IN-01: 累加 trace 中所有 usage.total_tokens
outcome.token_cost_observed = sum(
    int((ev.get("usage") or {}).get("total_tokens") or 0)
    for ev in runtime.trace
    if ev.get("type") == "tool_loop_summary"
)
```

**实测证据:** Phase-8 batch 的 `evolution_snapshot.json` 中,每个 `trials[*]` 的 `token_cost_observed` 应该 > 0(因为 seed delta 触发了实际的 LLM 调用,有真实 token 消耗)。
```bash
python -c "
import json, glob
for p in glob.glob('tests/smoke/.runs/<phase-8-ts>/*/*/evolution_snapshot.json'):
    d = json.load(open(p))
    for t in d.get('trials', []):
        print(p, t.get('token_cost_observed'))
"
# 期望:每行的 token_cost_observed > 0
```

### IN-08 — 把 `max_retries=3` 提到 `deepseek_provider_from_env` kwarg

**当前**(`runner.py:249-250`):
```python
_PROVIDER_BUDGET_KEY = "max_" + "retries"  # noqa: assembled to satisfy forbid-list scan
_PROVIDER_CTOR_KWARGS: dict[str, Any] = {_PROVIDER_BUDGET_KEY: 3}
```

`runner.py:241` 用 `deepseek_provider_from_env(**_PROVIDER_CTOR_KWARGS)`。这是 *字符串拼接绕开 forbid-list 扫描* —— 反 audit。

**目标:**
1. `deepseek_provider_from_env` 已经接受 `max_retries: int | None = None`(`openai_compatible.py:137`)—— 直接传入即可。
2. 改写:
   ```python
   _RUNNER_PROVIDER_MAX_RETRIES = 3  # D-03 budget

   def _default_deepseek_factory() -> Any:
       from seers_harness.provider_runtime.openai_compatible import deepseek_provider_from_env
       return deepseek_provider_from_env(max_retries=_RUNNER_PROVIDER_MAX_RETRIES)
   ```
3. 删除 `_PROVIDER_BUDGET_KEY` 和 `_PROVIDER_CTOR_KWARGS`。
4. 检查 runner 模块 docstring forbid list(line 104-115)—— 它说"no wrapper layer";max_retries 走 kwarg 不是 wrapper,合规。

**实测证据:** N/A,pure cleanup。grep 确认 `max_retries` 在 `runner.py` 中只出现于该函数 body,且 `_PROVIDER_BUDGET_KEY` / `_PROVIDER_CTOR_KWARGS` 已删除。

---

## 5. Validation Architecture

> *本节是 Nyquist 步骤 5.5 的 trigger ——`grep "## Validation Architecture"` 会命中这里,使 `08-VALIDATION.md` 被 materialise。*

Phase 8 验证分三层,每一层职责不可由相邻层替代。任何 deliverable 在所有三层都有证据后才算 work,且 *实测层是最终判官*。

### 5.1 单元层(FakeProvider + 故障注入)

**职责:** 证明 *契约* 在隔离条件下成立 —— 函数签名、返回 shape、异常路由、配置解析。

**工具:**
- `tests/test_validation_runner.py` 系列(已存在 phase-7 模式):注入 `provider_factory` 返回 `ScriptedProvider` 或 `FaultProvider`,绕过真实 DeepSeek。
- `tests/test_provider_openai_compatible.py`:env 解析、构造参数。
- `tests/test_trial_runner_smoke.py`:patch 应用、temp root 隔离。
- `tests/test_exception_classifier.py`:cause-chain walk、isinstance allowlist。

**Phase 8 新增/修改单测列表(per deliverable):**

| Deliverable | 新增/修改测试 | 路径 |
|---|---|---|
| A | `test_provider_timeout_default_180s` | `tests/test_provider_openai_compatible.py` |
| B (×3) | transient retry 3 路径(2 次成功 / 不重试 auth / 耗尽 budget) | `tests/test_validation_runner.py` |
| C | `test_parse_retry_log_present_on_retry`(新增 log 行后) | `tests/test_provider_openai_compatible.py` |
| D (×5) | 见 §2-D 测试锚点 | `tests/test_validation_runner.py` |
| E (×2) | failure_class mapping + index/summary 集成 | `tests/test_exception_classifier.py`, `tests/test_index_writer.py`, `tests/test_batch_summary_writer.py` |
| F (×4) | 见 §3.6 测试锚点 | `tests/test_validation_runner.py` |
| WR-01 | `test_stage3_fail_fast_drains_inflight` | `tests/test_validation_runner.py` |
| WR-02 | `test_finally_writer_failure_does_not_mask_original` | `tests/test_validation_runner.py` |
| WR-03 | N/A(纯删除,grep verify) | — |
| WR-04 callsite | grep verify `_current_node_id as _cv` 不存在 | — |
| WR-05 | `test_trial_runner_reraises_provider_errors` | `tests/test_trial_runner_smoke.py` |
| IN-01 | `test_trial_outcome_token_cost_from_trace_usage` | `tests/test_trial_runner_smoke.py` |
| IN-08 | grep verify `_PROVIDER_BUDGET_KEY` 不存在 + `deepseek_provider_from_env(max_retries=3)` 在 runner 中 | — |

**单元层验收:** `pytest -q` 在 phase-8 final commit 上 ≥ 当前 baseline(253),无 skipped 新测,无 xfail。

### 5.2 集成层(全套 pytest 在 phase-8 final commit 上)

**职责:** 证明 phase-8 改动没有破坏 phase 1-7 的 122/122 → 125/125 → 253/253 累积回归。

**Phase 8 新增测试约 15-20 个(见 5.1 表),目标:268+ tests,0 skip,0 fail。**

### 5.3 实测层(Real DeepSeek Stage 1+2+3 Batch)

**职责:** *证明模块在真实条件下实际 fires*。这是 phase 8 的最终判官 —— 单元/集成全绿但实测失败 = 验收失败,phase 8 仍 reopen。

**Batch 启动命令(canonical):**
```bash
python -m seers_harness.validation.runner --env-file .env.local
```
(无 shell `export`,完全依赖 `--env-file` 加载 key,验证 D 项 firing。)

**Batch 矩阵:** Stage 1 (n=1, c=1) → Stage 2 (n=20, c=1) → Stage 3 (n=20, c=20),无 inter-stage checkpoint。

**Batch 输出位置:** `tests/smoke/.runs/<phase-8-ts>/`(git-ignored per D-09)。

### 5.4 实测证据矩阵(逐 Deliverable × Stage × Pass Criterion)

| Deliverable | Stage 中观察点 | 通过判据 |
|---|---|---|
| **A** 超时 180s | Stage 1 / 2 / 3 任一请求 | 任一 trace 的 `usage.json` 显示总耗时 60s-180s 且 `exception is null`(对照 0526 trace 在 60s 处死);若 *所有* 请求都 < 60s,A 项视为 *未在 batch 中 firing*(planner 应注解:此时单元测试是唯一证据)。 |
| **B** 请求级 transient 重试 | Stage 2 或 3 任一请求 + 故障注入 1 个请求 | `.run-logs/runner-<ts>.log` 含 `transient (attempt N/3); backoff=Ns` 文本;若无自然 transient,必须有 1 个故障注入请求展示该路径(`index.json` 该 row `fault_inject=true`)。 |
| **C** CR-05 审计 | 任一 stage 任一请求出现 tool_args 截断 | log 含 `parse_retry node=... attempt=N/M` 文本;最终该请求 (i) 成功 *或* (ii) `exception` 为 `ProviderResponseError` 路由 `provider_error` fail-fast。 |
| **D** `--env-file` | Stage 1 启动 | log 前 2 行:`env-file: loaded N keys from .env.local` + `DEEPSEEK_API_KEY suffix=****<4chars>`;value 字符串不出现在 log 中。 |
| **E** `failure_class` | 所有 stages 全部请求 | `index.json` 每行有 `failure_class` ∈ {ok, auth, rate_limit, transient, malformed_tool_args, schema_violation, runner_bug};`batch_summary.json` `by_failure_class` 各 value 之和 = `totals.requests`。 |
| **F** evolution 接线 | 所有 stages 全部请求 | `evolution_snapshot.json` 含 `trials[]` 非空 *至少一个请求*;`trial_succeeded` 或 `trial_failed` event 存在;`record.trial_selected_delta_id == "phase-8-seed-001"`(或等价 patch-derived id)在 `index.json` 至少一行。 |
| **WR-01** drain in-flight | Stage 3 fail-fast 时(若发生) | `len(index.json.requests) == 20`;disk 上 `stage3/<rid>/` 目录数 = 20。**若无 fail-fast,跳过,单测为唯一证据**。 |
| **WR-02** best-effort finally | N/A 自然 batch 中难触发 | **单测为唯一证据**;实测 batch 失败时,日志中不出现 "flush_evidence failed" 行(若出现,说明 IN-04 fix 失效,新 finding)。 |
| **WR-03** 删除 dup `_detect_delimiter` | N/A | grep:`_detect_delimiter` 在 `runner.py` 出现次数 = 0;`detect_delimiter`(无下划线)调用 = 1。 |
| **WR-04 callsite** 公开 helper | N/A | grep:`_current_node_id as _cv` 在 `runner.py` 出现次数 = 0;`reset_current_node_id` import = 1。 |
| **WR-05** trial 异常窄化 | Stage 2/3 trial 中,若 DeepSeek auth/rate 错误发生 | log 显示 `provider_error -> fail-fast`(via D-19 routing);**不应** 显示 `trial_failed` 类型为 `ProviderAuthError`(若显示,WR-05 fix 失效)。**若无自然 provider error,单测为唯一证据**。 |
| **IN-01** token_cost_observed | F seed delta 触发的所有 trials | `evolution_snapshot.json` 中 `trials[*].token_cost_observed > 0` 至少一个请求。 |
| **IN-08** max_retries kwarg | N/A | grep:`_PROVIDER_BUDGET_KEY` / `_PROVIDER_CTOR_KWARGS` 在 `runner.py` 出现次数 = 0;`deepseek_provider_from_env(max_retries=3)` 出现 = 1。 |

### 5.5 实测层验收闸门

- **D8-ACC-1:** 一次 Stage 1+2+3 batch 在 *单一* phase-8 commit 上 end-to-end 完成,零请求因 60s/stale-env/未处理 transient 而 fail-fast。
- **D8-ACC-2:** `evolution_snapshot.json` 含 ≥ 1 个非空 `trials[]`(F 接线证据)。
- **D8-ACC-3:** `index.json` 每行有 `failure_class`;`batch_summary.json` `by_failure_class` 完整。
- **D8-ACC-4:** `pytest -q` 全套通过(单元+集成层 §5.1 + §5.2)。
- **D8-ACC-5:** `07-WRIN-TRIAGE.md` 7 个 scheduled 项目移至 phase-8 commit ref。
- **D8-ACC-6:** `08-VERIFICATION.md` 状态 `passed`。

任一 deliverable 在 §5.4 矩阵中没有可验证证据 = phase 8 仍 reopen。

---

## 6. 根因诊断剧本(D8-VAL-ROOTCAUSE Playbook)

> 当 phase-8 batch 失败时,planner 已在每个相关 task 的 `<read_first>` 中按 *嫌疑链最近端优先* 列文件。下表是 planner 写诊断 task 时的参考模板。

### 6.1 `auth` 失败

**表层症状:** `ProviderAuthError("AuthenticationError: 401 ... key: ****<suffix>")` 浮到 runner;`failure_class="auth"`。
**嫌疑链(最近端优先):**
1. shell env 中 `DEEPSEEK_API_KEY` 与启动时 `--env-file` 加载的不一致(D 项 firing 失败)。
2. `.env.local` 中的 key 已被 platform 端 rotate(实际值过期)。
3. `.env.local` 文件本身缺失或格式错误(我们的 `_load_env_file` 应该 raise 而不是悄悄 skip)。
**必读文件(`<read_first>`):**
- `seers_harness/validation/runner.py` (`_load_env_file` + main argparse 块)
- `.env.local`(只读取,不在 task 输出中展示 value!)
- `.run-logs/runner-<phase-8-ts>.log`(前 5 行的 env-file log + 401 trace)
**反模式 ❌:**
- 不要"catch 401 并提示用户更新 key" —— 根因是 *启动时 env 加载漏了*,不是 401 本身。
- 不要把 `DEEPSEEK_API_KEY` value 写到诊断输出。

### 6.2 `rate_limit` 失败

**表层症状:** `ProviderRateLimitError`;`failure_class="rate_limit"`。
**嫌疑链:**
1. Stage 3 c=20 真的撞到 DeepSeek 实测速率上限(*预期* 行为,见 STATE.md "phase 7 stage 3 may surface real DeepSeek rate-limit ceilings")。
2. account 级 quota 接近耗尽(`tests/smoke/.runs/` 一周内 batch 次数累积)。
3. provider 端 max_retries=3 已经掩盖了 1-2 次 rate burst —— 此 raise 已经是 retry 后的真失败。
**必读文件:**
- `seers_harness/provider_runtime/openai_compatible.py:73-104`(SDK retry 路径)
- DeepSeek dashboard(*非文件*,planner 在 task 注释中说明)
- 前 N 个请求的 `.run-logs/`(看是否累积)
**反模式 ❌:**
- 不要把 SDK max_retries 从 3 改大 —— D-03 锁定,且会延迟真问题的暴露。
- 不要在 runner 加额外 rate-limit absorber —— 已 deferred 到 follow-up phase。

### 6.3 `transient` 失败(retry 耗尽)

**表层症状:** B 项 3 次尝试都 transient,最终 raise;`failure_class="transient"`。
**嫌疑链:**
1. DeepSeek beta endpoint 实际不可用(基础设施层)。
2. 60s → 180s 超时升级后,仍然 TTFB > 180s(reasoning model 比预估慢)—— *根因不是 transient 本身,是 A 项预算还不够*。
3. 网络中间层(VPN / proxy)间断性断流。
**必读文件:**
- `.run-logs/runner-<ts>.log`(全部 3 次 attempt 的 stack trace + 时间戳)
- `seers_harness/provider_runtime/openai_compatible.py:50-104`(确认超时 / SDK retry 路径)
- `seers_harness/validation/runner.py` `_run_one_request_with_transient_retry`(B 项 wrapper)
**反模式 ❌:**
- 不要把 transient retry budget 从 3 加大 —— charter 已锁定,且不能掩盖基础设施问题。
- 不要 catch `ProviderTransientError` 后转成 trial_failure —— D-19 路由禁止。

### 6.4 `malformed_tool_args` 失败

**表层症状:** `ProviderResponseError("Failed to parse tool_call.arguments ...")`;`failure_class="malformed_tool_args"`。
**嫌疑链:**
1. CR-05 parse-retry budget(`_parse_max_retries`,默认 3)耗尽 —— DeepSeek 多次返回不可恢复的 JSON。
2. 单次返回内容超长截断(0526 case)—— root cause 在 DeepSeek 端,但 *如果观察到的截断很短,可能 model side 的 max_tokens 隐含限制变化*。
3. Tool schema 与 model 行为漂移 —— `tools` payload 中的 schema 不匹配 model 的输出格式。
**必读文件:**
- `seers_harness/provider_runtime/openai_compatible.py:66-103`(parse_retry 循环 + `_parse_args`)
- `tests/smoke/.runs/<ts>/<rid>/evidence/<node>/messages.jsonl`(查看 raw model output)
- `seers_harness/tools/*.py`(对应失败 node 的 tool schema)
**反模式 ❌:**
- 不要把 parse_retry budget 加大 —— 真问题在 DeepSeek 端的 *单次响应质量*,不是重试次数。
- 不要在 `_parse_args` 中尝试"修复 JSON"(prepend `{`、补 `}`、等)—— 引入未审计的 LLM-output mutation,违反 D-22。

### 6.5 `schema_violation` 失败

**表层症状:** `pydantic.ValidationError` 浮到 runner;`failure_class="schema_violation"`。
**嫌疑链:**
1. Model 输出了非法字段(C16 STOP-GATE 残留字段 / 自评分字段 —— P-10 违反)。
2. Schema 本身 drift(`PersonalizationFactor` 等 model 改了,但 SKILL.md prompt 没改 / vice versa)。
3. Tool handler 接收正确 model 输出,但在 handler 内部把它转成了非法 shape。
**必读文件:**
- `seers_harness/domain/models.py`(失败的 model 类)
- 对应的 SKILL.md(`workflow-skills/current/<skill>/SKILL.md`)
- `messages.jsonl` 中 model 的 raw output
- `tool_calls.jsonl` 中实际传给 handler 的 arguments
**反模式 ❌:**
- 不要在 `model_validate` 外面加 `try/except` 然后"修一下再 validate" —— P-10 锁死 schema 即真理。

### 6.6 `runner_bug` 失败(default 桶)

**表层症状:** `failure_class="runner_bug"`(其他所有都不匹配)。
**嫌疑链:**
1. F 接线 bug:`run_request_trial` 接受了不合法 patch / temp_root 操作失败 / events list 共享导致 race。
2. WR-01 drain 逻辑 bug:future 状态判断错误。
3. 第三方依赖升级(`pydantic` / `httpx` / `openai` SDK)行为漂移。
**必读文件:**
- *Whatever the trace points at*(planner 的 task 描述必须 grep 出 exception 的实际 raise 位置)
- `seers_harness/validation/runner.py`(整文件)
- `seers_harness/evolution/trial_runner.py`(F 接线相关)
- `pyproject.toml` 或 `requirements.txt`(锁定的依赖版本)
**反模式 ❌:**
- 不要把 `runner_bug` 视为"未知 bug 占位符"就归档 —— 必须 root-cause 后给定具体 sub-cause 并写 follow-up WR 项。
- 不要在 catch 处加 `print` 就当 fix —— 修根因,不是给桶贴标签。

### 6.7 通用反模式(适用于所有桶)

- ❌ 不在 `index.json` / `batch_summary.json` 漏写 `failure_class` —— ACC-3 强制 100% 列存在。
- ❌ 不在 runner 中 catch 完异常然后转成 `trial_failure` —— D-19 路由禁止。
- ❌ 不把 root-cause 诊断写到 `08-VERIFICATION.md` 的"已修"段而无 commit ref —— 没有 commit 的"已修"没有意义,作为新 finding 记录。

---

## 7. 测序复核

**Charter 锁定的顺序:**
> A/D/E(可重跑前置) → C(审计,依赖一次 batch) → WR-03 / WR-04-callsite / IN-08(纯清理) → F(演化接线) → B(transient 重试包裹新接线) → WR-01 / WR-02 / WR-05 / IN-01(touch the new wiring)

### 7.1 隐藏耦合检查

- **A 与 D 是否冲突?** A 改 default,D 加 `--env-file`;两者都修改 `_default_deepseek_factory` 的间接调用路径。**不冲突。** D 不读 timeout,A 不读 env file;两者在 main argparse 块和 `_default_deepseek_factory` 都有改动但路径不交叉。
- **E 与 F 顺序敏感性?** E 在 F 之前落地,意味着 `failure_class` 字段会被 *无 trial 状态* 的请求填(全 `"ok"`);F 落地后这些字段不变。**安全。** E 的字段定义不依赖 trial 存在。
- **C 在 F 之前是否合理?** C 是审计,需要 batch 已经跑 — 但 phase 8 *的* batch 必须在 F 落地后才有意义(否则没接线,trials[] 必空)。**修正:** C 应该等 F 落地后跑 batch 时一并审计 —— 实际执行顺序变成 [A/D/E → WR-03/WR-04/IN-08 → F → B → WR-01/WR-02/WR-05/IN-01] → 跑一次 batch → C 审计 batch 产物。**这只是 charter 顺序的语义微调,不改写代码顺序。**
- **WR-05 在 F 之前 vs 之后?**(已在 §2-WR-05 讨论)
  - F *之前*:`trial_runner` 不被 runtime 调用,narrow 异常无副作用。
  - F *之后*:narrow 后,F 接线的真实 bug 会浮现而不被掩盖。
  - **保持 charter 顺序:F 之后立刻 WR-05,这是 *增强* F 的可观测性,不是风险。**
- **WR-01 与 F 顺序敏感性?** WR-01 改 Stage 3 fail-fast 的 drain 逻辑;F 在 trial 路径中可能 raise(被 narrowed 后)。WR-01 的 drain 逻辑应当包含 trial 引发的 exception(WR-05 narrow 后会变成 fail-fast)。**安全,只要 WR-01 的 drain 也用 `failure_class(exc)` 标 drain 出的失败 record。** 这是 §4-WR-01 伪代码已经体现的。
- **IN-01 与 F 顺序敏感性?** IN-01 改 `run_request_trial` 的 outcome 填充;F 调 `run_request_trial`。F 在 IN-01 之前落地的话,`trial_outcome.token_cost_observed` 会是 0(默认),实测层的 IN-01 验收会失败。**修正:** IN-01 应该和 F 同一个 commit 或紧跟在 F 之后,不能在 WR-01/02/05 之后。**修订顺序:F → IN-01 → B → WR-01 → WR-02 → WR-05。**

### 7.2 最终推荐顺序

| # | 项 | 文件 | 是否需要 commit 一起? |
|---|---|---|---|
| 1 | A | `openai_compatible.py` | 单独 |
| 2 | D | `runner.py`(main + load helper)| 单独 |
| 3 | E | `exception_classifier.py` + `runner.py` + `index_writer.py` + `batch_summary_writer.py` | 单独 |
| 4 | WR-03 | `runner.py` | 单独 |
| 5 | WR-04-callsite | `runner.py` | 单独(可与 WR-03 合并) |
| 6 | IN-08 | `runner.py` | 单独(可与 WR-03/WR-04 合并为"runner 清理三件套") |
| 7 | F | `runner.py`(主接线)| 单独,大 commit |
| 8 | IN-01 | `trial_runner.py` | 紧跟 F |
| 9 | B | `runner.py`(transient retry wrapper)| 单独 |
| 10 | WR-01 | `runner.py`(Stage 3 drain)| 单独 |
| 11 | WR-02 | `runner.py`(finally best-effort)| 单独 |
| 12 | WR-05 | `trial_runner.py` | 单独 |
| — | C 审计 | 跑一次实测 batch,读 log | 不产生代码 commit(除非加 parse_retry log)|

总计:11-12 个 commit + 1 个审计步骤 = 12-13 个原子 commit,符合 GSD 原子 commit 规范。

### 7.3 风险缓解

- **大 commit 风险(F):** F 接线是单 commit 中最大的改动。Planner 应在 F 的 PLAN 中拆分 task 但保持单 commit —— 接线 + 单测在同一个 commit。如果需要拆,拆为"(F-1) 添加 seed delta + portfolio 构造","(F-2) `_run_one_request` 接线","(F-3) `_run_stage` 调用点更新"三个 commit,但三者无 IN-01 token cost 接入会让 F-1/F-2/F-3 各自的实测无意义 —— **推荐保持 F 单 commit + IN-01 紧随**。

---

## 8. 未决问题 / 推荐问询用户

≤ 3 项,planner 应在 PLAN 写入前请用户 confirm:

1. **`SchemaError` 别名问题。** Charter 文本(§Group 1 E)写"`SchemaError → schema_violation`",但代码中没有名为 `SchemaError` 的类;实际 raise 的是 `pydantic.ValidationError`。**建议默认行动:** 在 `exception_classifier.failure_class` 中映射 `pydantic.ValidationError → "schema_violation"`,并在 PLAN 注释中标明这是 charter `SchemaError` 的 canonical 实现。**请用户确认或反对该映射。**

2. **种子 delta 候选。** §3.4 推荐 C3(`generate-copy-candidates/SKILL.md` 前置 HTML 注释)。**请用户确认或指定其他 delta。** 如果用户偏好"真实 prompt-level 改动"(C2 类),planner 需要明确 *哪个 SKILL 的哪一句* 加什么,这超出 RESEARCH 阶段能锁定的细节。

3. **故障注入要不要进入 phase-8 batch?** §2-B 实测证据要求建议 *如果* Stage 1+2+3 自然 batch 中没出现 transient,加 1 个 marker 为 `fault_inject=true` 的请求来 firing B 项路径。**请用户确认这种"在生产 batch 中混 1 个故障注入请求"的策略是否可接受**,或要求 phase 8 完全靠自然 transient 出现(若不出现就接受 B 项仅有单测证据)。

---

## RESEARCH COMPLETE

- 文件已写到 `.planning/phases/08-evolution-wiring-and-runner-debt/08-RESEARCH.md`,8 大节齐全(含 `## Validation Architecture` 让步骤 5.5 触发)。
- Group A-E + F + G(7 个 WR/IN)所有 deliverable 都精确到 file:line,伪代码就位;实测证据矩阵逐项给出可 grep / 可 read 的判据。
- 测序复核发现一处微调:IN-01 必须紧随 F(charter 写的位置太晚),已在 §7.2 给出 12 commit 推荐序。
- 3 项待用户确认:(a)`SchemaError == pydantic.ValidationError` 别名;(b)种子 delta C3 选择;(c)故障注入请求是否计入 phase-8 batch。
