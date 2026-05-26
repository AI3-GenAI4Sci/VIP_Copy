---
phase: 07-real-llm-validation
reviewed: 2026-05-26T13:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - seers_harness/evolution/delta_portfolio.py
  - seers_harness/evolution/trial_runner.py
  - seers_harness/validation/__init__.py
  - seers_harness/validation/batch_summary_writer.py
  - seers_harness/validation/evidence_writer.py
  - seers_harness/validation/evolution_snapshot.py
  - seers_harness/validation/exception_classifier.py
  - seers_harness/validation/index_writer.py
  - seers_harness/validation/machine_judges.py
  - seers_harness/validation/recording_provider.py
  - seers_harness/validation/runner.py
findings:
  critical: 4
  warning: 6
  info: 8
  total: 18
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-05-26T13:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 7 的三层（capture / writer / runner）总体职责切分清晰：
* **D-22(d) 分层**：grep `recording_provider` / `evidence_writer` 在 `index_writer.py` / `batch_summary_writer.py` / `machine_judges.py` 中 — 均无导入。layering 正确。
* **D-22(b) 文件布局**：`evidence_writer` 的 per-node JSONL/JSON 形状与 plan 一致。
* **D-08 内容中立**：`RecordingProvider.generate_with_tools` 没有 try/except 包住内层调用，异常透传 — 满足 D-08。
* **D-11 byte-identical 默认**：`delta_portfolio.assemble_portfolio` 与 `trial_runner.run_request_trial` 的 `events is not None` 守卫一致；空列表 `[]` 与 `None` 行为不同（前者 append、后者跳过），符合 plan。

但仍发现若干会影响真实运行正确性 / 安全性的缺陷：D-19 分类器对 `__cause__` 链盲点（已被 live run 证实）、API key 经 exception message 落盘到 `index.json`、CLI 标志（`--csv` / `--num-requests`）被声明却完全不传给 `run()`、以及 `evidence_writer` 对 `node_id` 没有做路径清理。下面按严重度逐项列出。

---

## Critical Issues

### CR-01: `classify()` 不检查 `__cause__` — 已被 live run 证实把 provider 401 误判为 `infra_error`

**File:** `seers_harness/validation/exception_classifier.py:94-107`
**Issue:**
`classify(exc)` 只对最外层 `exc` 做 `isinstance` 比对，模块 docstring 也明确写道「never the cause chain」。然而 `seers_harness/workflow/dag_runner._run_node` 会把真正的 provider 异常包装成 `RuntimeError("Node X failed after 1 attempts")` 再 re-raise（`__cause__` 指向真实异常）。结果：当 DeepSeek 返回 401（`ProviderAuthError`），到达 stage runner 的是 `RuntimeError`，被分类为 `infra_error` 而非 `provider_error`。phase_context 已注明这是 live failure 的实际表现。后果是路由文案错误，但更要紧的是**异常分类不可信** — 任何位于上游 wrapper 之后的真实 provider 错误都会落到 default `infra_error` 桶。

**Why it matters:** D-19 路由是 stage runner 决定 fail-fast 行为的唯一开关；分类错误会让用户看到「infra_error」却找不到对应的代码 bug，浪费定位时间。
**Fix:**
```python
def classify(
    exc: BaseException,
) -> Literal["trial_failure", "provider_error", "infra_error"]:
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, TrialFailure):
            return "trial_failure"
        if isinstance(cur, _PROVIDER_EXCEPTION_TYPES):
            return "provider_error"
        cur = cur.__cause__ or cur.__context__
    return "infra_error"
```
同时把模块 docstring 中「never the cause chain」改成「walks the cause/context chain so wrapped provider exceptions still route correctly」。

---

### CR-02: `--csv` 和 `--num-requests` 被声明但从未传给 `run()` — 用户给的 CLI 标志被静默丢弃

**File:** `seers_harness/validation/runner.py:807-836`
**Issue:**
`main()` 中 argparse 注册了 `--csv` 与 `--num-requests`，但调用 `run()` 时只传了 `stages` 与 `out_dir`，且 `run()` 的签名也没有对应形参。结果是用户传 `--csv /alt/path.csv --num-requests 10` 会被 argparse 接受、被代码完全忽略，仍然走 `data_100k.csv` 的前 20 条。这是 silent CLI breakage（命令通过、行为错误）。

**Why it matters:** 让运维拿这两个标志去复跑 / 缩量调试时无法生效；更糟的是错误地把 `--num-requests=1` 传给 Stage 3 这种致命用法不会被拒绝。
**Fix:** 在 `run()` 签名中加 `csv: Path | None = None, num_requests: int | None = None`，把 default `_default_scenario_loader` / `_default_request_ids_provider` 重构成接收这两个参数的工厂函数，并在 `main()` 中把 `args.csv` / `args.num_requests` 传给 `run(...)`。或者，如果决定 v1 不支持这两个标志，请直接从 argparse 中删除以避免误导。

---

### CR-03: 异常 message 直接被写入 `index.json` 与 stderr — 可能持久化 DeepSeek API key

**File:** `seers_harness/validation/runner.py:567, 622, 588, 639` (以及 `seers_harness/validation/evolution_snapshot.py:86-88` 间接持久化)
**Issue:**
fail-fast / trial-failure 路径里把异常以 `f"{type(exc).__name__}: {exc}"` 写到 `record["exception"]`，再经 `write_index` 落盘到 `index.json`；同样的字符串还透过 `traceback.print_exc(file=sys.stderr)` 打印到 stderr。OpenAI SDK 的 `AuthenticationError` 在某些后端版本下会把请求 header 摘要（含 `Authorization: Bearer sk-...`）作为 message 暴露，DeepSeek 兼容层透传时也可能把 key 前缀带进 `ProviderAuthError`。一旦这种 message 被 `f"{exc}"` 抓到 `index.json`，evidence 目录虽然 git-ignored，仍是一个长期残留在磁盘上的明文 key 副本。`evolution_snapshot.json` 里 `exception_message` 同样有这个风险（trial_runner.py:236）。

**Why it matters:** phase_context 明确写「no key in error messages」。把异常字符串生写到 index 文件就是「key in error messages」的执行链上一步，且 `tests/smoke/.runs/` 即便 git-ignored 也会被 share/sync/截屏分享。这是 secret 落盘风险，必须屏蔽。
**Fix:** 在写 `record["exception"]` 与 `event["exception_message"]` 前对 message 做白名单处理（只保留 class name + 长度上限），或调用一个 `_redact(message)` helper 把 `sk-[A-Za-z0-9_-]+`、`Bearer\s+\S+`、`Authorization[: ]+\S+` 这类 pattern 替换成 `<redacted>`。并对 `traceback.print_exc(...)` 同步走 `redact` 包装。例如：

```python
import re
_SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_\-]+|Bearer\s+\S+|Authorization[:= ]+\S+)", re.I)
def _safe_exc(exc: BaseException) -> str:
    return _SECRET_RE.sub("<redacted>", f"{type(exc).__name__}: {exc}")[:512]
```

并在两处 `f"{type(exc).__name__}: {exc}"` 替换为 `_safe_exc(exc)`；`exception_message` 也走相同函数。

---

### CR-04: `evidence_writer` 对 `node_id` 没有路径清理 — `..` / 绝对路径会逃逸 `out_dir`

**File:** `seers_harness/validation/evidence_writer.py:81-87`
**Issue:**
`node_dir = base / node_id` 直接把字典里的 `node_id` 当作子目录名拼接，没有任何 sanitisation。`Path("/tmp/runs") / "../../../etc/foo"` 会产出 `/etc/foo`；`Path("/tmp/runs") / "/abs"` 会跳到 `/abs`。`node_id` 来源是 RecordingProvider 写入的 `record["node_id"]`，最终源头有两条：
1. `generate_with_tools(node_id=...)` 的 kwarg — 由 dag_runner 传入，为 NodeSpec.id（受我们控制）；
2. ContextVar fallback — runner 中用 `set_current_node_id(request_id)`，而 request_id 来自 `data_100k.csv`。

虽然今天 (1) 来自配置内、(2) 来自项目 CSV，攻击面有限，但写入器作为「可能跨场景被 reuse」的 utility，应该在写入前就拒绝任何 `..`、绝对路径或 `/`、`\`、`:` 组合。phase_context 也直接点了这条。

**Why it matters:** 一旦未来 07-06 把 `node_id` 链路接到任何 LLM 输出 / 用户提供的 scenario 字段（trial 命名规则、reflow 命名等），此处即变为目录穿越漏洞，可写入 `tests/smoke/.runs/<ts>/../../.git/hooks/pre-commit` 这类敏感路径。
**Fix:**
```python
import os.path
def _sanitise_node_id(raw: str | None, fallback: str) -> str:
    if not isinstance(raw, str) or not raw:
        return fallback
    cleaned = raw.replace("/", "_").replace("\\", "_").replace(":", "_")
    cleaned = cleaned.lstrip(".")  # drop leading dots so ".." cannot escape
    if not cleaned or cleaned in {".", ".."}:
        return fallback
    return cleaned

# in _flush_one:
node_id = _sanitise_node_id(record.get("node_id"), f"req_{index:04d}")
node_dir = base / node_id
# defence-in-depth: refuse if the resolved path leaves base
if os.path.commonpath([node_dir.resolve(), base.resolve()]) != str(base.resolve()):
    raise ValueError(f"node_id escaped out_dir: {raw!r}")
```

`runner._safe_request_dirname` 同样只 replace `/` 与 `:`，对 `..` 不防御 — 建议同函数化。

---

## Warnings

### WR-01: Stage 3 fail-fast 后已在执行的 future 的结果被丢失 — `index.json` 与 disk evidence 不一致

**File:** `seers_harness/validation/runner.py:610-644`
**Issue:**
当某个 future 触发 fail-fast，代码循环 `future_to_rid` 调 `other.cancel()` 并 `break`。`Future.cancel()` 只能取消尚未开始的 future；已经在 worker 里跑的 future 会继续运行至完成。但 `for fut in as_completed(...)` 已经被 `break`，他们的 `result()` 永远不会被收集进 `records`。最终：
* `_run_one_request` 的 `finally` 还是会跑、把 `messages.jsonl` / `tool_calls.jsonl` 等写到磁盘；
* `index.json` 却完全缺这些行（`records` 没 append）。

这违反 D-02「partial-artifacts-on-disk preserved」的可审计预期 — 审计员看 disk 时有数据，看 `index.json` 时却没有对应的 row。
**Why it matters:** Stage 3 是 c=20 path，fail-fast 时常规会有 10+ 个 in-flight 请求。这些请求最有研究价值（live concurrency 边界），却被 index 漏记。
**Fix:** 把已经收集到的 `records` 之外，再排空一轮：在 `break` 之前把 `future_to_rid` 中所有「已 done 且未在 records 里」的 future 的 result/exception 收回；或者改成 `wait=True` 并继续遍历剩余 `as_completed` 结果，只是不再「提早 break」 — 在 `failure_exc is not None` 后续仍把 future result 转成 fail_record 入 records，但不再处理新错误。最朴素：

```python
for fut in as_completed(future_to_rid):
    rid = future_to_rid[fut]
    try:
        record = fut.result()
    except BaseException as exc:
        record = _fail_record(rid, exc)
        if not is_trial_failure(exc) and failure_exc is None:
            failure_exc = exc  # 记录但不 break
    records.append(record)
```

---

### WR-02: `_run_one_request` 的 `finally` 中 `write_evolution_snapshot` 会覆盖原始 exception

**File:** `seers_harness/validation/runner.py:476-494`
**Issue:**
当 `runtime.run_request` 抛错时，控制流进 `finally`。`finally` 内部执行 `flush_evidence(...)` 与 `write_evolution_snapshot(...)`。一旦后者本身抛错（例如磁盘满、`request_dir` 权限不够、events 列表里被往里塞了非 dict 而 reducer 又不是 100% 鲁棒 — 见 IN-04），原始 exception 会被这个新 exception 覆盖，stage runner 拿不到真正的失败原因。
**Why it matters:** Phase 7 的 evidence 价值在于失败现场 — 一个 cleanup-time 的 IO 错误把根因换掉，会把 audit 引向错误方向。
**Fix:** 把 `flush_evidence` 与 `write_evolution_snapshot` 各自包一层 `try / except Exception: traceback.print_exc(...); pass`，确保 cleanup 错误只 log、不传播。注释说明这与 D-22(b) "best-effort post-mortem" 的精神一致。

---

### WR-03: `runner._default_scenario_loader` 重复实现 `_detect_delimiter` 且 import 了未使用的 `detect_delimiter`

**File:** `seers_harness/validation/runner.py:264-268, 336-344`
**Issue:**
导入：
```python
from seers_harness.intake.request_preprocessor import (
    detect_delimiter,
    preprocess_request_from_csv,
)
```
但 `detect_delimiter` 全文未使用，runner 自己又写了一份 `_detect_delimiter`（line 336-344）。两份实现：counts 比较时使用 `max(counts, key=counts.get)`，行为应该一致，但细节上工坊代码用 `";"` 兼容、本地版没有；任何 upstream 修复都会绕过 runner，产生静默 drift。
**Why it matters:** 不是即时 bug，但是「同一个语义在两处写两遍」典型的 quality 退化点；下次审计 csv 行为时不会想到 runner 自带一个副本。
**Fix:** 删除本地 `_detect_delimiter`，直接调用 import 的 `detect_delimiter(csv_path)`；或者把 import 删掉以表明 runner 真的是独立副本（不推荐）。

---

### WR-04: 通过私有名字 `_current_node_id` 的 alias 在 finally 里 reset — 跨模块私有依赖

**File:** `seers_harness/validation/runner.py:480-485`
**Issue:**
```python
from seers_harness.validation.recording_provider import (
    _current_node_id as _cv,
)
_cv.reset(token)
```
`_current_node_id` 是 recording_provider 的私有 ContextVar（前缀下划线明确标记）。runner 跨模块访问私有名字来 reset。recording_provider 已经导出了 `set_current_node_id` / `get_current_node_id`，少一个 `reset_current_node_id(token)` 公共 helper。
**Why it matters:** 一旦 recording_provider 重命名 `_current_node_id`（这是合法的、它是私有的），runner 静默断裂；外加 `try/except Exception: pass` 把这种断裂彻底吞掉，不会再出现错误。
**Fix:** 在 `recording_provider.py` 添加：
```python
def reset_current_node_id(token: contextvars.Token) -> None:
    _current_node_id.reset(token)
```
然后 runner 改用 `reset_current_node_id(token)`，并去掉 `try/except Exception: pass`（reset 是确定性的，不需要兜底）。

---

### WR-05: `run_request_trial` 把所有 `Exception` 都吃掉 — 与 D-19 fail-fast 在 07-06 集成时会冲突

**File:** `seers_harness/evolution/trial_runner.py:226-238`
**Issue:**
```python
except Exception as exc:
    outcome.success = False
    outcome.failure_category = type(exc).__name__
    if events is not None:
        events.append(...)
```
这里不 re-raise — 任何 trial 内异常都被「降级」为 outcome 字段。注释也是这么说的。但这意味着：当 07-06 接通 trial 后，**provider auth / rate-limit 等本应 fail-fast 的错误**也会被这层 wrapper 吞掉，host 请求会无声继续。`exception_classifier.classify` 由于 trial 路径不再抛出，永远不会看到这些异常。
**Why it matters:** 与 D-19 routing 直接矛盾 — D-19 三标签「provider_error -> fail-fast」设计前提是 provider 异常会真正往上传，但 trial wrapper 截断了路径。当前 07-04 stage runner 不调 `run_request_trial`，矛盾还没显形；07-06 一旦接通即爆。
**Fix:** 把 `except Exception` 收窄成对一组「期望被降级」的异常类列表（schema-validation、tool-shape、`TrialFailure`、`AssertionError` 等），其它异常 re-raise。或在 `except` 中先 `if isinstance(exc, _PROVIDER_EXCEPTION_TYPES): raise` 再做降级。任何修改都需在 07-01 PLAN must-haves 中追加一行说明，再让 07-06 PLAN 引用。

---

### WR-06: trial `exception_message` 写入 `evolution_snapshot.json` — 同 CR-03 的二级泄漏面

**File:** `seers_harness/evolution/trial_runner.py:230-238`, `seers_harness/validation/evolution_snapshot.py:86-88`
**Issue:**
`trial_failed` 事件携带 `exception_message: str(exc)`，最终通过 `write_evolution_snapshot` 落盘到 `evolution_snapshot.json`。如果 trial 内部抛出携带 key 的 provider 异常（参见 WR-05 分析），message 会被 verbatim 持久化到 evidence 目录的 JSON 文件里。这是 CR-03 在 trial 这一支路上的镜像问题。
**Why it matters:** 与 CR-03 的修法应该一致。
**Fix:** 在 `trial_runner.run_request_trial` 写 event 前对 `str(exc)` 调用同一份 `_redact()` helper（建议把 helper 放进 `seers_harness/validation/_secrets.py` 类似的工具模块，让 capture/runner 双层共用）。

---

## Info

### IN-01: `TrialOutcome.token_cost_observed` 是死字段，从未被赋值

**File:** `seers_harness/evolution/trial_runner.py:151`
**Issue:** `token_cost_observed` 字段 `default=0`、`run_request_trial` 内部也没有任何代码写它。Docstring 提到「Callers with provider-side usage data can override」但今天没有任何 caller 这么做。
**Fix:** 要么在 `run_request_trial` 里从 `runtime.trace` 中累计 token usage 并赋值，要么先把字段连同 docstring 一起删掉，待 07-06 补回。

---

### IN-02: `judge_val02` 把 `True` / `False` 当成合法 product id

**File:** `seers_harness/validation/machine_judges.py:90-97`
**Issue:** `isinstance(True, int)` 在 Python 中是 `True`，所以 `[True, False]` 这类列表会通过 VAL-02 检查。
**Fix:** 把 `if not isinstance(item, (int, str)):` 加一层 `isinstance(item, bool)` 排除：

```python
if isinstance(item, bool) or not isinstance(item, (int, str)):
    return False, f"covers_product_ids[{index}] not int/str"
```

---

### IN-03: `extract_literal_overlap` 对中文文本只切出 1 个 token，behaviour 与名字不符

**File:** `seers_harness/validation/machine_judges.py:191-226`
**Issue:** 函数 docstring 说 "language-agnostic"。但 `"这是一个测试".split()` 返回 `["这是一个测试"]`，整段视为单一 token。当 user_signal 与 disposition 都是中文时，Jaccard 几乎只在两端文本完全相同时才 ≠ 0。E4 排序会几乎完全无效。
**Why it matters:** 不是 bug（行为有 docstring 背书）但 E4 这条 D-16 维度对中文 evidence 几乎不工作 — case-analysis 阶段如果依赖 E4 排序会得到误导性结果。
**Fix:** 在 docstring 顶层加一行警告，并在 07-05 的 case-analysis template 里显式说明「E4 在中文场景下退化」；或者把 split 换成「逐字符 + 长度阈值过滤」近似（unicode codepoint set 的 Jaccard）。

---

### IN-04: `write_evolution_snapshot` 对 `events is None` / 非-list 不防御

**File:** `seers_harness/validation/evolution_snapshot.py:49-63`
**Issue:** 类型注解为 `list[dict]`，但运行时 `for event in events:` 对 `None` 直接抛 TypeError。和 `flush_evidence(request_log, ...)` 的 `for index, record in enumerate(request_log)` 一样不防御。在 finally cleanup 路径里这会与 WR-02 协同放大原异常的覆盖问题。
**Fix:**
```python
if not isinstance(events, list):
    events = []
```
放在函数顶部一行即可。

---

### IN-05: `set_current_node_id(request_id)` 写入的 ContextVar 永远不会被读

**File:** `seers_harness/validation/runner.py:430`, `seers_harness/validation/recording_provider.py:145`
**Issue:** runner 用 `set_current_node_id(request_id)` 把 `request_id` 写进 ContextVar；但 `RecordingProvider.generate_with_tools` 的 `node_id` 是 kwarg-required，且 `resolved_node_id = node_id if node_id is not None else _current_node_id.get()` 中 `node_id` 永远不为 None（dag_runner 一定传）。所以 fallback 分支不可达，contextvar 写入是 dead op。
**Fix:** 要么让 RecordingProvider 接受 `node_id: str | None = None` 并真正使用 fallback；要么删除 runner 中的 `set_current_node_id` / `_cv.reset` 代码块，避免读者误解层间契约。

---

### IN-06: `batch_summary_writer` 在 fail_lists 与 manual_review_queue 中可能出现空字符串 entries

**File:** `seers_harness/validation/batch_summary_writer.py:96-117`
**Issue:** `node_id = str(row.get("node_id") or "")`，当 row 缺 node_id 时会得到 `""`。`fail_val01.append(node_id)` 等会把 `""` 加进列表（`needs_review` 这条被 `if needs_review and node_id` 守卫了）。
**Fix:** 在 `node_id` 为空时跳过 fail_lists 的 append（或追加 sentinel `<missing-node-id-row-{idx}>` 让 audit 仍然知道有这一行）。

---

### IN-07: `manual_review_queue` 截断后实际长度变 31，与 docstring「20-30 entries」轻微出入

**File:** `seers_harness/validation/batch_summary_writer.py:138-141`
**Issue:** 当 overflow > 0：先 `queue[:30]`，再 append sentinel `"<truncated: N more>"` → 长度 31。
**Fix:** 把 cap 改成 29（`queue[:_MANUAL_REVIEW_QUEUE_CAP - 1]`）然后再 append sentinel；或者把 docstring 的范围更新为「up to 31 entries (30 ids + 1 sentinel)」。

---

### IN-08: `_PROVIDER_BUDGET_KEY = "max_" + "retries"` 是 forbid-list scan 规避代码 — 让 grep 反向真值

**File:** `seers_harness/validation/runner.py:248-249`
**Issue:** 注释承认这是为了让 grep `max_retries` 找不到此处。这种「字符串拼接绕检查」反过来会让真正想审 retries 配置的人 grep 不到 — 把审查工具对抗成 noise generator。
**Fix:** 把 forbid-list 的真正语义放到 plan 文档里描述（「runner 不实现 retry 包装」），然后让源码大方写 `max_retries=3`。或者把这个 key 从「runner 直接实例化」中提取出去（让 `_default_deepseek_factory` 不显式传 budget，而是依赖 `deepseek_provider_from_env` 自带的默认值）。

---

_Reviewed: 2026-05-26T13:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
