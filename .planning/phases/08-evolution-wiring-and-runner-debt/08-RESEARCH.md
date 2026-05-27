# Phase 08: 阶段研究 — Runner ↔ Evolution 接线 + Runner-Debt 清扫 + 阶段7实测硬化

**Phase:** 08-evolution-wiring-and-runner-debt
**生成时间:** 2026-05-27
**作者:** 主上下文研究(researcher 子代理两次上游断连后接管)
**消费者:** `gsd-planner`(产出 PLAN.md 集)、`gsd-pattern-mapper`、步骤 5.5(materialise VALIDATION.md)

> **范围红线**(由 `08-CONTEXT.md` 的 `<scope_fence>` 决定):
> 本研究 **不** 重新打开 Phase 7 验收讨论,**不** 重新设计 Phase 6 演化策略,**不** 修改 capture 层(`recording_provider` / `evidence_writer` / `machine_judges`)除了 E 项追加的 `failure_class` 列。所有结论都服务于在 `runner.py` 一次性扫掉 Groups A-G,然后让 Phase 7 的 Stage 1+2+3 实测能干净跑通。

---

## 1. 执行摘要

- **核心改动面积出乎意料地小。** 7 个文件被触碰,主战场是 `seers_harness/validation/runner.py`。所有外部接口(provider、`assemble_portfolio`、`run_request_trial`、`classify`、`run_skill_via_tools`、`distill-skill-deltas` skill 注册)都已就绪,Phase 8 是把 *已经长好的零件* 用一根线连起来 + 顺手填几个洞 + 加 5 个行为度量,不是新设计。
- **不能 fail-fast 跳过实测层。** Phase 7 重新打开的根本原因就是 *单元/烟囱测试全绿但实测跑不通*。Phase 8 验收硬挂在一次 Stage 1+2+3 实测 batch 上(`D8-VAL-REAL`),pytest 通过只是必要条件、不是充分条件。**真阳性边界:** 不只是"模块 firing"(假阳性),而是"模块做了它该做的事"—— 挖掘真的产出多角度 factor、文案真的产出多 candidate、模型偷懒时反思真的被消费、演化真的从 trace 算法提取 delta 并跑出 trial outcome 与 baseline 有可测差异。Phase 8 通过 `machine_judges` 加 5 个行为度量(§5.4)统计这些行为,任一未达阈值 = 阻塞 user review,不自动 pass。
- **三组失败模式都有 0526 trace 锚点,可以精确根因追溯。**
  - 60s 超时:`.run-logs/runner-20260526T183141Z.log:76` `httpx.ReadTimeout → ProviderTransientError`
  - shell-env 漂移:`.run-logs/runner-20260526T174546Z.log:25` `401 Authentication Fails, ****92c7`
  - tool_args 截断:`07-VERIFICATION.md` 记录的 Stage 2 req2 第 940 char `evidence_refs:` 截断
- **每组最高风险:**
  - Group 1 高风险 = **D**(`--env-file`,安全敏感:绝不能把 key 写日志);
  - Group 2 高风险 = **F = 演化全链路接线(C4 路径)**:不只是把 `assemble_portfolio` + `run_request_trial` 连进 runner,而是把 `distill-skill-deltas` skill 的 *agent 调用点* 接在 Stage 1 完成后,Stage 2/3 跑 distilled delta 的 trial。每一步用现成 zero-shot agent / pure transform,**禁止 hardcode seed delta、禁止启发式 if-else、禁止人工预定义 patch**。
  - Group 3 高风险 = **WR-05**(过早收紧 `except Exception` 可能在 F 真正接线之前掩盖接线 bug — 见 §7 测序复核)。
- **测序 *已锁* 但需要一处微调:** 在 F 落地 *之前* 不要执行 WR-05。详见 §7。
- **B 项粒度澄清(2026-05-27 grep 后修正):** `seers_harness/agentic/tool_loop.py:31-65` 的 `run_skill_via_tools` **已经实现 turn 内 transient retry**(`max_transient_retries_per_turn=2` 默认,共 3 次尝试),但 *无 backoff*。Charter B 项的"请求级 retry 5s/15s backoff"在已有 retry 点上 *加 backoff* 即可实现,**不需要在 `_run_one_request` 外另起一层 wrapper**。这避免 §2-B 原伪代码中的"finally 重复 flush_evidence" 陷阱,也符合用户审美"避免多层嵌套"。详见 §2-B 重写。

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

### B. 请求级 transient 重试(落在已有 retry 点上加 backoff)

**关键 grep 发现(2026-05-27,撤回原 §2-B 的 wrapper 设计):**

`seers_harness/agentic/tool_loop.py:31-65` 的 `run_skill_via_tools` **已经实现 turn 内 transient retry**:

```python
# tool_loop.py:53-65 (existing)
for turn in range(max_tool_calls):
    for attempt in range(max_transient_retries_per_turn + 1):
        try:
            result = provider.generate_with_tools(...)
            break
        except ProviderTransientError:
            if attempt == max_transient_retries_per_turn:
                raise
```

`max_transient_retries_per_turn` 默认 2,即一次 turn 内有 3 次尝试。`dag_runner.py:82` 的调用点没有显式覆写,沿用默认。**这意味着:**

- charter B 项的"3 次尝试"已经实现,但是 *无 backoff* —— immediate retry,DeepSeek 端 transient 通常需要几秒恢复时间,无 backoff 会把 budget 燃尽。
- charter B 写的"包 `_run_one_request`"会引入 *第二层* retry(turn 级 + 请求级),且包到 `_run_one_request` 外面会让 `finally:` 块的 `flush_evidence` / `write_evolution_snapshot` 在每次重试都跑一次,文件被覆盖,evidence 失真。

**修正设计:在已有 retry 点加 backoff,不另起 wrapper。**

**修改点:** `seers_harness/agentic/tool_loop.py:53-65`

```python
# 当前:
for attempt in range(max_transient_retries_per_turn + 1):
    try:
        result = provider.generate_with_tools(...)
        break
    except ProviderTransientError:
        if attempt == max_transient_retries_per_turn:
            raise

# 目标(B 项):attempt 0 立即,attempt 1 sleep 5s,attempt 2 sleep 15s
_TRANSIENT_BACKOFF_SECONDS: tuple[float, ...] = (0.0, 5.0, 15.0)

for attempt in range(max_transient_retries_per_turn + 1):
    if attempt > 0:
        backoff = _TRANSIENT_BACKOFF_SECONDS[min(attempt, len(_TRANSIENT_BACKOFF_SECONDS) - 1)]
        time.sleep(backoff)
    try:
        result = provider.generate_with_tools(...)
        break
    except ProviderTransientError:
        if attempt == max_transient_retries_per_turn:
            raise
```

**为什么这是更好的位置:**
- *单层循环,无嵌套*。已有 turn-internal retry 是天然位置,不引入第二层。
- backoff 总和 = 5s + 15s = 20s。Stage 3 c=20 的 worst-case 增量 ≤ 20s × 20 = 400s,仍可接受;但 c=20 的 worker 是 *独立线程*,backoff 不阻塞其他 request,实际增量更接近 20s。
- 不需要 `_run_one_request_with_transient_retry` wrapper,不需要在 `_run_stage` 改 submit 调用,**runner.py 零改动**(B 项落在 tool_loop)。
- `finally:` flush 块仍只在 `_run_one_request` 退出时执行一次,evidence 完整。

**测试锚点:**
- 现有:`tests/test_tool_loop.py`(若存在;否则在 `tests/test_validation_runner.py` 加 fault-injection provider)。
- 新增:
  - `test_tool_loop_backoff_on_transient` —— monkeypatch `time.sleep`,inject provider 前 2 次 raise `ProviderTransientError`、第 3 次成功 → 验证 `time.sleep` 被调用 2 次,值分别是 5.0、15.0。
  - `test_tool_loop_does_not_backoff_on_first_attempt` —— 第一次 attempt 不 sleep。
  - `test_tool_loop_does_not_retry_auth_error` —— `ProviderAuthError` → 第一次就 fail-fast,无 sleep。
  - `test_tool_loop_exhausts_transient_budget` —— 连续 3 次 transient → raise(走 D-19 `provider_error`)。

**实测证据(D8-VAL-REAL):**
- 唯一 *额外* 实测要求(超过 pytest):phase-8 batch 期间任一请求若发生自然 transient,`.run-logs/runner-<ts>.log` 应该出现 `ProviderTransientError` 后跟着的 *下一个 turn 仍然成功*(隐含 sleep 已生效),整个 request 没有 fail-fast。
- 用户决定(Q3 = B):**不在 batch 中混入故障注入请求**。如果 phase-8 batch 中没有自然 transient,B 项以 pytest 4 路径单测为 *唯一证据*,不伪造实测证据。

**陷阱:**
- *不要* 把 `_TRANSIENT_BACKOFF_SECONDS` 改成"每次 attempt 翻倍"(指数退避)—— charter 锁定 5s, 15s 字面值,且固定值更可测。
- *不要* 在 `time.sleep` 外加 `print` —— 已有 retry 点已经在 LLM trace 中可见(下一个 turn 是 retry)。新增 print 是噪声。
- *不要* 把 backoff 加到 `_run_one_request` 外面 —— 见上方"为什么这是更好的位置"。

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

### 3.4 演化全链路接线(C4 路径 — agent 产 delta,无 hardcoded seed)

**用户决定(Q2 = C4,2026-05-27):** 撤回 C3(HTML 注释种子),改为让 `distill-skill-deltas` agent 在 Stage 1 完成后从 *真实 trace* 算法提取 delta,Stage 2/3 跑该 delta 的 trial。**禁止 hardcode seed、禁止人工预定义 patch、禁止启发式 if-else。**

**全链路零件清单(grep verified):**

| 零件 | 路径 | 角色 |
|---|---|---|
| `distill-skill-deltas` SKILL.md | `workflow-skills/evolution/distill-skill-deltas/SKILL.md` | Tool-use agent 形态,产 `DeltaDistillationArtifact` |
| `EVOLUTION_TOOLS_SPEC` + `EVOLUTION_TOOL_HANDLERS` | `seers_harness/tools/evolution_tools.py:376, 385` | `record_delta_observation` / `record_delta_change` / `submit_delta_distillation_final` 三 handler |
| `run_skill_via_tools` | `seers_harness/agentic/tool_loop.py:31` | Generic agent driver,接受 skill + tools + provider |
| `DeltaDistillationArtifact` → `DeltaProposal[]` | `seers_harness/evolution/delta_portfolio.py:124` (model) | distill artifact 携带的 proposal 列表 |
| `assemble_portfolio` | `delta_portfolio.py:395` | Merge `DeltaProposal[]` 进 `DeltaPortfolioRow[]` |
| `run_request_trial` | `evolution/trial_runner.py:155` | 跑 trial,emit events,返回 `TrialOutcome` |
| `update_after_trial` | `delta_portfolio.py:193` | 把 trial outcome 折回 portfolio belief counters |

**已就绪。零件都在,phase 8 只需接线。**

**接线伪代码(在 runner.py `run()` 函数中):**

```python
# 现有(line 786):
_delta_portfolio_empty: list[Any] = []  # noqa: F841

# 改为:
delta_portfolio: list[DeltaPortfolioRow] = []  # D-18:起始空,distill 后填充

# Stage 1 后,distill skill 跑一次 agent 调用(用 Stage 1 的 trace 作为 payload):
for stage in stages:
    result = _run_stage(stage=stage, request_ids=request_ids, ..., delta_portfolio=delta_portfolio)
    if not result.passed:
        return 1

    # 演化接线:Stage 1 完成后调用 distill agent,Stage 2/3 才有 trial 可跑
    if stage == 1 and result.passed:
        delta_portfolio = _distill_after_stage1(
            stage1_result=result,
            provider_factory=provider_factory,
            current_portfolio=delta_portfolio,
        )
        # delta_portfolio 现在含 1 个或多个 DeltaPortfolioRow,由 agent 从 trace 提取
```

**`_distill_after_stage1` 实现要点:**

```python
def _distill_after_stage1(
    *,
    stage1_result: StageResult,
    provider_factory: ProviderFactory,
    current_portfolio: list[DeltaPortfolioRow],
) -> list[DeltaPortfolioRow]:
    """读 Stage 1 trace,跑 distill-skill-deltas agent,返回新 portfolio。

    Agent 产 delta;此函数零启发式 / 零模板预定义。
    """
    # 1. 构造 distill payload:Stage 1 唯一一个请求的完整 trajectory
    #    (factor / copy / rubric artifacts + tool-call sequence + token usage)
    stage1_request_dir = stage1_result.stage_dir / _safe_request_dirname(stage1_result.records[0]["request_id"])
    trajectory_payload = _build_trajectory_payload(stage1_request_dir)

    # 2. 跑 agent:run_skill_via_tools 是已存在的 generic driver
    from seers_harness.agentic.tool_loop import run_skill_via_tools
    from seers_harness.tools.evolution_tools import EVOLUTION_TOOLS_SPEC, EVOLUTION_TOOL_HANDLERS
    from seers_harness.evolution.delta_portfolio import DeltaDistillationArtifact, assemble_portfolio

    skill_bundle = (LIVE_SKILL_ROOT / "evolution/distill-skill-deltas/SKILL.md").read_text()
    distill_provider = RecordingProvider(provider_factory(), [])  # capture distill agent 的 trace 为审计证据

    result = run_skill_via_tools(
        skill_name="distill-skill-deltas",
        skill_bundle=skill_bundle,
        payload=trajectory_payload,
        tools_spec=EVOLUTION_TOOLS_SPEC["distill-skill-deltas"],
        tool_handlers=EVOLUTION_TOOL_HANDLERS,
        provider=distill_provider,
        node_id="distill_after_stage1",
    )

    # 3. result.artifact 是 dict;model_validate 进 DeltaDistillationArtifact
    artifact = DeltaDistillationArtifact.model_validate(result.artifact)
    proposals = artifact.proposals  # DeltaProposal[]

    # 4. 合并进 portfolio(纯 transform,zero 启发式)
    return assemble_portfolio(current_portfolio, proposals, events=None)
```

**`_build_trajectory_payload` 是 *纯 transform*,无启发式:**

```python
def _build_trajectory_payload(stage1_request_dir: Path) -> dict:
    """读 stage1 request dir 中所有 evidence files,组装 distill payload。

    Pure file read + dict assembly. No heuristic filtering, no LLM-side processing.
    """
    evidence = stage1_request_dir / "evidence"
    payload = {
        "request_id": stage1_request_dir.name,
        "factor_discovery": json.loads((evidence / "factor_discovery/artifact.json").read_text()),
        "copy_generation": json.loads((evidence / "copy_generation/artifact.json").read_text()),
        "personalized_copy_rubric": json.loads((evidence / "personalized_copy_rubric/artifact.json").read_text()),
        "tool_calls_per_node": {
            n: [json.loads(l) for l in (evidence / n / "tool_calls.jsonl").read_text().splitlines() if l]
            for n in ("factor_discovery", "copy_generation", "personalized_copy_rubric")
        },
        "usage_per_node": {
            n: json.loads((evidence / n / "usage.json").read_text())
            for n in ("factor_discovery", "copy_generation", "personalized_copy_rubric")
        },
    }
    return payload
```

**`run_request_trial` 调用点(在 `_run_one_request` 内,Stage 2/3 用):**

仍按原 §3.5 伪代码,但 `delta_portfolio` 现在来自 distill agent 而非 hardcoded seed。

**关键审美约束(用户 2026-05-27 reaffirmed):**
1. **该用 agent 的别用人工** —— distill agent 由 LLM 读 trace 产 delta,phase 8 不内置任何"delta 模板"或"目标 SKILL 黑白名单"。
2. **该用算法的别用启发式** —— `assemble_portfolio` 是 set-merge by `delta_id`,纯函数;`update_after_trial` 是 bandit counter 更新,纯算术;`_build_trajectory_payload` 是 file-read + dict-assembly,无 filtering / weighting。
3. **多层嵌套禁止** —— `_distill_after_stage1` 单层函数调用,无 wrapper-in-wrapper;`run_skill_via_tools` 已经是 agent 调用的 generic seam,不自己造第二个。
4. **失败行为:** 若 distill agent 在 Stage 1 后产出 0 proposals,`delta_portfolio` 保持空 → Stage 2/3 不跑 trial → ACC-2 失败 → phase 8 reopen。**禁止 fallback 到 hardcoded seed**。这是真阳性边界:agent 没产 delta 就是没产,不补救。

**测试锚点:**
- 新增:
  - `test_distill_after_stage1_with_recording_provider` —— 注入一个 fake provider(返回 valid `DeltaDistillationArtifact`)+ 一个 fake stage1_result → `_distill_after_stage1` 返回 portfolio 含 1+ row。
  - `test_distill_after_stage1_empty_proposals_yields_empty_portfolio` —— 注入 provider 返回 `proposals=[]` → portfolio 保持空,不 raise。
  - `test_distill_after_stage1_invalid_artifact_raises` —— 注入 provider 返回 schema-invalid artifact → `ValidationError` 浮到 caller,fail-fast。

**实测证据:**
- Phase-8 batch Stage 1 完成后,日志含 `distill_after_stage1` node_id 的 tool_loop_summary trace。
- `delta_portfolio` 在 Stage 1 结束时 *non-empty*(数量由 agent 决定,不强制阈值)。
- Stage 2/3 期间至少一个请求的 `evolution_snapshot.json` 含 `trial_succeeded` 或 `trial_failed` event,且 `trial.delta_id` 与 distill 产出的某个 proposal 的 `delta_id` 匹配。
- Stage 2/3 结束后,portfolio rows 的 `sample_count` / `success_count` / `failure_count` non-zero(`update_after_trial` 真的把 outcome 折回)。这是 §5.4 metric `trial_belief_update_count > 0` 的来源。

### 3.5 F 接线伪代码

`_run_one_request` 接收 `delta_portfolio` 和 `live_skill_root`(由 Stage 1 后的 distill 填充):

```python
def _run_one_request(
    *, request_id, scenario, nodes, provider_factory, request_dir,
    events: list[dict],
    delta_portfolio: list[DeltaPortfolioRow],  # F:由 distill agent 填充
    live_skill_root: Path,                     # F:用于 trial 的 skill root
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
        # Host request:常规 3-node DAG
        result_paths = runtime.run_request(scenario=scenario, nodes=list(nodes))
        # ... existing artifact 解析 ...

        # F 接线:host 成功后,对 portfolio 中每个 row 跑一次 trial
        # delta_portfolio 由 _distill_after_stage1 填充;Stage 1 时 portfolio 为空,for 循环空跑
        for portfolio_row in delta_portfolio:
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
                events=events,
            )
            if trial_outcome.trial_delta_id is not None:
                record["trial_selected_delta_id"] = trial_outcome.trial_delta_id
            # 把 outcome 折回 portfolio belief counters(算法,非启发式)
            from seers_harness.evolution.delta_portfolio import update_after_trial
            portfolio_row = update_after_trial(portfolio_row, trial_outcome)
    finally:
        # existing finally: _cv.reset, flush_evidence, write_evolution_snapshot
        ...
    return record
```

**`_patch_from_portfolio_row`** 是纯 transform:读 `portfolio_row.target_skill` 对应 live file,计算 sha256,构造 `SkillDeltaPatch`。如果 `proposed_change` 是 textual 的(SKILL.md 文本替换),直接构造 patch;如果 `proposed_change` 是更高级的指令(如 "add a new tool"),phase 8 范围内只支持 textual modify_skill case,其他类型直接 skip(`portfolio_row.change_type` 不是 `"modify_skill"` 时跳过)。

```python
def _patch_from_portfolio_row(row: DeltaPortfolioRow, live_skill_root: Path) -> SkillDeltaPatch | None:
    """从 portfolio row 构造可应用的 patch。

    phase 8 范围:只支持 modify_skill 类型 + 文本替换。其他类型返回 None(skip)。
    proposed_change 是 agent 产出的 full replacement_text。
    """
    if row.change_type != "modify_skill":
        return None
    live_target = live_skill_root / row.target_skill
    if not live_target.exists():
        return None  # agent 引用了不存在的 skill,skip 而不 raise(D8-VAL-ROOTCAUSE:不掩盖)
    live_text = live_target.read_text(encoding="utf-8")
    return SkillDeltaPatch(
        target_path=row.target_skill,
        original_text_sha256=sha256_of_text(live_text),
        replacement_text=row.proposed_change,
    )
```

**`_run_stage` 调用点更新:**
```python
record = _run_one_request(   # B 项落在 tool_loop,这里不再 wrap
    request_id=rid,
    scenario=scenario,
    nodes=nodes,
    provider_factory=provider_factory,
    request_dir=request_dir,
    events=events,
    delta_portfolio=delta_portfolio,    # F 接线
    live_skill_root=live_skill_root,    # F 接线
)
```

`run()` 函数需要把 `delta_portfolio`(在 Stage 1 后被 `_distill_after_stage1` 替换)和 `live_skill_root` 一路传给 `_run_stage` 再传给 `_run_one_request`。

### 3.6 F 接线测试锚点

- 现有:`tests/test_trial_runner_smoke.py`(phase-6 baseline)。
- 新增:
  - `test_run_one_request_fires_trial_when_portfolio_nonempty` —— inject agent-produced portfolio (DeltaPortfolioRow 含 valid `change_type=modify_skill` + `proposed_change=full replacement text`) + fake provider → 跑 1 个请求 → `evolution_snapshot.json` 解析后 `trials[]` 非空 + outcome.success=True。
  - `test_run_one_request_skips_trial_when_portfolio_empty` —— empty portfolio(模拟 Stage 1 / distill 前)→ `trials[]` 为空,host request 仍成功(D-18)。
  - `test_run_one_request_trial_failure_does_not_abort_host` —— inject portfolio + provider 在 trial 中 raise → host record.exception is None, evolution_snapshot 含 `trial_failed`。
  - `test_run_one_request_skips_non_modify_skill_delta` —— portfolio row `change_type="add_skill"` → skip 不 raise(phase 8 范围内只支持 modify_skill)。
  - `test_run_one_request_skips_drifted_target_path` —— portfolio row `target_skill` 不存在 → skip,不 raise。
  - `test_distill_after_stage1_with_recording_provider` —— fake provider 返回 valid distill artifact + fake stage1 evidence dir → `_distill_after_stage1` 返回 portfolio 含 1+ row。
  - `test_distill_after_stage1_empty_proposals_yields_empty_portfolio` —— provider 返回 `proposals=[]` → portfolio 空,不 raise。
  - `test_distill_after_stage1_invalid_artifact_raises` —— provider 返回 schema-invalid artifact → `ValidationError` 浮到 caller。
  - `test_run_drives_distill_only_after_stage1_passes` —— inject failing Stage 1 → distill 不被调用;passing Stage 1 → distill 被调用恰一次。

### 3.7 F 接线实测证据(真阳性边界)

**ACC-2 verbatim:** `evolution_snapshot.json` 含至少 1 个非空 `trials[]`。**但这是假阳性下限** —— phase 8 真阳性需要见 §5.4 行为度量。

Phase-8 batch 完成后:
```bash
# 1. distill agent 在 Stage 1 后真的跑了(audit log)
grep -E "node=distill_after_stage1" tests/smoke/.runs/<phase-8-ts>/.../runner-*.log
# 期望:1 行 tool_loop_summary 事件

# 2. trials[] 非空 + delta_id 与 distilled proposal 一致
find tests/smoke/.runs/<phase-8-ts>/ -name evolution_snapshot.json \
  -exec python -c "import sys,json; d=json.load(open(sys.argv[1])); \
  trials=d.get('trials',[]); \
  print(sys.argv[1], 'trials:', len(trials), 'delta_ids:', [t.get('delta_id') for t in trials])" {} \;
# 期望:Stage 2/3 至少一个请求 trials >= 1,delta_id 是 agent 产出的 id 而非 'phase-8-seed-001'

# 3. portfolio belief 真的被 update_after_trial 折回(IN-01 + F 闭环证据)
# 在 batch 结束后 dump portfolio state(如果 runner.py 暴露的话);否则在单测验证
```
**真阳性最低门槛(用户 2026-05-27 框架):**
- distill agent 在真 trace 上跑通,产出 ≥1 DeltaProposal(由 agent 决定数量,非阈值)
- 至少一个 Stage 2/3 请求 fire trial,delta_id 来源于 distill artifact
- trial outcome 的 `success` / `failure_category` / `token_cost_observed` 全部 non-default
- `update_after_trial` 折回的 portfolio row `sample_count` >0 — 见 §5.4 metric M5

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
| A | `test_provider_timeout_default_180s` + `test_deepseek_runtime_facts_default_timeout_180s` | `tests/test_provider_openai_compatible.py` |
| B (×4) | tool_loop backoff 路径(0s/5s/15s 序列 / 不重试 auth / 耗尽 budget / 首次 attempt 不 sleep) | `tests/test_tool_loop.py`(若存在;否则补建) |
| C | `test_parse_retry_log_present_on_retry`(C 项需新增 1 行 log)| `tests/test_provider_openai_compatible.py` |
| D (×5) | 见 §2-D 测试锚点 | `tests/test_validation_runner.py` |
| E (×3) | `failure_class` mapping + index 集成 + summary 聚合 | `tests/test_exception_classifier.py`, `tests/test_index_writer.py`, `tests/test_batch_summary_writer.py` |
| F 接线 (×5) | 见 §3.6 测试锚点(run_one_request 分支 + distill agent 路径)| `tests/test_validation_runner.py`, `tests/test_trial_runner_smoke.py` |
| WR-01 | `test_stage3_fail_fast_drains_inflight` | `tests/test_validation_runner.py` |
| WR-02 | `test_finally_writer_failure_does_not_mask_original` | `tests/test_validation_runner.py` |
| WR-03 | N/A(纯删除,grep verify) | — |
| WR-04 callsite | grep verify `_current_node_id as _cv` 不存在 | — |
| WR-05 | `test_trial_runner_reraises_provider_errors`、`test_trial_runner_catches_schema_violation` | `tests/test_trial_runner_smoke.py` |
| IN-01 | `test_trial_outcome_token_cost_from_trace_usage`、`test_trial_outcome_token_cost_zero_when_no_usage` | `tests/test_trial_runner_smoke.py` |
| IN-08 | grep verify `_PROVIDER_BUDGET_KEY` 不存在 + `deepseek_provider_from_env(max_retries=3)` 在 runner 中 | — |
| **行为度量 M1-M5** | `test_machine_judges_factor_diversity`、`test_machine_judges_copy_diversity`、`test_machine_judges_reflection_trigger_rate`、`test_machine_judges_delta_diversity`、`test_machine_judges_belief_update_count` | `tests/test_machine_judges.py`(新增 5 个 judge 函数 + 5 个测试) |

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

### 5.4 实测证据矩阵(逐 Deliverable × Pass Criterion)

每个 deliverable 的实测证据分两栏:**Firing 证据**(模块跑了)+ **真阳性证据**(模块做对了)。若 batch 自然条件下未触发该路径,planner 标注"pytest 是唯一证据",**禁止伪造实测证据(D8-VAL-REAL)**。

| Deliverable | Firing 证据 | 真阳性证据 |
|---|---|---|
| **A** 180s timeout | 任一请求 TTFB 60s-180s 且 `exception is null`(对照 0526 trace 在 60s 处死)| `usage.json.completion_tokens` non-trivial(实际跑完 reasoning model),不是"刚好踩 180s 又被推 transient retry 挡住" |
| **B** tool_loop backoff | `.run-logs/runner-<ts>.log` 若有自然 transient → 该请求出现 `ProviderTransientError` 后下一个 turn 仍成功(隐含 sleep 生效)| 用户决定 Q3 = B:**不在 batch 中混故障注入**;无自然 transient 时 pytest 4 路径单测为唯一证据 |
| **C** CR-05 审计 | 任一 stage 任一请求出现 tool_args 截断 → log 含 `parse_retry node=... attempt=N/M`| 最终该请求 (i) 成功 *或* (ii) `exception=ProviderResponseError` + `failure_class=malformed_tool_args` |
| **D** `--env-file` | log 前 2 行:`env-file: loaded N keys from .env.local` + `DEEPSEEK_API_KEY suffix=****<4chars>`| value 字符串不出现在任何 stderr / artifact / index.json;`DEEPSEEK_API_KEY` 后 4 字符与 `.env.local` 一致(对照 0526 ****92c7 stale-env 401)|
| **E** `failure_class` | 每个 `index.json` row 含 `failure_class`;`batch_summary.json.by_failure_class` 之和 = `totals.requests`| 7 个枚举中 *每个* 在 batch 出现过(自然多样性 + IN-04 后 schema/runner_bug 应当稀少);若一个枚举 0 次,planner 在 batch 报告中标"枚举完备性待后续 batch 验证",非阻塞 |
| **F** evolution wiring | (1) Stage 1 后日志含 `node=distill_after_stage1` tool_loop_summary;(2) `delta_portfolio` 在 Stage 1 结束时 ≥ 1 row;(3) Stage 2/3 至少一个 `evolution_snapshot.json` 含非空 `trials[]`| `trial.delta_id` 来自 distill artifact(不是 hardcoded);trial outcome `success`/`failure_category` non-default;**M4 + M5 双重把关**(见 §5.4b)|
| **WR-01** drain in-flight | IF Stage 3 fail-fast 自然发生:`len(index.json.requests) == 20`,`stage3/<rid>/` 目录数 == 20| 无 fail-fast 时 pytest 是唯一证据 |
| **WR-02** finally best-effort | N/A(IN-04 后罕见)| 实测 batch 中不出现 `flush_evidence failed` 或 `write_evolution_snapshot failed` 日志行(出现 = IN-04 失效,新 finding)|
| **WR-03** 删除 dup `_detect_delimiter` | grep:`_detect_delimiter` 在 `runner.py` 出现次数 = 0,`detect_delimiter` 调用 = 1| N/A pure cleanup |
| **WR-04 callsite** | grep:`_current_node_id as _cv` 在 `runner.py` 出现次数 = 0,`reset_current_node_id` import = 1| N/A pure cleanup |
| **WR-05** trial 异常窄化 | IF trial 期间 DeepSeek auth/rate 错误自然发生:log 显示 `provider_error -> fail-fast`,**无** `trial_failed` 事件携带 provider exception class| 无 provider error 时 pytest 单测为唯一证据(M4 间接验证:trial 跑通就说明 narrow 不误伤)|
| **IN-01** token_cost_observed | F seed delta 触发的 trials 中 `token_cost_observed > 0` 至少一个请求 | M4 中"trial 与 baseline 的 token_cost_observed 差异 ≠ 0"间接验证(M4 也涵盖此 deliverable)|
| **IN-08** max_retries kwarg | grep:`_PROVIDER_BUDGET_KEY` 在 `runner.py` 出现次数 = 0;`deepseek_provider_from_env(max_retries=3)` 出现 = 1| N/A pure cleanup |

### 5.4b 行为度量 — 真阳性验收的 5 个 metric(用户 2026-05-27 锁定)

> 用户对 RESEARCH 原版"trials[] 非空 + token_cost > 0"的真阳性边界提出加强要求(2026-05-27):
> "*挖掘真的能调用 tool 挖掘出足够数量的多角度的个性化,文案生产真的能产出多样化文案,在模型偷懒时真的通过工具反思避免偷懒。进化机制真的在工作,比如 hook 机制触发的好,真的有 delta 产出且有整个流程。*"
>
> 这 5 个 metric 在 `seers_harness/validation/machine_judges.py` 新增 5 个 judge 函数实现,由 `batch_summary.json` 报告。**任一未达阈值 = phase 8 触发 user review,不自动 pass**。所有计算都是 *算法*(set 操作、Jaccard、计数),零启发式 if/elif。

**M1 — 挖掘多样性 `factor_count_p50` ≥ 3**

- **判据:** `factor_discovery/artifact.json` 中 `factors` 数组长度,phase-8 batch 全请求的 p50。
- **算法:** `statistics.median([len(d.factors) for d in all_factor_artifacts])` ≥ 3。
- **失败语义:** 模型偷懒只产 1-2 个 factor 是假阳性(挖掘"成功"但没真正多角度)。
- **阈值依据:** RESEARCH 推荐值 3,用户 2026-05-27 接受。

**M2 — 挖掘角度分布 `factor_diversity_score` ≥ 0.5**

- **判据:** Phase-8 batch 中所有 factor 的 `covers_product_ids` 集合两两 Jaccard 距离的均值 + `transferable_disposition` token-level 离散度(Jaccard distance)。
- **算法(`machine_judges.compute_factor_diversity`):**
  ```python
  def compute_factor_diversity(all_artifacts: list[dict]) -> float:
      ids_sets = [frozenset(f["covers_product_ids"]) for d in all_artifacts for f in d["factors"]]
      texts = [_tokenize(f["transferable_disposition"]) for d in all_artifacts for f in d["factors"]]
      if len(ids_sets) < 2: return 0.0
      ids_distance = mean(1 - len(a & b)/len(a | b) for a, b in combinations(ids_sets, 2) if a or b)
      text_distance = mean(1 - len(a & b)/len(a | b) for a, b in combinations(texts, 2) if a or b)
      return (ids_distance + text_distance) / 2
  ```
- **失败语义:** 所有 factor 都是同一角度(高 token 重叠)= 模型用模板填充,挖掘失败。
- **阈值依据:** 0.5 = "平均 50% token 不重叠",是较弱真阳性边界(挖掘真正分散);用户 2026-05-27 接受 RESEARCH 推荐。

**M3 — 文案多样性 + 反思触发率(合并 metric)**

- **判据 M3a `copy_candidate_count_p50` ≥ 2:** `copy_generation/artifact.json.considered_drafts` 数组长度 phase-8 batch p50 ≥ 2。
- **判据 M3b `reflection_triggered_when_underspec_rate` ≥ 0.8:** 当 `factor_count < 3` 时,该请求的 `tool_calls.jsonl` 应该出现 `reflect_on_coverage` 或 `reflect_on_diversity` 调用。"当 factor 不足时反思触发"的比率 ≥ 80%。
- **算法:**
  ```python
  def compute_copy_diversity(all_artifacts: list[dict]) -> float:
      return statistics.median([len(d["considered_drafts"]) for d in all_artifacts])

  def compute_reflection_trigger_rate(per_request: list[tuple[int, list[str]]]) -> float:
      """per_request: list of (factor_count, [tool_names called in factor_discovery node]) tuples"""
      underspec = [tools for fc, tools in per_request if fc < 3]
      if not underspec: return 1.0  # 没有 underspec 请求,trivially pass
      triggered = sum(1 for tools in underspec if any(t.startswith("reflect_") for t in tools))
      return triggered / len(underspec)
  ```
- **失败语义 M3a:** 单一 candidate = 模型偷懒,没真正生 multi-draft。
- **失败语义 M3b:** factor 不足时不触发反思 = mirror 机制失效,文案直接基于不足 factor 生成。
- **阈值依据:** M3a = 2(用户 2026-05-27 接受);M3b = 0.8(用户接受,允许 20% 漏触发为 batch 噪声)。

**M4 — 演化 delta 多样性 `delta_diversity_score` > 0(开放,non-trivial)**

- **判据:** distill agent 在 Stage 1 后产出的 `DeltaProposal[]` 中:
  - count ≥ 1(agent 真的产 delta);
  - 若 count ≥ 2:`target_skill` 不全相同(覆盖 ≥ 2 个 skill)*或* `change_type` 不全相同。
- **算法:**
  ```python
  def compute_delta_diversity(proposals: list[DeltaProposal]) -> dict:
      return {
          "count": len(proposals),
          "unique_targets": len({p.target_skill for p in proposals}),
          "unique_change_types": len({p.change_type for p in proposals}),
      }
  ```
- **失败语义:** 0 proposals = distill agent 没真正工作。1 proposal + 后续 batch 都同 skill = 演化 chain 只动一个面。
- **阈值依据:** count ≥ 1 hard 阈值(否则 ACC-2 失败);unique_targets ≥ 2 OR unique_change_types ≥ 2 当 count ≥ 2 时作为软阈值,batch 报告内告警但不阻塞(Stage 1 单一 trace 产单一目标 delta 是 *可能的合理结果*)。

**M5 — 演化 belief 更新 `trial_belief_update_count` > 0**

- **判据:** Stage 2/3 完成后,portfolio 至少一个 row 的 `sample_count` > 0(`update_after_trial` 真的折回 outcome,不是只跑 trial 不更新)。
- **算法:**
  ```python
  def compute_belief_update_count(final_portfolio: list[DeltaPortfolioRow]) -> int:
      return sum(1 for row in final_portfolio if row.sample_count > 0)
  ```
- **失败语义:** trial 跑了但 portfolio 没动 = `update_after_trial` 调用点缺失,演化 chain 断开。
- **阈值依据:** > 0 hard 阈值,这是"全链路"的最后一环。

**M1-M5 实现位置:** `seers_harness/validation/machine_judges.py`(已存在 VAL-01/02/04 模式),新增 5 个 `compute_*` 函数 + 1 个 `build_behavioral_report(stage_dir)` aggregator,写入 `batch_summary.json.behavioral_metrics` 字段。所有计算 *仅* 读取 `index.json` / `evidence/<node>/artifact.json` / `evidence/<node>/tool_calls.jsonl` —— 不调 LLM,纯算术。

**M1-M5 阈值汇总 + 阻塞规则:**

| Metric | 阈值 | 阻塞? | 用户决定来源 |
|---|---|---|---|
| M1 factor_count_p50 | ≥ 3 | **阻塞** | 2026-05-27 RESEARCH 推荐接受 |
| M2 factor_diversity_score | ≥ 0.5 | **阻塞** | 2026-05-27 RESEARCH 推荐接受 |
| M3a copy_candidate_count_p50 | ≥ 2 | **阻塞** | 2026-05-27 RESEARCH 推荐接受 |
| M3b reflection_triggered_when_underspec_rate | ≥ 0.8 | **阻塞** | 2026-05-27 RESEARCH 推荐接受 |
| M4 delta_diversity_score.count | ≥ 1 | **阻塞** | 2026-05-27 用户"hook 机制触发的好,真的有 delta 产出" |
| M4 delta_diversity_score.unique_* | count ≥ 2 时 ≥ 2 | 软告警 | RESEARCH 折衷 |
| M5 trial_belief_update_count | > 0 | **阻塞** | 2026-05-27 用户"真的有 delta 产出且有整个流程" |

**阻塞机制:** 在 `08-VERIFICATION.md` 模板的 acceptance gate 中加一条:"M1-M5 全部达阈值 OR 软告警可解释"。Phase 8 的 verifier 读 `batch_summary.json.behavioral_metrics`,任一阻塞 metric 未达 = phase 8 状态 `gaps_found`,user review 决定是否接受 / 重跑 / 修代码后重跑。**这是 *user 决策*,不是自动 pass。**

### 5.5 实测层验收闸门

- **D8-ACC-1:** 一次 Stage 1+2+3 batch 在 *单一* phase-8 commit 上 end-to-end 完成,零请求因 60s/stale-env/未处理 transient 而 fail-fast。
- **D8-ACC-2:** `evolution_snapshot.json` 含 ≥ 1 个非空 `trials[]`(F 接线 firing 证据;真阳性证据见 M4 + M5)。
- **D8-ACC-3:** `index.json` 每行有 `failure_class`;`batch_summary.json.by_failure_class` 完整。
- **D8-ACC-4:** `pytest -q` 全套通过(单元+集成层 §5.1 + §5.2);新增 M1-M5 单测全绿。
- **D8-ACC-5:** `07-WRIN-TRIAGE.md` 7 个 scheduled 项目移至 phase-8 commit ref。
- **D8-ACC-6:** `08-VERIFICATION.md` 状态 `passed`,**含 M1-M5 全部达阈值或 user 显式接受软告警**。

任一 deliverable 在 §5.4 矩阵中没有可验证证据,**或** M1-M5 任一阻塞 metric 未达,= phase 8 仍 reopen。

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
| 1 | A | `openai_compatible.py`(timeout 默认值)| 单独 |
| 2 | D | `runner.py`(main + `_load_env_file`)| 单独 |
| 3 | E | `exception_classifier.py`(`failure_class` 函数)+ `runner.py`(record 字段)+ `index_writer.py` + `batch_summary_writer.py` | 单独 |
| 4 | WR-03 | `runner.py`(删除 dup `_detect_delimiter`)| 单独(可与 WR-04/IN-08 合并)|
| 5 | WR-04-callsite | `runner.py`(改用 `reset_current_node_id`)| 同上 |
| 6 | IN-08 | `runner.py`(`max_retries` kwarg)| 同上 — "runner 清理三件套" |
| 7 | F 接线 | `runner.py`(`_run_one_request` + `_run_stage` + `run` + `_distill_after_stage1`)+ `_patch_from_portfolio_row` helper | 单独,大 commit |
| 8 | IN-01 | `trial_runner.py`(token_cost_observed 写入)| 紧跟 F |
| 9 | M1-M5 行为度量 | `machine_judges.py`(5 个 `compute_*` + `build_behavioral_report`)+ `batch_summary_writer.py`(append 字段)| 紧跟 IN-01(在 IN-01 之后,因为 M5 依赖 portfolio 更新 + IN-01 的 token_cost)|
| 10 | B | `tool_loop.py`(已有 retry 点加 backoff)| 单独;**注意:不修 runner.py**,这是关键审美约束 |
| 11 | WR-01 | `runner.py`(Stage 3 fail-fast drain)| 单独 |
| 12 | WR-02 | `runner.py`(finally best-effort wrap)| 单独 |
| 13 | WR-05 | `trial_runner.py`(narrow `except Exception`)| 单独 |
| — | C 审计 | 跑实测 batch,读 log | 不产生代码 commit(除非 audit log 行需要补 → 在 §2-C 标注的"附带修改")|

总计:13 个原子 commit + 1 个审计步骤,符合 GSD 原子 commit 规范。

> **Wave 标号说明(advisory,plan-checker ISSUE-02 应对):** 本 phase 的 plan wave 字段是 *advisory grouping*(逻辑分组),不严格遵循"wave = max(深度依赖)+1"的并行执行模型。原因:phase 8 是 13 个串行 commit(每个 plan 单独 commit + 必要时 cherry-pick),不存在 wave 内并行执行的实际场景。`depends_on` 链已经表达完整序关系。Plan 06 标 wave 3 但 dep 是 wave 3 的 plan 05 —— 表示 "06 紧跟 05,语义上属于同一组(F 接线 + IN-01 token cost)";同理 wave 6 (09/10/11) 表示"trio of touch-new-wiring 收尾",顺序串行 (09→10→11) 由 depends_on 锁定。Execute-phase 工作流读 depends_on 串行执行,wave 字段仅用于 ROADMAP annotation 的可读性分组。

### 7.3 风险缓解

- **大 commit 风险(F):** F 接线是单 commit 中最大的改动。Planner 应在 F 的 PLAN 中拆分 task 但保持单 commit —— 接线 + 单测在同一个 commit。如果需要拆,拆为"(F-1) `_distill_after_stage1` + `_build_trajectory_payload`","(F-2) `_run_one_request` 接线 trial loop + `_patch_from_portfolio_row`","(F-3) `_run_stage` 调用点更新 + run() 装配"三个 commit。这三者互相支撑,无 IN-01 token cost 接入会让 M4/M5 后续验证缺数据,**推荐保持 F 单 commit + IN-01 + M1-M5 紧随**。
- **B 项粒度风险:** B 落在 `tool_loop.py` 而非 `runner.py`,这意味着影响面 *扩大* 到所有 `run_skill_via_tools` 调用点(`dag_runner` + `_distill_after_stage1`)。这是 *好事* —— 整个 harness 的 transient retry 都获得 backoff,不只 runner。但要确认没有现有调用点假设无 backoff 行为(grep `run_skill_via_tools` 调用点,无 sleep mock 期望即可)。

---

## 8. 未决问题(2026-05-27 已 resolve)

原 §8 的 3 个 open questions 在用户 2026-05-27 kick-off 时全部锁定:

1. **Q1 `SchemaError` 别名:** 锁定为 `pydantic.ValidationError`(`failure_class` 函数中 `isinstance(exc, pydantic.ValidationError) → "schema_violation"`)。
2. **Q2 种子 delta:** 撤回 C3 hardcoded seed,**改 C4 — distill agent 在 Stage 1 后从真 trace 算法提取 delta,Stage 2/3 跑该 delta 的 trial**。完整闭环 distill → portfolio → trial → update_after_trial。
3. **Q3 故障注入:** 选 B,**不在 phase-8 batch 中混故障注入请求**。B 项实测证据仅限自然 transient;无自然 transient 时 pytest 4 路径单测为唯一证据。

新增的真阳性 5 个行为度量(M1-M5)+ 阻塞规则在 §5.4b 锁定。Planner 不再需要询问用户即可写 PLAN。

## RESEARCH COMPLETE

- 文件已写到 `.planning/phases/08-evolution-wiring-and-runner-debt/08-RESEARCH.md`,8 大节齐全(含 `## Validation Architecture` 让步骤 5.5 触发)。
- Group A-E + F + G(7 个 WR/IN)所有 deliverable 都精确到 file:line,伪代码就位。**B 项重构:** 落在 `tool_loop.py` 已有 retry 点上加 backoff,不在 runner.py 外起 wrapper(避免多层嵌套 + finally 重复 flush)。
- **F 项 C4 路径锁定:** distill agent 在 Stage 1 后跑 `run_skill_via_tools(skill="distill-skill-deltas", ...)` 从真 trace 提 delta,Stage 2/3 trial。完整闭环。零 hardcoded seed。
- **新增 5 个行为度量(M1-M5)阻塞验收:** factor 多样性 / 文案 multi-draft / 偷懒时反思触发率 / delta 多样性 / belief 更新计数。算法实现(Jaccard、median、计数),零启发式。
- 测序复核:F 之后 IN-01,IN-01 之后 B,B 之后 WR-01/02/05。Planner 用此序写 PLAN(11-12 commit)。
- 用户的 3 个 Q 全部已 resolve;§8 已更新。Planner 可直接写 PLAN。
