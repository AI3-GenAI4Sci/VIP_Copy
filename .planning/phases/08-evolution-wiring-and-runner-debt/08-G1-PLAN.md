---
phase: 08-evolution-wiring-and-runner-debt
plan: G1
type: execute
wave: 1
gap_closure: true
depends_on: []
files_modified:
  - seers_harness/workflow/skill_loader.py
  - seers_harness/workflow/dag_runner.py
  - seers_harness/validation/runner.py
  - seers_harness/agentic/tool_loop.py
  - tests/test_skill_loader.py
  - tests/test_dag_runner_skill_dispatch.py
autonomous: true
requirements: []
must_haves:
  goal: "建立单一 harness primitive `load_skill_prose(skill_name)` —— 唯一一处读取 SKILL.md prose;'fixed node → fixed skill' 是 primitive 之上的 registry/hook 扩展。修复 F-08-B ground zero(`dag_runner.py:84` 字面 `\"SKILL_BODY\"`),并把 `_distill_after_stage1` 的独立 read_text 收编。Real-LLM evidence target:Stage 3 batch 中三个 production node + distill node 的 `messages.jsonl[0].content` 长度 > 100 bytes。"
  truths:
    - "(F-08-B)harness 中存在且仅存在一个读取 `<root>/<skill_name>/SKILL.md` prose 的入口 `load_skill_prose(skill_name) -> str`,源码 grep `read_text` over SKILL.md 在生产路径只命中 primitive 一处"
    - "(F-08-B)`dag_runner._run_node` 通过 NODE_SKILL_BINDING(扩展注册表)+ load_skill_prose 注入 system message,字面 `\"SKILL_BODY\"` 不再出现在 source"
    - "(F-08-B)`_distill_after_stage1` 调用同一 primitive,evolution skill 通过同一注册表绑定 distill node;`runner.py:491-493` 的独立 read_text 删除"
    - "(F-08-B)primitive 实现 module-level cache(读一次,后续命中 dict)+ explicit FileNotFoundError when skill missing,运行时不返回 fallback 占位符"
    - "(F-08-B)fake-provider 单测断言:三个 production node 收到的 system message 长度 ≥ SKILL.md 字节数 - 50(允许 prose stripping noise),不再是 10 字节字面常量"
  artifacts:
    - path: seers_harness/workflow/skill_loader.py
      provides: "load_skill_prose primitive + NODE_SKILL_BINDING registry + (optional) SkillBindingRegistry 扩展类"
      exports: ["load_skill_prose", "NODE_SKILL_BINDING", "resolve_skill_for_node"]
      contains: "def load_skill_prose"
    - path: seers_harness/workflow/dag_runner.py
      provides: "_run_node 调 resolve_skill_for_node + load_skill_prose 替换字面 SKILL_BODY"
      contains: "load_skill_prose"
    - path: seers_harness/validation/runner.py
      provides: "_distill_after_stage1 调 load_skill_prose 而非独立 read_text"
      contains: "load_skill_prose(\"distill-skill-deltas\")"
    - path: tests/test_skill_loader.py
      provides: "primitive 行为单测(cache、错误路径、binding lookup)"
  key_links:
    - from: seers_harness/workflow/dag_runner.py
      to: seers_harness/workflow/skill_loader.py
      via: "import + call resolve_skill_for_node + load_skill_prose"
      pattern: "from seers_harness.workflow.skill_loader import"
    - from: seers_harness/validation/runner.py:_distill_after_stage1
      to: seers_harness/workflow/skill_loader.py
      via: "import + call load_skill_prose"
      pattern: "load_skill_prose"
  forbid_list:
    - "禁止 在 dag_runner / runner / tool_loop 之外保留任何对 SKILL.md 的 read_text/Path.read_text 调用 —— 必须全部走 primitive"
    - "禁止 让 load_skill_prose 在文件不存在时返回空串或占位符 —— 必须 raise FileNotFoundError(避免 F-08-B 那种 silent 10-byte fallback 复现)"
    - "禁止 把 'SKILL_BODY' 字面字符串保留在生产路径(skill_loader.py 的字符串常量也禁止)—— 单测 grep 0 hits"
    - "禁止 在 primitive 之外建立第二个 binding(e.g. dag_runner 内联 dict 映射)—— binding 必须在 skill_loader.py 暴露"
---

<objective>
落地 F-08-B 的 root-cause 修复:把 SKILL.md prose 真实下发给 LLM。建立单一 harness primitive `load_skill_prose(skill_name) -> str`,在 module-level 缓存读取结果;把 "节点 → skill 名" 的绑定作为扩展层(`NODE_SKILL_BINDING` 字典 + `resolve_skill_for_node` 查找函数)叠在 primitive 之上;`dag_runner._run_node` 与 `_distill_after_stage1` 都通过这同一 primitive 拿 prose,字面 `"SKILL_BODY"` 与独立 `read_text` 全部消除。

Purpose: F-08-B(2026-05-28 confirmed)是 4 层根因里最深一条 —— `dag_runner.py:84` 写死 10 字节字符串 `"SKILL_BODY"` 作为 skill_bundle,3 个 production node 的 system message 全是这 10 字节,SKILL.md 6 个反模式 / 7 axes / "anchor diversity" prose 从未到达 LLM。同时 `runner.py:491-493` 自己 `read_text` distill SKILL —— 形成两个独立 loader,违反"单一 primitive"约束(用户决定 D2)。修了这条,F-08-C 信息密度修复才有落点(LLM 至少能读到 SKILL prose 才会读 user_state),F-08-D 机制修复才有真信号(distill 拿到的 trajectory 里 production agent 不再裸奔)。
Output: 单一 atomic commit;新文件 `skill_loader.py` + 改 `dag_runner.py` + `runner.py` + (若需)`tool_loop.py` + 2 个新测试文件。所有改动通过 `pytest -q` 全绿。
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/phases/08-evolution-wiring-and-runner-debt/08-CHARTER.md
@.planning/phases/08-evolution-wiring-and-runner-debt/08-CONTEXT.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-B-copy-quality-rootcause.md
@.planning/phases/08-evolution-wiring-and-runner-debt/.continue-here.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task G1-T1: 建立 load_skill_prose primitive + NODE_SKILL_BINDING 扩展层</name>
  <files>
    seers_harness/workflow/skill_loader.py (new)
    tests/test_skill_loader.py (new)
  </files>
  <read_first>
    - seers_harness/workflow/dag_runner.py 第 60-100 行(看 `_run_node` 当前如何调 `run_skill_via_tools`,字面 `"SKILL_BODY"` 在 line 84)
    - seers_harness/agentic/tool_loop.py(找 `run_skill_via_tools` 的签名,确认 `skill_bundle` 参数如何被注入到 messages[0].content;参考 F-08-B 文档说 line 51 拼 system message)
    - seers_harness/validation/runner.py 第 482-522 行(`_distill_after_stage1`,line 491-493 是另一处 read_text;同时确认 `LIVE_SKILL_ROOT` 常量来源)
    - seers_harness/evolution/__init__.py(看 evolution 包暴露口,确认 distill skill 路径是否走 evolution 子目录)
    - workflow-skills/current/discover-personalization-factors/SKILL.md(确认现存 skill 路径布局,71 行)
    - workflow-skills/evolution/distill-skill-deltas/SKILL.md(distill skill 在 `evolution/` 子目录,不在 `current/`)
  </read_first>
  <behavior>
    - Test 1: `load_skill_prose("discover-personalization-factors")` 返回 SKILL.md 全文(字节数 == 文件实际字节数,Chinese ensure_ascii=False 不参与 byte 计数)
    - Test 2: `load_skill_prose("distill-skill-deltas")` 在 evolution 子目录命中(说明 primitive 接受多 root 或有 fallback search 顺序)
    - Test 3: `load_skill_prose("nonexistent-skill")` raise `FileNotFoundError`,错误信息含 skill_name + 搜过的根目录,**不**返回空串/占位符
    - Test 4: 同一 skill 调 100 次,只触发一次磁盘读(用 `unittest.mock.patch.object(Path, "read_text")` 计 call_count == 1)
    - Test 5: `resolve_skill_for_node("factor_discovery")` -> "discover-personalization-factors";`copy_generation` -> "generate-copy-candidates";`personalized_copy_rubric` -> "personalized-copy-rubric-judge";`distill_after_stage1` -> "distill-skill-deltas";unknown node -> raise `KeyError`
    - Test 6: NODE_SKILL_BINDING 是显式 dict,**不**包含 "SKILL_BODY" 这个字符串常量(grep assertion in test)
  </behavior>
  <action>
    新建 `seers_harness/workflow/skill_loader.py`,暴露:

    1) 模块级常量 `_SKILL_ROOTS: tuple[Path, ...]` —— 按搜索顺序列出 `workflow-skills/current/` 与 `workflow-skills/evolution/`(确切相对项目根的路径,从 `LIVE_SKILL_ROOT` 推);

    2) 模块级 `_PROSE_CACHE: dict[str, str]` —— LRU/普通 dict 都可,thread-safe(`threading.Lock` 保护写),key 为 skill_name;

    3) `def load_skill_prose(skill_name: str) -> str` —— 在 cache 命中则直接返回;否则按 `_SKILL_ROOTS` 顺序拼 `<root>/<skill_name>/SKILL.md`,第一处 `exists()` 即 `read_text(encoding="utf-8")` 写 cache 并返回;走完所有 root 仍未命中,raise `FileNotFoundError(f"SKILL.md not found for skill_name={skill_name!r}, searched: {_SKILL_ROOTS}")`;**绝不**返回占位字符串(F-08-B 反模式);

    4) 模块级常量 `NODE_SKILL_BINDING: dict[str, str]` —— 静态映射 4 个 node id 到 4 个 skill 名(production 三节点 + distill);

    5) `def resolve_skill_for_node(node_id: str) -> str` —— 查 BINDING,miss 则 raise `KeyError`(让 caller 知道是 binding 未注册,不是 SKILL 文件缺失);

    6) (扩展位)预留一个 module-level docstring 段落说明:如果未来要支持"按 scenario flag 切换 skill 变体",做法是在 binding 层加一个 `SkillBindingRegistry` 类替换 dict,**不要**回到 dag_runner 内联 dict 的反模式。

    新建 `tests/test_skill_loader.py` —— 6 个 test 对应 behavior 1..6;test 4 用 `monkeypatch` 在 `Path.read_text` 上做 wrapper 计调用次数;test 6 用 `inspect.getsource(skill_loader)` + `assert "SKILL_BODY" not in source`。

    **D2 honored**:`load_skill_prose` 是唯一文件读取入口;binding 在同一模块作为可替换的扩展面。**禁止**把 binding inline 进 dag_runner 或 runner.py。
  </action>
  <acceptance_criteria>
    - `pytest -q tests/test_skill_loader.py` 6/6 绿
    - `grep -nE 'read_text\\(.*SKILL\\.md|read_text\\(\\)|Path.*SKILL\\.md' seers_harness/ --include='*.py' -r | grep -v 'skill_loader.py'` 命中数 == 0(只 primitive 自己读)
    - `grep -n '"SKILL_BODY"' seers_harness/ -r` 命中数 == 0
    - `python -c "from seers_harness.workflow.skill_loader import load_skill_prose; print(len(load_skill_prose('discover-personalization-factors')))"` 输出 > 1500(SKILL.md 实际 prose 字节数,不是 10)
    - `python -c "from seers_harness.workflow.skill_loader import resolve_skill_for_node; print(resolve_skill_for_node('factor_discovery'))"` 输出 `discover-personalization-factors`
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task G1-T2: dag_runner + _distill_after_stage1 切换到 primitive,删除独立 read_text</name>
  <files>
    seers_harness/workflow/dag_runner.py (modify line 84 + import block)
    seers_harness/validation/runner.py (modify _distill_after_stage1 lines 482-522)
    tests/test_dag_runner_skill_dispatch.py (new)
  </files>
  <read_first>
    - seers_harness/workflow/skill_loader.py(刚在 T1 建好,确认导出)
    - seers_harness/workflow/dag_runner.py 第 1-50 行(import block 与 NodeSpec.skill_name 字段关系)
    - seers_harness/workflow/dag_runner.py 第 60-100 行(_run_node 主循环)
    - seers_harness/validation/runner.py 第 482-522 行(distill_after_stage1 ground zero)
    - seers_harness/agentic/tool_loop.py 整文件(确认 run_skill_via_tools 把 skill_bundle 参数传哪 — F-08-B 提到 line 51 拼 system message[0].content;不要改 tool_loop 的接口)
    - tests/test_payloads_loop06_audit.py(参考 fake-provider 注入风格,以便新 dag_runner skill_dispatch test 能 reuse 同样的 fake)
    - tests/smoke/(看是否有现成 fake provider 可以 record system message 用于断言;若无,在新 test 内 inline 一个 minimal fake)
  </read_first>
  <behavior>
    - Test 1(dag_runner skill prose injected):用 fake provider 拦 `generate_with_tools` 调用,断言收到的 messages[0].role == "system" AND len(messages[0].content) > 100 (实际 SKILL prose 字节数,不是 10)
    - Test 2(dag_runner 多 node 分发正确):3 个 node id(factor_discovery / copy_generation / personalized_copy_rubric)分别命中各自的 SKILL prose(content 内含各自 SKILL.md 第一段 verbatim 子串如 `"For one request and one list group"` for copy_generation)
    - Test 3(distill_after_stage1 用 primitive):patch `seers_harness.validation.runner.load_skill_prose` 拦下调用,断言 distill 路径调它一次且参数 == "distill-skill-deltas",并断言 `runner.py` 内 grep `read_text.*evolution/distill` == 0
    - Test 4(grep gate):`grep -c '"SKILL_BODY"' seers_harness/workflow/dag_runner.py` 在 `grep -v '^#'` 过滤后 == 0
    - Test 5(F-08-B 回归):integration smoke 跑 fake provider 一个 3-node DAG,inspect 三个 messages.jsonl,每个 message[0].content 长度 ≥ 1500
  </behavior>
  <action>
    1) `dag_runner.py`:
       - import: `from seers_harness.workflow.skill_loader import load_skill_prose, resolve_skill_for_node`(放在文件顶部 import block);
       - 第 84 行 `skill_bundle="SKILL_BODY"` → 改为 `skill_bundle=load_skill_prose(node.skill_name)`(NodeSpec.skill_name 已是逻辑名,直接用,不再走 NODE_SKILL_BINDING —— 因为 NodeSpec 已携带显式 skill_name;BINDING 是给"node_id → skill_name"无 NodeSpec 时的 caller 用,如 distill);
       - **不要**改 `_run_node` 其它逻辑、不要改 `run_skill_via_tools` 接口、不要改 NodeSpec schema。
    2) `runner.py:_distill_after_stage1` 第 491-493:
       - 删 `skill_bundle = (LIVE_SKILL_ROOT / "evolution/distill-skill-deltas/SKILL.md").read_text(encoding="utf-8")`;
       - 顶部 import 加 `from seers_harness.workflow.skill_loader import load_skill_prose`;
       - 替换为 `skill_bundle = load_skill_prose("distill-skill-deltas")`;
       - 检查 LIVE_SKILL_ROOT 常量是否还有别处引用 SKILL.md prose 读取 —— 应只剩 trial_runner 的 `shutil.copytree` 用法(那是文件操作,不是 prose 读取),不删。
    3) `tests/test_dag_runner_skill_dispatch.py` 新建,5 个 test 对应 behavior;复用 `RecordingProvider`(`seers_harness.validation.recording_provider`)拦截 messages,断言 system message 字节数;test 4 用 `Path("seers_harness/workflow/dag_runner.py").read_text() | grep -v '^#' | grep -c '"SKILL_BODY"'` 等价的 Python 代码(strip 注释后 substring 检查 == 0)。
    4) **forbid_list 自查**:确认 dag_runner / runner / tool_loop **没有任何**新加的 inline `Path.read_text` over `SKILL.md`。
  </action>
  <acceptance_criteria>
    - `pytest -q` 全套 321+ tests pass + 5 new tests pass(总 326+ green)
    - `grep -rn '"SKILL_BODY"' seers_harness/` 命中数 == 0
    - `grep -rn 'read_text.*SKILL\\.md\\|read_text.*evolution/distill' seers_harness/ --include='*.py' | grep -v skill_loader.py` 命中数 == 0
    - 手动 sanity:`python -c "from seers_harness.workflow.dag_runner import WorkflowRuntime; import inspect; src = inspect.getsource(WorkflowRuntime._run_node); assert 'load_skill_prose' in src and '\"SKILL_BODY\"' not in src"` 不 raise
    - `git diff --stat` 显示 dag_runner.py / runner.py / skill_loader.py / 2 新 test 文件;**不**包含 tool_loop.py(接口未改)
  </acceptance_criteria>
</task>

</tasks>

<verification>
- pytest -q 全绿(预期 326+,新增 11 tests)
- grep gates(SKILL_BODY 与 read_text)0 hits
- runtime sanity:fake provider DAG 跑一次,断言三个 system message 长度均 > 1500 bytes
- F-08-B 修复证据:`tests/smoke/.runs/<G1-test-ts>/.../messages.jsonl` 第一行 content 长度 > 1500(单测 fixture 模拟 production batch 的 evidence shape)
</verification>

<success_criteria>
G1 ship 当且仅当:(a) primitive 是单一 prose 入口(grep 通过);(b) dag_runner 与 distill 都走 primitive(grep + 单测通过);(c) `pytest -q` 全绿;(d) primitive 错误路径明确(无 silent fallback)。这一个 plan 单独 ship 后,Stage 3 batch 的 SKILL prose 已会下发到 LLM —— 但 G2 + G3 + G4 必须叠加才能闭合 F-08-A/C/D 因果链。Real-LLM 验证延后到 G5。
</success_criteria>

<output>
Create `.planning/phases/08-evolution-wiring-and-runner-debt/08-G1-SUMMARY.md` when done.
</output>
