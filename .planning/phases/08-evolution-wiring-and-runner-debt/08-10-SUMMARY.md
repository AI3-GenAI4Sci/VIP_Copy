---
phase: 08-evolution-wiring-and-runner-debt
plan: 10
subsystem: validation-runner
tags: [runner-debt, finally-best-effort, WR-02, defensive, secrets-redaction]
requires:
  - 08-09 (drain failure_class router locked, baseline 308 tests)
  - 08-04 (reset_current_node_id helper 兜底语义已固化)
  - 08-05 (_run_one_request 签名扩展含 events 参数)
provides:
  - "_run_one_request finally 块对 flush_evidence + write_evolution_snapshot 的 best-effort 包装"
  - "cleanup 失败可观测(stderr `[runner] {writer} failed for {rid}: {redacted_exc}`)但不掩盖原始 try 块异常"
affects:
  - seers_harness/validation/runner.py:662-704
  - tests/test_validation_runner.py:+105 行(3 个新测试 case)
tech-stack:
  added: []
  patterns:
    - "Python finally 反模式修复 — finally 内的清理调用各自包 try/except Exception,只 swallow cleanup 异常,不 swallow 原始异常"
    - "Information-Disclosure 防线复用:cleanup 异常用 safe_exc(redacted) 而非 traceback.print_exc(stack 含 secret 风险)"
key-files:
  created: []
  modified:
    - seers_harness/validation/runner.py
    - tests/test_validation_runner.py
decisions:
  - "捕获 Exception 不捕获 BaseException — KeyboardInterrupt 不被 cleanup 挡住(plan forbid_list 显式约束)"
  - "log 字面值锁定:`flush_evidence failed for {rid}` / `write_evolution_snapshot failed for {rid}` — 单测 grep 这两串作为接线证据"
  - "comment 中描述 redaction 路径用 \"full-stack printer\" 而非 `traceback.print_exc` 字面 — 避免污染 grep 计数(plan 验证项要求 traceback.print_exc 计数与 08-09 后一致 = 3)"
metrics:
  duration: ~9min
  tasks: 1
  files_modified: 2
  tests_added: 3
  baseline_pytest: 308
  final_pytest: 311
  completed_date: "2026-05-27"
---

# Phase 08 Plan 10: finally-best-effort wrap for cleanup writers (D8-G-WR-02)

## 一句话总结

把 `_run_one_request` finally 块里裸调用的 `flush_evidence` 和 `write_evolution_snapshot` 各自包一层 `try/except Exception`,使磁盘写失败不再覆盖原始 try 块的 ProviderError —— 修复 Python finally 反模式;cleanup 异常通过 `safe_exc` 渲染到 stderr(redacted),不用 `traceback.print_exc`(stack 含 secret 风险)。

## 接线诊断

**问题来源**:`07-WRIN-TRIAGE.md` 中 D8-G-WR-02 deferred 项。phase-7 IN-04 在 writer 层加了 None-guard,但 runner finally 端遇到环境性故障(disk full / permission denied)依然能 raise;尤其在 plan 08-05 把 `write_evolution_snapshot(events, ...)` 引到 finally 之后,cleanup 失败的概率非零。

**Python `finally` 语义**:`finally` 块若 raise,会 *覆盖* try 块原始异常 —— caller 看到的是 `PermissionError("disk full")` 而非真因 `ProviderAuthError("rotated key")`,排障时间 +一个数量级。

**修复形态**(`seers_harness/validation/runner.py:662-704`):

```python
finally:
    try:
        reset_current_node_id(token)         # plan 08-04 兜底,语义不动
    except Exception:
        pass
    try:
        flush_evidence(request_log, evidence_dir)
    except Exception as cleanup_exc:
        print(f"[runner] flush_evidence failed for {request_id}: "
              f"{safe_exc(cleanup_exc)}", file=sys.stderr)
    try:
        write_evolution_snapshot(events, request_dir / "evolution_snapshot.json")
    except Exception as cleanup_exc:
        print(f"[runner] write_evolution_snapshot failed for {request_id}: "
              f"{safe_exc(cleanup_exc)}", file=sys.stderr)
```

**关键约束(per plan forbid_list)**:

| 约束 | 落实点 |
|------|--------|
| 捕 `Exception`(非 `BaseException`) | KeyboardInterrupt 不被 cleanup 挡住 |
| `safe_exc(cleanup_exc)` 渲染 | 走 `_secrets.py` 的 `Bearer sk-...` redaction;严禁 `traceback.print_exc` |
| `request_id` 而非 full path | 审计够用,避免 leak FS 拓扑 |
| reset_current_node_id 兜底不动 | plan 08-04 已锁定语义 |

## 测试落地

新增单测(`tests/test_validation_runner.py:+105 行`),3 个 case 覆盖完整真值表:

| Case | try 块 | finally cleanup | 期望 |
|------|--------|-----------------|------|
| A `..._flush_evidence` | `ProviderAuthError` | `flush_evidence` 注入 `PermissionError` | 原 `ProviderAuthError` 浮;stderr 含 `flush_evidence failed for {rid}` |
| B `..._write_snapshot` | `ProviderAuthError` | `write_evolution_snapshot` 注入 `PermissionError` | 原 `ProviderAuthError` 浮;stderr 含 `write_evolution_snapshot failed for {rid}` |
| C `..._happy_path` | 成功(`_FakeRuntime`) | 无故障 | record 正常;stderr **无** `failed for` 行 |

Fault injection 用 `monkeypatch.setattr(runner, "flush_evidence", _raise_perm_error)` 形式,辅助 helper `_raise_perm_error` + 新 `_AuthFailingRuntime` class(继承 `_FakeRuntime`,重载 `run_request` 直接 raise `ProviderAuthError`)。Case A 还断言 stderr 中 `flush_evidence failed for` 行后没有 `File "` 帧,验证 redaction 路径走 `safe_exc` 而非 stack 打印。

## 验证证据

```bash
$ pytest -q tests/test_validation_runner.py -k "finally_writer_failure"
3 passed, 18 deselected in 0.03s

$ pytest -q                # 全套
311 passed in 46.37s       # baseline 308 + 3 新

$ grep -c "flush_evidence failed for" runner.py            # = 1
$ grep -c "write_evolution_snapshot failed for" runner.py  # = 1
$ grep -c "safe_exc(cleanup_exc)" runner.py                # = 2 (两处 except 各一)
$ grep -c "traceback.print_exc" runner.py                  # = 3 (与 plan 08-09 后一致,WR-02 不引入新 print_exc)
```

## Deviations from Plan

无。Plan TDD 规范 RED→GREEN 一次过,grep 不变量全中,本 plan 不触发任何 deviation rule。

唯一一处微调:plan action 描述里我曾在新增 comment 中写了 `traceback.print_exc` 字面串(描述"严禁用 traceback.print_exc"),导致 grep `traceback.print_exc` 计数从 3 升到 4;立即改写为 "full-stack printer" 描述以维持 plan 验证项要求的 grep 计数 = 3。这是 plan-内 grep 不变量的字面级落实,不是行为偏离。

## Threat Surface 自检

| Threat ID | 落实 |
|-----------|------|
| T-08-10-01 (Information Disclosure: cleanup_exc 含 secret) | `safe_exc` 走 `_secrets.py` 的 sk-/Bearer/Authorization regex redaction;无 `traceback.print_exc` 引入 |
| T-08-10-02 (Repudiation: cleanup 失败 swallow 后无 audit) | print 含 `request_id` + redacted exc class+message,可后续 root-cause |

## Self-Check: PASSED

- runner.py:662-704 finally 形态如设计 — `[ ✓ ]` 验证通过 `Read` 工具
- tests/test_validation_runner.py:+105 行(3 个新 case)— `[ ✓ ]` `pytest -k finally_writer_failure` 三个 case 全绿
- 全套 311 测试通过(baseline 308 + 3 新)— `[ ✓ ]`
- grep 不变量全中 — `[ ✓ ]`
