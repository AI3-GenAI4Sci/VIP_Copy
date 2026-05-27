---
phase: 08-evolution-wiring-and-runner-debt
plan: G1
subsystem: workflow + validation
tags: [skill-loader, dag-runner, distill, F-08-B, gap-closure]
requires:
  - F-08-B finding (workspace/.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-B-copy-quality-rootcause.md)
provides:
  - seers_harness.workflow.skill_loader (single SKILL.md prose primitive + node→skill binding extension)
  - 真实 SKILL.md prose 进入 dag_runner._run_node 的 system message
  - _distill_after_stage1 走同一 primitive,不再独立 read_text
affects:
  - seers_harness/workflow/dag_runner.py(line 84 字面 "SKILL_BODY" 删除)
  - seers_harness/validation/runner.py(_distill_after_stage1 line 491-493 read_text 删除)
  - tests/test_08_06_token_cost_observed.py(_register_test_skill 补 load_skill_prose stub)
tech-stack:
  added: [threading.Lock (cache 写入串行化)]
  patterns: [module-level cache + 多 root 搜索 + 显式 FileNotFoundError + 静态 registry dict]
key-files:
  created:
    - seers_harness/workflow/skill_loader.py
    - tests/test_skill_loader.py
    - tests/test_dag_runner_skill_dispatch.py
  modified:
    - seers_harness/workflow/dag_runner.py
    - seers_harness/validation/runner.py
    - tests/test_08_06_token_cost_observed.py
decisions:
  - "D2 落地:`load_skill_prose` 是 SKILL.md prose 唯一入口;`NODE_SKILL_BINDING` + `resolve_skill_for_node` 是 primitive 之上的 registry 扩展面,不是第二个 loader"
  - "primitive 在 miss 时 raise FileNotFoundError(消息含 skill_name + 搜索过的根),不回退占位符 —— 防 F-08-B 那种 silent 10-byte fallback"
  - "module-level dict cache + threading.Lock 保护写入:Stage 3 c=20 并发读写不会重复读盘,锁只覆盖 dict insert,不覆盖磁盘读"
  - "搜索顺序 `current/` 优先于 `evolution/`:production 三节点先命中 `current/<skill>/SKILL.md`,distill 节点命中 `evolution/distill-skill-deltas/SKILL.md`"
metrics:
  duration: 24min
  completed: 2026-05-27T18:22:00Z
  tests_added: 13
  tests_total: 334
  baseline_tests: 321
---

# Phase 08 Plan G1: SKILL loader 统一化 + F-08-B 根因修复 Summary

## 一句话

新增 `skill_loader.load_skill_prose` —— harness 中唯一一处读取 SKILL.md prose 的入口,带 module-level cache 与显式 `FileNotFoundError`;`dag_runner.py:84` 的 `"SKILL_BODY"` 字面常量 与 `runner.py:_distill_after_stage1` 的独立 `read_text` 都被收编到这个 primitive。

## 背景:F-08-B 根因链

2026-05-27 真实 DeepSeek batch (`tests/smoke/.runs/20260527T123110Z/`) 发现 3 个 production node 的 `messages.jsonl[0].content` 全部是 10 字节字符串 `"SKILL_BODY"` —— SKILL.md prose 从未到达 LLM,所有"7 axes / 反模式 / anchor diversity"教学失效。LLM 在没有 SKILL 引导时,按训练分布生成"4 字情绪+商品名"广告模板,F-08-B finding 已确认该 bug 是 4 层根因里最深一条(F-08-B → F-08-C → F-08-A → F-08-D 因果链)。

ground zero:`seers_harness/workflow/dag_runner.py:84` 写死 `skill_bundle="SKILL_BODY"`;同时 `runner.py:491-493` 自己 `read_text` distill SKILL,形成两个独立 loader,违反"单一 primitive"约束(用户决定 D2)。

## 实施

### Task G1-T1:`load_skill_prose` primitive + `NODE_SKILL_BINDING` 扩展层

新建 `seers_harness/workflow/skill_loader.py`,暴露:

- `_SKILL_ROOTS: tuple[Path, ...]` —— `(workflow-skills/current, workflow-skills/evolution)`,按顺序搜索;
- `_PROSE_CACHE: dict[str, str]` + `_CACHE_LOCK: threading.Lock` —— 模块级缓存,锁覆盖 dict insert;
- `load_skill_prose(skill_name) -> str` —— cache hit 直接返回;否则按 `_SKILL_ROOTS` 顺序拼路径,第一处 `exists()` 即 `read_text(encoding="utf-8")` 写 cache 并返回;全部 miss 则 raise `FileNotFoundError`,消息含 `skill_name` + 搜过的根目录,**绝不**返回占位符字符串;
- `NODE_SKILL_BINDING: dict[str, str]` —— 静态绑定 4 个 node id 到 4 个 skill 名(production 三节点 + distill);
- `resolve_skill_for_node(node_id) -> str` —— 查 BINDING,miss raise `KeyError` 并带可用 node 列表;
- `_clear_cache_for_tests()` —— 测试专用 hook,生产代码不调。

模块 docstring 写明:未来若要"按 scenario flag 切换 skill 变体",做法是把 `NODE_SKILL_BINDING` dict 升级为 `SkillBindingRegistry` 类,**禁止**回到 dag_runner 内联 dict 的反模式。

新建 `tests/test_skill_loader.py` —— 8 个 test:

1. `test_load_skill_prose_returns_full_skill_md_for_current_skill` —— 字节数 > 1500 且 byte-for-byte 等于直接读盘的文本(`discover-personalization-factors` 是 5499 bytes)
2. `test_load_skill_prose_finds_skill_in_evolution_root` —— `distill-skill-deltas` 在 evolution 子目录命中,验证多 root 搜索
3. `test_load_skill_prose_raises_filenotfound_for_unknown_skill` —— miss 时 raise `FileNotFoundError`,消息含 skill_name + `workflow-skills` 子串
4. `test_load_skill_prose_caches_after_first_read` —— monkeypatch `Path.read_text` 计数,101 次调用只触发 1 次磁盘读
5. `test_resolve_skill_for_node_canonical_bindings` —— 4 个 node id 各自命中预期 skill 名;`set(NODE_SKILL_BINDING.keys())` 严格等于预期 4 元素集合
6. `test_resolve_skill_for_node_unknown_raises_keyerror` —— unknown node raise `KeyError` 且消息含 node_id
7. `test_skill_loader_source_does_not_contain_forbidden_literal` —— `inspect.getsource(skill_loader_mod)` 不含 `"SKILL_BODY"` 字面 token(用 `"SKILL" + "_BODY"` 构造,避免源码本身被这条断言"自查"困死)
8. `test_clear_cache_for_tests_resets_cache` —— hook 真实清空 dict,`importlib.reload` smoke

### Task G1-T2:dag_runner + _distill_after_stage1 切换到 primitive

1. `seers_harness/workflow/dag_runner.py`:
   - 顶部 import 加 `from seers_harness.workflow.skill_loader import load_skill_prose`
   - 第 84 行 `skill_bundle="SKILL_BODY"` → `skill_bundle=load_skill_prose(node.skill_name)`(`NodeSpec.skill_name` 已是逻辑名,直接用,因为 NodeSpec 已经显式携带 skill_name;BINDING 走 `resolve_skill_for_node` 是给 distill 这种无 NodeSpec 的 caller 用)
   - 其余 `_run_node` / `NodeSpec` / `run_skill_via_tools` 接口未动

2. `seers_harness/validation/runner.py:_distill_after_stage1`(line 491-493):
   - 删 `skill_bundle = (LIVE_SKILL_ROOT / "evolution/distill-skill-deltas/SKILL.md").read_text(encoding="utf-8")`
   - 改为 `skill_bundle = load_skill_prose("distill-skill-deltas")`(import 在函数内 lazy 进口,避免模块顶部循环依赖风险)
   - `LIVE_SKILL_ROOT` 常量保留 —— `_patch_from_portfolio_row` 还在用它做 live skill SHA-integrity 校验(line 538),那是文件操作不是 prose 读取,不删

3. `tests/test_dag_runner_skill_dispatch.py` 新建 5 个 test:
   - `test_dag_runner_injects_real_skill_prose_not_placeholder` —— F-08-B 直接回归保护:断言 system message != "SKILL_BODY" 且 byte-for-byte 等于 `load_skill_prose(...)` 输出
   - `test_dag_runner_dispatches_each_node_its_own_skill_prose` —— 每个 node 收到自己的 SKILL prose,无 cross-skill 泄漏
   - `test_distill_after_stage1_uses_skill_loader_primitive` —— grep `inspect.getsource(runner_mod)` 断言:有 `from seers_harness.workflow.skill_loader import` + 有 `load_skill_prose` 字符串 + 没有 `"evolution/distill-skill-deltas/SKILL.md"` 这条旧路径字符串
   - `test_dag_runner_source_does_not_contain_forbidden_literal` —— `inspect.getsource(dag_runner_mod)` 不含 `"SKILL_BODY"` 且必须含 `load_skill_prose`
   - `test_dag_runner_system_message_length_meets_real_llm_evidence_floor` —— system message 字节数 > 1500(real-LLM batch acceptance floor)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `test_08_06_token_cost_observed.py` 在 dag_runner 新行为下需补 load_skill_prose stub**

- **Found during:** Task G1-T2(运行 full pytest 时暴露 2 个 pre-existing test 红)
- **Issue:** `test_workflow_runtime_trace_carries_tool_loop_usage` 和 `test_trial_outcome_token_cost_from_runtime_trace_usage` 用合成 `skill_name="test"` 配 monkeypatch TOOLS_SPEC / TOOL_HANDLERS,但 dag_runner 现在改成调 `load_skill_prose("test")` —— 没有对应 SKILL.md 文件就 raise `FileNotFoundError`,被外层 `except Exception` 当 retryable 路径吞掉。这是 G1 直接引入的 blocker(scope 内,不是 deferred)。
- **Fix:** 扩展 `_register_test_skill` helper,加一行 `monkeypatch.setattr(dag_runner, "load_skill_prose", lambda skill_name: "STUB_SKILL_PROSE_FOR_TESTS")`。token-cost 测试关心的是 `tool_loop_summary` event 里的 usage,跟 SKILL 内容无关,任何非空 stub 都可。
- **Files modified:** `tests/test_08_06_token_cost_observed.py`(`_register_test_skill` 函数)
- **Commit:** 同 G1 atomic commit

### 其他偏差

- 计划 must_haves 列了 `tool_loop.py` 可能要改,但 T2 read_first 与实现后确认 `run_skill_via_tools` 签名不需要动 —— `skill_bundle: str` 参数已经接受任何字符串(F-08-B bug 是 caller 传错值,不是 callee 不接受 prose)。git diff 已确认 tool_loop.py 未改,符合 plan acceptance criterion `git diff --stat 不包含 tool_loop.py`。
- `tests/test_skill_loader.py` 实际写了 8 个 test(plan 列 6 个),多出的 2 个是 `test_clear_cache_for_tests_resets_cache`(测 hook 自身)+ 一个由 behavior 6 拆分的源码扫描。`tests/test_dag_runner_skill_dispatch.py` 写了 5 个 test 严格对齐 plan behavior 1..5。

### 未触及(out-of-scope)

- `workflow-skills/current/*/SKILL.md` 三个文件 pre-existing dirty(`.continue-here.md` 已警示),G1 完全不动 —— 这些 dirty 是 G2/G3 阶段的 SKILL prose rewrite 工作。
- `.planning/` 内任何 STATE.md / ROADMAP.md 改动,按 orchestrator 约定不动。

## 验证证据

| Gate | 命令 | 结果 |
|------|------|------|
| pytest 全套 | `pytest -q` | 334 passed in 46.44s(321 baseline + 13 new,0 regression) |
| SKILL_BODY 字面 | `grep -rn '"SKILL_BODY"' seers_harness/` | 0 hits |
| 独立 SKILL read_text | `grep -rn 'read_text.*SKILL\.md\|read_text.*evolution/distill' seers_harness/ --include='*.py' \| grep -v skill_loader.py` | 0 hits |
| primitive 实际下发 prose | `python -c "from seers_harness.workflow.skill_loader import load_skill_prose; print(len(load_skill_prose('discover-personalization-factors')))"` | 5452 bytes(不是 10) |
| binding 正确 | `python -c "from seers_harness.workflow.skill_loader import resolve_skill_for_node; print(resolve_skill_for_node('factor_discovery'))"` | `discover-personalization-factors` |
| dag_runner 用 primitive | `grep -c load_skill_prose seers_harness/workflow/dag_runner.py` | 2(import + call) |
| runner 用 primitive | `grep -c load_skill_prose seers_harness/validation/runner.py` | 2(import + call) |

## 风险与遗留

### 已闭环

- F-08-B 表层(SKILL prose 不下发)的代码路径修复 —— 验证依赖 real-LLM Stage 3 batch(G5 范畴),fake-provider 单测已经把"system message 字节数 ≥ SKILL.md 字节数 - 50"钉死作为回归 canary。
- Single primitive D2 落地 —— grep 通过,future caller(G2/G3/G4)只能走 `load_skill_prose`。

### 留给后续 plan

- G2(context disclosure):copy_payload_for / rubric_payload_for 信息密度修复 —— G1 把 SKILL prose 下发了,LLM 才有"读 user_state"的契机;G2 决定能读到多少 user_state 字段。
- G3(distill 改造):dual-track success/failure pattern mining + target_skill 三处契约 —— 现在 distill 拿到的是真实 SKILL prose,生成的 delta 才有信号。
- G4(替换 deterministic loop):G1 不动 _run_one_request 的 trial 调度。
- G5(真实 DeepSeek Stage 3 batch):G1+G2+G3+G4 全部落地后,跑一次 Stage 3 (n=20, c=20) 一次性验证 `messages.jsonl[0].content` 字节数 > 100 (planner truth 5)。

### 已知 Stubs

无。本 plan 没有占位实现,所有改动均是真实代码路径。

### Threat Flags

无新增 trust boundary 表面。`load_skill_prose` 读取的是项目根 `workflow-skills/` 目录(开发者写,不接受 user input 作为 path),threat surface 与之前 inline `read_text` 一致。

## Self-Check: PASSED

- `seers_harness/workflow/skill_loader.py` —— FOUND
- `tests/test_skill_loader.py` —— FOUND
- `tests/test_dag_runner_skill_dispatch.py` —— FOUND
- `seers_harness/workflow/dag_runner.py` 修改 —— `git diff --stat` 1 file changed
- `seers_harness/validation/runner.py` 修改 —— `git diff --stat` 1 file changed
- `tests/test_08_06_token_cost_observed.py` 修改 —— `git diff --stat` 1 file changed(Rule 3 fix)
- pytest 334 passed —— PASS
- SKILL_BODY = 0 hits —— PASS
- read_text gate = 0 hits(outside skill_loader.py)—— PASS

## TDD Gate Compliance

本 plan 按 plan-level TDD 流程执行,两个 task 都先写测试(RED)再写实现(GREEN):

- T1 RED:写 `tests/test_skill_loader.py` 8 个 test,运行得到 `ModuleNotFoundError: No module named 'seers_harness.workflow.skill_loader'`(RED 通过)
- T1 GREEN:写 `seers_harness/workflow/skill_loader.py`,运行得到 8 passed(GREEN 通过)
- T2 RED:写 `tests/test_dag_runner_skill_dispatch.py` 5 个 test,运行得到 5 failed(`system message length (10 bytes) below the 1500-byte SKILL.md prose floor`,RED 通过)
- T2 GREEN:改 `dag_runner.py:84` + `runner.py:491-493` + 修 1 个 blocker test,运行得到 13 new + 321 baseline = 334 passed(GREEN 通过)

由于本 plan 采用 atomic single commit(plan 元数据 + plan 主文档允许),RED 与 GREEN 不分开提交;实际开发顺序日志 RED→GREEN 在本 SUMMARY "实施" 段已逐步骤记录。
