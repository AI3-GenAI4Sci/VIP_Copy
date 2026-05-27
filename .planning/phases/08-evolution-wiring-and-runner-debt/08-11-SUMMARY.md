---
phase: 08-evolution-wiring-and-runner-debt
plan: 11
subsystem: evolution-trial-runner
tags: [wr-05, except-narrow, provider-error, fail-fast, d-19]

# Dependency graph
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    plan: 08-05
    provides: F 接线后 trial_runner 才进入 runtime 真实路径,narrow 在此之后才有可观测后果
  - phase: 08-evolution-wiring-and-runner-debt
    plan: 08-06
    provides: token_cost_observed 在 try 成功路径赋值,WR-05 narrow 不改异常路径下的 token_cost 行为
provides:
  - run_request_trial 异常路径收窄到 (TrialFailure, AssertionError, SchemaError)
  - ProviderAuthError / ProviderRateLimitError / ProviderTransientError 在 trial 中 re-raise,走 D-19 provider_error fail-fast
  - 其他异常(KeyError、TypeError、IndexError 等)上浮,走 D-19 infra_error fail-fast
  - SchemaError = pydantic.ValidationError 的 module-local alias,charter 文本与 code 对齐
affects: [08-12, 08-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "异常路径 narrow 用 (类元组, ...) 形式分两段:一段 re-raise(provider 三类),一段 catch(trial 三类)"
    - "SchemaError 用 module-local alias 而非直接引用 pydantic.ValidationError,保留 charter 词汇"
    - "trial_failed event shape 保持不变(WR-06 redaction 路径仍生效)"

key-files:
  created:
    - tests/test_08_11_trial_runner_narrow.py
  modified:
    - seers_harness/evolution/trial_runner.py

key-decisions:
  - "测试文件采用 tests/test_08_NN_*.py 命名(沿 08-06 / 08-07 先例),因 PLAN 指向的 tests/test_trial_runner_smoke.py 在仓库中并不存在;tests/ 被 .gitignore 兜底,只有 test_08_NN_*.py 等显式入仓的文件可保留为 phase 证据。"
  - "保留既有 trial_failed event shape(trial_id / delta_id / exception_class / exception_message)— WR-05 只动 except 子句的类元组,事件载荷 verbatim 不动,避免连锁回归。"
  - "token_cost_observed 异常路径仍走 dataclass default 0(plan 08-06 IN-01 只在 try 块成功路径赋值)— WR-05 不动这条路径,防止 IN-01 行为漂移。"

patterns-established:
  - "trial 异常路径分流模板:provider 错误 re-raise → D-19 provider_error;领域三类(TrialFailure/AssertionError/SchemaError)catch → trial_failed;runner bug 上浮 → infra_error。三标签与 exception_classifier.classify() 同形。"

requirements-completed: []

# Metrics
duration: 18min
completed: 2026-05-27
---

# Phase 08 Plan 08-11:trial_runner 异常路径 narrow 总结

**`run_request_trial` 不再 swallow 任意 `Exception`:provider 三类错误 re-raise 让 runner 走 D-19 `provider_error` fail-fast,trial 三类(TrialFailure / AssertionError / SchemaError)仍 catch 写 `trial_failed`,其他 runner bug 上浮走 `infra_error`。**

## 性能

- **耗时:** ~18 分钟
- **完成时间:** 2026-05-27
- **任务:** 1 / 1
- **修改文件:** 2

## 完成项

- 在 `seers_harness/evolution/trial_runner.py` 顶部追加 import:
  - `ProviderAuthError` / `ProviderRateLimitError` / `ProviderTransientError`(来自 `core.errors`)
  - `TrialFailure`(来自 `validation.exception_classifier`)
  - `SchemaError`(`from pydantic import ValidationError as SchemaError`)
- 将 `except Exception as exc:` 拆为两段:
  1. `except (ProviderAuthError, ProviderRateLimitError, ProviderTransientError): raise` — D-19 provider_error 路径,不 emit trial_failed
  2. `except (TrialFailure, AssertionError, SchemaError) as exc:` — D-19 trial_failure 路径,outcome.success=False + emit trial_failed(event shape 与 08-06 之前 verbatim 一致,WR-06 redaction 仍生效)
- 不再有 `except Exception` fallback —— 其他异常(KeyError / TypeError / IndexError / ...)上浮到 caller,让 D-19 落到 `infra_error` fail-fast。
- 新增 `tests/test_08_11_trial_runner_narrow.py`,3 个 parametrized 测试覆盖 9 个 case:
  - `test_trial_runner_reraises_provider_errors`(3 case:auth / rate_limit / transient):断言 raise 同一实例 + events 无 trial_failed
  - `test_trial_runner_catches_schema_violation`(3 case:TrialFailure / AssertionError / pydantic.ValidationError):断言 outcome.success=False、failure_category == type(exc).__name__、events 单一 trial_failed
  - `test_trial_runner_propagates_unknown_exception`(3 case:KeyError / TypeError / IndexError):断言 raise 同一实例 + events 无 trial_failed / trial_succeeded

## 任务提交

1. **Task 1:trial_runner narrow + 单测** —— (本 plan 单次 atomic commit)

## 创建/修改的文件

- `seers_harness/evolution/trial_runner.py` —— 顶部 3 个 import + except 子句拆分为 re-raise / catch 两段
- `tests/test_08_11_trial_runner_narrow.py` —— 3 个 parametrized 测试(9 个 case)

## 决策

- **测试文件命名 deviation:** PLAN 写的是 `tests/test_trial_runner_smoke.py`,但仓库无此文件(`.gitignore` 兜底,只有显式入仓的 `tests/test_08_NN_*.py` 等保留)。沿 08-06 / 08-07 先例,新增 `tests/test_08_11_trial_runner_narrow.py`,本 plan 证据可被审计层稳定 git ls-files。
- **event shape verbatim 不动:** 仅替换 `except` 子句的类元组,事件 dict 字段顺序与 08-06 之前完全一致(`type` / `trial_id` / `delta_id` / `exception_class` / `exception_message`),避免快照消费者(如 `evolution_snapshot.json` reducer)出现 schema drift。
- **`token_cost_observed` 异常路径行为不变:** 08-06 IN-01 只在 try 块尾部(成功路径)给 `token_cost_observed` 赋值。WR-05 不动这条路径,异常路径下 `TrialOutcome.token_cost_observed` 保留 dataclass default `0`,与 08-06 行为一致。

## 偏差(Plan 之外的工作)

- **测试文件名偏差(Rule 3 阻塞修复):** PLAN 指向的 `tests/test_trial_runner_smoke.py` 不存在;改写到 `tests/test_08_11_trial_runner_narrow.py`(理由见上)。
- **Test 3 强烈推荐而非可选:** PLAN 把 `test_trial_runner_propagates_unknown_exception` 标为"可选但推荐",本次直接落地,因为 T-08-11-02 威胁模型(future patch 把 `except Exception` 加回退化 phase-7 行为)就靠这条测试守门 —— 不落地则威胁模型项缺乏强制约束。

## 遇到的问题

无。新测一次通过 9 个 case,全量套件 `.venv/bin/python -m pytest -q` 320 passed(311 基线 + 9 new case,无回归)。

## 验证

执行的命令与结果:

```bash
.venv/bin/python -m pytest -q tests/test_08_11_trial_runner_narrow.py -x
# 9 passed in 0.08s

.venv/bin/python -m pytest -q
# 320 passed in 46.46s

grep -c "except (ProviderAuthError" seers_harness/evolution/trial_runner.py
# 1

grep -c "except (TrialFailure" seers_harness/evolution/trial_runner.py
# 1

grep -c "except Exception as exc" seers_harness/evolution/trial_runner.py
# 0

grep -c "SchemaError" seers_harness/evolution/trial_runner.py
# 2
```

所有 PLAN 的 verify 条件全部满足:
- 2+ 个新测全绿(实际 9 个 case)
- `except (ProviderAuthError` == 1
- `except (TrialFailure` == 1
- `except Exception as exc` == 0(narrow 完成)
- `SchemaError` ≥ 2(import alias + except 子句引用)
- phase-7 baseline 253 测试 + 08-06 / 08-07 / 08-08..10 累计 311 测试 → 320 全绿,无回归

## 威胁模型对账

- **T-08-11-01(Repudiation,401 被掩盖为 trial_failed)mitigated:** ProviderAuthError 现在 re-raise → runner D-19 标 `provider_error`,batch_summary 的 `by_failure_class.auth` 非零,operator 可直接定位 stale env。三个 parametrized provider-error case 强制这一行为。
- **T-08-11-02(Tampering,future patch 把 except 加回 Exception)mitigated:** `test_trial_runner_propagates_unknown_exception` 在 KeyError / TypeError / IndexError 上强制 raise 浮出,任何 patch 把 `except Exception` 加回都会让这 3 个 case 失败(provider error 不会 propagate)。

## 用户需准备

无。

## 下一阶段就绪度

08-12 / 08-13(若仍未执行)可以继续。WR-05 已在 F 接线之后落地(per 08-RESEARCH §7.3 测序复核),narrow 是 *增强* F 可观测性,不是新风险面:trial 中出现的 provider error 现在会 fail-fast,而非默默标 trial_failed。

## Self-Check: PASSED

- `seers_harness/evolution/trial_runner.py`(modified)— FOUND
- `tests/test_08_11_trial_runner_narrow.py`(created)— FOUND
- 9 个 new test case 全绿(`pytest tests/test_08_11_trial_runner_narrow.py`)
- 全量 320 passed(基线 311 + 9,无回归)
- grep 四项断言全部命中(1 / 1 / 0 / 2)

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-27*
