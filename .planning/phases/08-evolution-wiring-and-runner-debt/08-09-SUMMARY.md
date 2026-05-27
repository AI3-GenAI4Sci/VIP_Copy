---
phase: 08-evolution-wiring-and-runner-debt
plan: 09
subsystem: validation
tags: [runner, threadpool, fail-fast, drain, as_completed, failure_class]

# Dependency graph
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    provides: "plan 08-03 失败分类枚举(failure_class 7-enum 路由);plan 08-08 transient backoff 已落 tool_loop 层"
provides:
  - "Stage 3 fail-fast 路径 drain 在跑的 in-flight futures,disk artifacts 与 index.json 在 c=20 并发场景下数量一致"
  - "drain 出的失败 record 走 plan 08-03 的 failure_class 7-enum 路由"
  - "原始 fail-fast cause(failure_exc)在 drain 过程中被保留,不被 in-flight 次因覆盖"
affects: [phase 07 真 LLM 验收(D8-G-WR-01 / D8-ACC-1 / D8-ACC-4), 后续 Stage 3 cycle-time 评估]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "concurrent.futures fail-fast drain: cancel() not-started + as_completed() in-flight + per-future record collection"
    - "因果链保留约定: failure_exc 仅在第一次失败时赋值,drain 路径不覆盖"

key-files:
  created: []
  modified:
    - seers_harness/validation/runner.py
    - tests/test_validation_runner.py

key-decisions:
  - "drain 用 as_completed(remaining) 等待已开始的 future 完成,不引入 timeout(单请求 timeout=180s × c=20 上限可接受,T-08-09-01 risk accepted)"
  - "cancelled future 不产生 index 行(未启动 _run_one_request,无 disk artifact,符合 D-02 partial-on-disk 行对齐 disk 规则)"
  - "drain 出的次失败走 failure_class(drain_exc),不调 classify(),不进入 D-19 的 trial_failure 路径"
  - "测试压成 c=6/n=6 + c=3/n=3 双场景,避开 c=20 让 pytest 慢跑,bug 在 n>=2 即可重现"

patterns-established:
  - "Stage 3 ThreadPoolExecutor fail-fast drain: 任何 fail-fast 触发后,先 cancel() 未开始的 future,再 as_completed() 收集所有 in-flight future 的 record(成功/失败均收),break"
  - "drain branch 失败处理: try/except BaseException as drain_exc → records.append({..., failure_class(drain_exc)}),禁止 catch 后转 trial_failure"

requirements-completed: []

# Metrics
duration: 14min
completed: 2026-05-27
---

# Phase 08 Plan 09: Stage 3 fail-fast drain in-flight futures Summary

**ThreadPoolExecutor fail-fast 路径替换原 cancel+break 为 cancel-未开始 + as_completed-drain-在跑,确保 disk artifacts 与 index.json 在 Stage 3 c=20 场景下行数一致(D8-G-WR-01 落地)。**

## Performance

- **Duration:** 14 min
- **Started:** 2026-05-27T11:33:00Z
- **Completed:** 2026-05-27T11:47:09Z
- **Tasks:** 1(单 atomic commit,RED → GREEN 一气呵成)
- **Files modified:** 2

## Accomplishments

- `seers_harness/validation/runner.py:_run_stage` Stage 3 fail-fast 分支:`for other in future_to_rid: other.cancel(); break` 替换为 RESEARCH §4-WR-01 伪代码的 drain 模式:
  1. `remaining = [f for f in future_to_rid if not f.done()]`(只 drain 还没完成的)
  2. `for f in remaining: f.cancel()`(取消未开始的)
  3. `for f in as_completed(remaining):` 等已开始的跑完
  4. `f.cancelled() → continue`(未启动者无 record)
  5. `f.result() → records.append(record)`(已完成者按结果入队)
  6. 失败者走 `except BaseException as drain_exc → failure_class(drain_exc)`
- 新增 2 个单测覆盖 drain 路径:
  - `test_stage3_fail_fast_drains_inflight`:c=6/n=6,rid-04 raise ProviderAuthError 触发 fail-fast,5 个 in-flight 受 `threading.Event` 控顺序后正常完成 → records 长度 == 6,classes == ["auth", 5×"ok"]
  - `test_stage3_fail_fast_drains_inflight_failure_with_class`:c=3/n=3,fail-fast 是 auth,drain 出一个 transient 一个 success → records.classes == ["auth", "ok", "transient"],证明 drain 失败也走 failure_class 7-enum 而非 D-19 trial_failure
- 全套 pytest 308 passed(baseline 306 + 2 新测,无回归)

## Task Commits

1. **Task 1: Stage 3 fail-fast 路径 drain in-flight futures + 1 个单测** - `a99e65f` (feat,单 atomic;包含 RED → GREEN 一气呵成的 runner.py 替换 + 2 个单测)

## Files Created/Modified

- `seers_harness/validation/runner.py`(line 833-872 替换 fail-fast 退出块,from cancel+break 到 cancel-未开始+as_completed-drain;`as_completed` / `failure_class` import 在 plan 07-04 / 08-03 已落,无需新增)
- `tests/test_validation_runner.py`(新增 `import threading`;末尾新增两个测试函数)

## Verification

- `pytest -q tests/test_validation_runner.py -k "stage3_fail_fast_drains" -x` → 2 passed
- `pytest -q tests/test_validation_runner.py` → 18 passed(baseline 16 + 2 新测)
- `pytest -q` 全套 → 308 passed
- `grep -c "as_completed(remaining)" seers_harness/validation/runner.py` == 1 ✓
- `grep -c "failure_class(drain_exc)" seers_harness/validation/runner.py` == 1 ✓

## Decisions Made

1. **测试规模选 c=6 / c=3 而非 c=20。** Bug 在 n>=2 即可重现(只要存在"未完成的 in-flight"),用 c=20 不增加证据强度,反而拖慢 pytest 多线程场景的 fixture 释放。
2. **`cancelled() → continue` 而非补 None record。** 未启动的 future 没有跑过 `_run_one_request`,disk 上没有 `request_dir/`,不应在 index.json 里出现这一行(D-02 行对齐 disk 规则)。RESEARCH §4-WR-01 伪代码已锁定这一行为。
3. **不在 drain 中加 timeout。** 单请求 provider timeout=180s(D8-A);c=20 worst-case drain 上限 = 180s,可接受(T-08-09-01 risk accepted)。如果未来 drain 真挂,后续 phase 加 timeout drain。
4. **drain 出的 exception 必须走 `failure_class(drain_exc)` 而非 `classify(drain_exc)`。** drain 出的失败是次因,不进入 D-19 trial_failure / fail-fast 决策(主线已 fail-fast 了);只为 index.json 操作员视角填一个聚合标签。

## Deviations from Plan

None - plan executed exactly as written.

(Plan §action step 1 提示需要 `confirm as_completed import`、step 3 提示需要 `confirm failure_class import`;查 runner.py 顶部 line 125 / line 152 已 import 这两个符号,均无需新增。)

## Issues Encountered

- 第一次写完代码后 grep 发现 `as_completed(remaining)` 和 `failure_class(drain_exc)` 各有 2 次匹配 —— 因为我在 docstring 注释里也写了这两个 token 字面量。重写注释时把 token 字面量去掉(用"`as_completed`"裸名 + "drain 出的失败"自然语言),grep count 回到验收期望的 == 1。

## User Setup Required

None.

## Next Phase Readiness

- D8-G-WR-01 落地。phase 8 wave 6 还剩 plan 08-10(WR-02 finally best-effort 包装)、08-11(WR-05 trial_runner narrow except)、08-12 / 08-13 等未排期。
- phase 8 Group 3(G)的 disk-vs-index 合约现在在 unit-test 层有保护;真 LLM 层的实测证据(自然 fail-fast 触发时 `len(index.json["requests"]) == 20` AND disk `stage3/<rid>/` 目录数 == 20)等到下一次 batch 跑后补;若没自然 fail-fast,pytest 即唯一证据(plan §verification 已声明)。

## Self-Check: PASSED

- `seers_harness/validation/runner.py`: FOUND
- `tests/test_validation_runner.py`: FOUND
- `.planning/phases/08-evolution-wiring-and-runner-debt/08-09-SUMMARY.md`: FOUND
- commit `a99e65f`: FOUND in git log
- pytest 全套 308 passed
- grep counts both == 1

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-27*
