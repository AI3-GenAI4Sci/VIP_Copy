---
phase: 08-evolution-wiring-and-runner-debt
plan: G3
type: execute
wave: 3
gap_closure: true
depends_on:
  - 08-G1
  - 08-G2
files_modified:
  - workflow-skills/evolution/distill-skill-deltas/SKILL.md
  - seers_harness/tools/evolution_tools.py
  - seers_harness/validation/runner.py
  - tests/test_evolution_tools.py
  - tests/test_validation_runner.py
autonomous: true
requirements: []
must_haves:
  goal: "重写 distill-skill-deltas SKILL.md prose(统一术语 + success/failure dual-track 注意)、加锁 target_skill 三处契约(SKILL prose + tool spec + `_patch_from_portfolio_row` 运行时网关)、为 distill agent trace 接通持久化(F-08-D Gap 6)。修复 F-08-01 主因(target_skill 路径无契约)+ F-08-D Gap 2(distill 当前对成功/失败模式无差别,产出无判别力的 generic delta)+ F-08-D Gap 6(distill 零 on-disk 审计)。Real-LLM evidence target:Stage 3 batch 中 distill 产 delta 至少有 1 条 target_skill 字段在 `_patch_from_portfolio_row` 解析通过(非 silent skip);`distill_evidence/` 目录非空。"
  truths:
    - "(F-08-01)target_skill 三处契约一致字面 invariant:SKILL prose 段、tool spec(`{\"type\":\"string\",\"description\":\"...\",\"pattern\":\"^current/[a-z0-9-]+/SKILL\\\\.md$\"}`)、`_patch_from_portfolio_row` 接受/拒绝路径的逻辑;三方任一段被改不一致,grep gate 失败"
    - "(F-08-01)`_patch_from_portfolio_row` 拒绝路径时 emit `print(f\"[runner] trial_skipped delta_id={...} reason={...} target_skill={...}\", file=sys.stderr)`,不再 silent return None — 任何拒绝必须可观测"
    - "(F-08-D Gap 6)`_distill_after_stage1` 把 RecordingProvider 的 request_log flush 到 `{stage1_dir}/distill_evidence/{messages.jsonl,tool_calls.jsonl,artifact.json,usage.json}` — 与 production node evidence shape 平行"
    - "(F-08-D Gap 2)distill SKILL prose 显式 dual-track:success-path pattern attention 与 failure-path pattern attention 各一段。引导 LLM 区别看待 trajectory 的两类信号:产 high-quality copy 的成功路径 vs 触发 low-discrimination rubric / 卡死同模式失败的失败路径"
    - "(F-08-A locked, anti-injection)distill SKILL prose 必须用项目术语(disposition / hook / anchor / floor / trajectory / pattern),禁止把用户口头举例(\"低价大牌\"/\"周三早9点\"/\"代理父亲\"/\"信息饕餮\"/\"多娃妈妈\" 等)字面写进 prose 作为 anchor 模板;forbid_list grep gate 在 acceptance_criteria"
    - "(F-08-D Gap 6)distill_evidence 持久化 SHALL 与 production node evidence 用同一 `flush_evidence(request_log, evidence_dir)` 入口,不创建第二条 flush 路径"
  artifacts:
    - path: workflow-skills/evolution/distill-skill-deltas/SKILL.md
      provides: "重写后的 distill SKILL — 统一术语 + dual-track success/failure prose + target_skill 格式说明段"
      contains: "target_skill"
    - path: seers_harness/tools/evolution_tools.py
      provides: "RECORD_DELTA_CHANGE_SPEC.target_skill 字段加 description + JSON pattern"
      contains: "pattern"
    - path: seers_harness/validation/runner.py
      provides: "_patch_from_portfolio_row 加 explicit warn log + path normalization;_distill_after_stage1 调 flush_evidence 把 distill trace 落盘"
      contains: "trial_skipped"
  key_links:
    - from: distill-skill-deltas SKILL prose
      to: tool spec target_skill pattern
      via: "SKILL prose 给的 target_skill 格式范例必须满足 RECORD_DELTA_CHANGE_SPEC.target_skill.pattern"
      pattern: "current/[a-z0-9-]+/SKILL"
    - from: _patch_from_portfolio_row
      to: tool spec target_skill pattern
      via: "patch helper 接受逻辑必须严格匹配 tool spec pattern;否则 LLM 提交合法字段但 helper 拒绝"
      pattern: "trial_skipped"
    - from: _distill_after_stage1
      to: flush_evidence
      via: "distill RecordingProvider 的 request_log 走同一 flush_evidence 入口落盘"
      pattern: "flush_evidence.*request_log"
  forbid_list:
    - "禁止 SKILL prose 字面引用用户口头举例(grep 守门:`grep -nE '低价大牌|周三早.{0,2}9.{0,2}点|代理父亲|信息饕餮|多娃妈妈' workflow-skills/evolution/distill-skill-deltas/SKILL.md` 必须 0 hits)"
    - "禁止 `_patch_from_portfolio_row` silent return None — 拒绝必须 print 到 stderr 并标 reason"
    - "禁止单测用 mock distill 输出绕过真实 handler 链 — distill 测必须通过 `EVOLUTION_TOOL_HANDLERS` + 一个 fake provider 真跑一遍 record_delta_change → submit_delta_distillation_final"
    - "禁止 SKILL prose 引入新概念词 — dual-track success/failure 用既有术语 (trajectory / pattern / failure_type / observation) 描述,不创造新词如 \"成功侧\"/\"失败侧\""
    - "禁止 distill_evidence 写到 git-tracked 路径 — 必须落在 `tests/smoke/.runs/<batch-ts>/stage1/<rid>/distill_evidence/`(已 gitignored 的 .runs 树下)"
---

<objective>
落地 F-08-01 + F-08-D Gap 2 / Gap 6 三连修复:重写 distill-skill-deltas SKILL prose(统一 dual-track 注意)、把 target_skill 三处契约 grep-verifiable 锁定一致、把 distill agent 的 RecordingProvider trace 落盘。这是 G4 接线 bandit 之前的最后一道清地基:distill 产 delta 的语义必须有方向(分别看 success / failure),target_skill 必须能解析到真实 skill 文件,distill 的产出必须可审计。

Purpose: F-08-01 三因里 target_skill 路径不解析是 deterministic loop 时代的表层 bug,但 G4 wire 上 select_trial_delta 之后,LLM 提交不解析的 target_skill 仍会让 trial 永远不发生 — 这次必须三处对齐。F-08-D Gap 2 是更深的问题:当前 SKILL prose 把 trajectory 当一个 input 看,LLM 抽 delta 时无差别处理 — 这是为什么 0526 batch 的 4 个 delta(`d1_slogan_only_copy_format` 等)看起来像 generic guideline,缺乏对 high-quality / low-quality 案例的对比意识。F-08-D Gap 6 修 distill 零审计 — 后续 G4 / G5 调试时无法离线重放 distill。

Output: 两个 atomic commit:(1) SKILL prose 重写 + tool spec target_skill pattern + grep gate 单测;(2) `_patch_from_portfolio_row` warn log + `_distill_after_stage1` flush_evidence 接通 + 持久化单测。
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/08-evolution-wiring-and-runner-debt/08-CONTEXT.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-01-d8f-trial-unreachable.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-D-delta-mechanism-redesign.md
@workflow-skills/evolution/distill-skill-deltas/SKILL.md
@seers_harness/tools/evolution_tools.py
@seers_harness/validation/runner.py
@seers_harness/validation/recording_provider.py
@seers_harness/validation/evidence_writer.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: distill SKILL prose 重写 + target_skill 三处契约 + grep 单测</name>
  <files>workflow-skills/evolution/distill-skill-deltas/SKILL.md, seers_harness/tools/evolution_tools.py, tests/test_evolution_tools.py</files>
  <read_first>
    - workflow-skills/evolution/distill-skill-deltas/SKILL.md(现状全文 — 看哪些段需要重写,哪些段保留)
    - seers_harness/tools/evolution_tools.py(`RECORD_DELTA_CHANGE_SPEC` 字典 + `record_delta_change` handler 验证逻辑;特别 line 269-310 spec 段)
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-01-d8f-trial-unreachable.md §"主因(最可能):target_skill 路径不解析"
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-D-delta-mechanism-redesign.md §Gap 5 + §Gap 2(dual-track design)
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-A-personalization-angles.md(只读 §3 维度性分析 + §6 自检 — 防止把字面 angle 名混进 prose;不读 §2 的 25 个具体 angle 名)
    - workflow-skills/current/discover-personalization-factors/SKILL.md(参考统一术语:disposition / hook / anchor 等)
    - workflow-skills/current/generate-copy-candidates/SKILL.md(参考术语)
    - workflow-skills/current/personalized-copy-rubric-judge/SKILL.md(参考术语)
  </read_first>
  <behavior>
    SKILL.md prose 重写要求:
    - 保留 frontmatter `name` + `description`;保留 "What this skill does" / "Glossary" / "How to think" / "Anti-patterns" / "Reflection" / "Finishing" 节标题。
    - **新增 "## Trajectory attention model" 节**(在 "How to think" 之后):用统一术语描述 dual-track。一段约 80-120 字写"成功路径模式提取"(高 rubric 通过率 / 高 disposition 命中 / 多样性达标的 trajectory 暗示了哪些 reusable patterns),一段约 80-120 字写"失败路径模式提取"(rubric judgments 全 admit 缺判别力 / agent 在 reflection 中重复触发同 anchor type / hook word 来源单一这类失败模式所对应的 SKILL 引导缺陷)。
    - **新增 "## target_skill format" 节**(在 "Finishing" 之前):明确 target_skill 必须是 LIVE_SKILL_ROOT 之下的相对路径,格式 `current/<skill-slug>/SKILL.md`,给两个示例(只用 production node skill 名 — `current/discover-personalization-factors/SKILL.md` / `current/generate-copy-candidates/SKILL.md`),解释 evolution 类 skill(distill 自己)不是合法 target — 它不在 production loop。
    - **改写 "Anti-patterns" 节**:加一条 "do not propose deltas whose target_skill cannot resolve at runtime — invalid paths are silently skipped by the trial gate, wasting distill compute"。
    - **统一术语 lock**:整个 prose 中 "disposition" / "hook" / "anchor" / "floor" / "trajectory" / "pattern" / "evidence_ref" / "failure_type" 是合法词;"成功侧" / "失败侧" / "买家心智" / 用户口头举例字面 等不许出现(由 forbid_list grep gate 把守)。

    `evolution_tools.py:RECORD_DELTA_CHANGE_SPEC` 修改:
    - 把 `"target_skill": {"type": "string"}`(line ~290-291)改为 `"target_skill": {"type": "string", "description": "Path to the target skill file relative to the live skill root, format 'current/<skill-slug>/SKILL.md'. Must resolve to an existing production skill (not evolution skills like distill-skill-deltas itself).", "pattern": "^current/[a-z0-9][a-z0-9-]*/SKILL\\.md$"}`。
    - 同步在 `RECORD_DELTA_OBSERVATION_SPEC` 的 `target_skill` 字段加同样 description + pattern(observation 也带 target_skill,见 line ~239-260)。
    - SUBMIT_DELTA_DISTILLATION_FINAL_SPEC 的 nested target_skill 字段(line ~344-345)同步加。
    - `record_delta_change` handler(line ~158-185)的 `_RecordDeltaChangeArgs` pydantic class 已对 target_skill 做 type-only 验证;新增一个 `import re` 后的 module-level 常量 `_TARGET_SKILL_PATTERN = re.compile(r"^current/[a-z0-9][a-z0-9-]*/SKILL\.md$")`,并在 handler 验证 `parsed.change_type` 之后加一段 `if not _TARGET_SKILL_PATTERN.match(parsed.target_skill): raise ToolValidationError(message=f"target_skill {parsed.target_skill!r} must match pattern current/<skill-slug>/SKILL.md", tool_name="record_delta_change", arg_path="target_skill")`。
    - record_delta_observation handler 同步加 pattern 验证。

    单测 `tests/test_evolution_tools.py`(若已有则追加,无则新建):
    - `test_target_skill_must_match_pattern`:跑一个无效 target_skill(如 `"discover-personalization-factors"` 没前缀)调 `record_delta_change(args, state)`,断言 raise `ToolValidationError` 含 `"target_skill"` 与 `"pattern"`。
    - `test_target_skill_pattern_accepts_canonical`:跑一个有效 target_skill(`"current/generate-copy-candidates/SKILL.md"`)调 handler,断言成功(handler return value 含 delta_id)。
    - `test_record_delta_observation_target_skill_pattern`:同上但走 observation handler。
    - `test_skill_prose_has_no_user_example_phrases`:python 测试 open SKILL.md 的 read_text() 然后 assert 一组 forbid 词组(`["低价大牌", "周三早9点", "代理父亲", "信息饕餮", "多娃妈妈"]`)在内容中 0 命中(case-sensitive 即可,本身这些都是中文)。
  </behavior>
  <action>
    1. **重写 `workflow-skills/evolution/distill-skill-deltas/SKILL.md`**(整文件 rewrite — 保 frontmatter,改正文)。结构按上面 behavior 段:What / Glossary / How to think / **Trajectory attention model**(新增)/ Anti-patterns(扩) / Reflection / **target_skill format**(新增)/ Finishing。术语锁 disposition / hook / anchor / floor / trajectory / pattern。绝不引入字面用户口头举例(grep gate 把守)。
    2. **修改 `seers_harness/tools/evolution_tools.py`**:
       - 顶部 import 段加 `import re`(若已有则跳过)
       - 加模块级常量 `_TARGET_SKILL_PATTERN = re.compile(r"^current/[a-z0-9][a-z0-9-]*/SKILL\.md$")`,放在 `_REJECT_SELF_RATED_KEYS` 之类常量旁。
       - `RECORD_DELTA_CHANGE_SPEC`:`target_skill` 字段加 description(verbatim 见 behavior 段)+ `"pattern": "^current/[a-z0-9][a-z0-9-]*/SKILL\\.md$"`。
       - `RECORD_DELTA_OBSERVATION_SPEC`:同上。
       - `SUBMIT_DELTA_DISTILLATION_FINAL_SPEC` nested deltas[].target_skill:同上。
       - `record_delta_change` handler:在 `parsed = _RecordDeltaChangeArgs.model_validate(args)` 之后、`if parsed.change_type not in (...)` 之前,加 pattern 验证 raise ToolValidationError(verbatim 见 behavior 段)。
       - `record_delta_observation` handler:同样位置加 pattern 验证。
    3. **新增/扩展 `tests/test_evolution_tools.py`**:4 个测试如 behavior 段定义。
  </action>
  <verify>
    <automated>pytest -q tests/test_evolution_tools.py -x 2>&1 | tail -20 ; grep -nE '低价大牌|周三早.{0,2}9.{0,2}点|代理父亲|信息饕餮|多娃妈妈' workflow-skills/evolution/distill-skill-deltas/SKILL.md ; grep -c '^## Trajectory attention model' workflow-skills/evolution/distill-skill-deltas/SKILL.md ; grep -c '^## target_skill format' workflow-skills/evolution/distill-skill-deltas/SKILL.md ; grep -nE '_TARGET_SKILL_PATTERN' seers_harness/tools/evolution_tools.py</automated>
    <human-check>4 个新测全绿;forbid 词组 grep 0 hits;两个新节标题各 1 hit;`_TARGET_SKILL_PATTERN` 在 evolution_tools.py 出现 ≥ 4(定义 + RECORD_DELTA_CHANGE handler + RECORD_DELTA_OBSERVATION handler + 可能的 import re 之外引用)。</human-check>
  </verify>
  <done>
    - SKILL.md 重写完成,新增 "Trajectory attention model" + "target_skill format" 节,统一术语
    - tool spec 三处 target_skill 字段加 description + pattern
    - 两个 handler 加 runtime pattern 验证
    - 4 个新测全绿
    - grep 守门 forbid 词组 0 hits
    - phase-7 baseline 不回归(全套 pytest 全绿)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: _patch_from_portfolio_row warn log + _distill_after_stage1 evidence 持久化 + 单测</name>
  <files>seers_harness/validation/runner.py, tests/test_validation_runner.py</files>
  <read_first>
    - seers_harness/validation/runner.py(`_patch_from_portfolio_row` line ~525-538;`_distill_after_stage1` line ~482-522;现有 `flush_evidence` import 与调用位置)
    - seers_harness/validation/recording_provider.py(`RecordingProvider` 暴露 `request_log` 属性的方式)
    - seers_harness/validation/evidence_writer.py(`flush_evidence(request_log, evidence_dir)` 签名)
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-D-delta-mechanism-redesign.md §Gap 6
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-01-d8f-trial-unreachable.md §"主因 → 次因 → 三因"
  </read_first>
  <behavior>
    `_patch_from_portfolio_row` 修改:
    - 保留现有 None-return 语义(让 caller skip),但把 silent return 改成显式 print。
    - row.change_type != "modify_skill" → `print(f"[runner] trial_skipped delta_id={row.delta_id} reason=non_modify_skill change_type={row.change_type}", file=sys.stderr)`,return None。
    - live_target.exists() False → `print(f"[runner] trial_skipped delta_id={row.delta_id} reason=target_unresolvable target_skill={row.target_skill}", file=sys.stderr)`,return None。
    - 成功路径不打日志(否则 c=20 stage 3 stderr 噪声)。

    `_distill_after_stage1` 修改:
    - 在 `result = run_skill_via_tools(...)` 与 `artifact = DeltaDistillationArtifact.model_validate(result.artifact)` 之间,加 evidence flush 调用。
    - 用 `from seers_harness.validation.evidence_writer import flush_evidence` 已 import(line 148);若未 import 则加。
    - flush 路径:`evidence_dir = stage1_request_dir / "distill_evidence"`;调用 `flush_evidence(distill_provider.request_log, evidence_dir)`,包 try/except Exception:cleanup 失败 print 但不 raise(对齐 plan 08-10 的 best-effort 兜底语义)。
    - distill provider 已是 `RecordingProvider(provider_factory(), [])` — 它的 `request_log`(第二个 arg)在 run_skill_via_tools 中被填充。

    单测 `tests/test_validation_runner.py` 追加:
    - `test_patch_from_portfolio_row_warns_on_non_modify_skill`:构造一个 `change_type="add_skill"` row,调 `_patch_from_portfolio_row(row, live_skill_root)`,capsys 捕获 stderr,断言含 `"trial_skipped"` + `"non_modify_skill"`,return None。
    - `test_patch_from_portfolio_row_warns_on_unresolvable_target`:构造 `change_type="modify_skill"` 但 target_skill 指向不存在路径,断言 stderr 含 `"trial_skipped"` + `"target_unresolvable"`,return None。
    - `test_patch_from_portfolio_row_resolves_canonical_path`:用 tmp_path 模拟 live_skill_root,放一个 `current/foo-skill/SKILL.md`,row.target_skill=`"current/foo-skill/SKILL.md"`,断言 return SkillDeltaPatch 非 None;stderr 不含 trial_skipped。
    - `test_distill_persists_evidence_to_disk`:用 fake provider + 通过 monkeypatch 的 `run_skill_via_tools` 让 distill 跑一次假 trace;断言 `<stage1_request_dir>/distill_evidence/messages.jsonl` 存在且非空,`tool_calls.jsonl` / `artifact.json` / `usage.json` 同样存在。
    - `test_distill_evidence_flush_failure_does_not_mask_artifact`:monkeypatch `flush_evidence` 让其 raise PermissionError,断言 `_distill_after_stage1` 仍正常 return portfolio 且 stderr 含 cleanup 失败日志,不 raise PermissionError 上去。
  </behavior>
  <action>
    1. **修改 `seers_harness/validation/runner.py:_patch_from_portfolio_row`**(line ~525-538):两处 return None 之前加 print 到 stderr,精确字串如 behavior 段。
    2. **修改 `_distill_after_stage1`**(line ~482-522):
       - 在调 run_skill_via_tools 之后(已有 print "produced N proposals"),在 `artifact = DeltaDistillationArtifact.model_validate(result.artifact)` 之前(或之后,无依赖),插入 evidence flush 块:
         ```
         evidence_dir = stage1_request_dir / "distill_evidence"
         try:
             flush_evidence(distill_provider.request_log, evidence_dir)
         except Exception as cleanup_exc:
             print(f"[runner] distill_evidence flush failed: {safe_exc(cleanup_exc)}", file=sys.stderr)
         ```
       - `safe_exc` 在 runner.py 顶部已 import(line 147);若未 import 则补 import。
    3. **追加 5 个测试到 `tests/test_validation_runner.py`** 如 behavior 段定义。每个测试独立 fixture(tmp_path / monkeypatch / capsys 组合),不互相依赖。
  </action>
  <verify>
    <automated>pytest -q tests/test_validation_runner.py -k "patch_from_portfolio_row or distill_persists or distill_evidence_flush_failure" -x 2>&1 | tail -25 ; grep -c "trial_skipped" seers_harness/validation/runner.py ; grep -c "distill_evidence" seers_harness/validation/runner.py ; grep -c "flush_evidence(distill_provider" seers_harness/validation/runner.py</automated>
    <human-check>5 个新测全绿;`trial_skipped` 在 runner.py 出现 == 2(两个拒绝分支各 1 次);`distill_evidence` 出现 ≥ 2(目录路径 + 错误日志);`flush_evidence(distill_provider` 出现 == 1(distill 持久化调用)。</human-check>
  </verify>
  <done>
    - _patch_from_portfolio_row 两个拒绝分支显式 stderr 日志
    - _distill_after_stage1 调 flush_evidence 持久化 distill trace,best-effort 兜底
    - 5 个新测全绿
    - phase-7 baseline 无回归(全套 pytest 全绿)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM ↔ tool spec target_skill | LLM 提交字符串,tool spec pattern 是第一道边界;handler runtime 验证是第二道 |
| _patch_from_portfolio_row ↔ filesystem | row.target_skill 来自 LLM,直接拼 LIVE_SKILL_ROOT 后必须 exists 检查 |
| distill RecordingProvider ↔ disk | request_log 含 LLM messages 与 tool_calls,落盘前已经过 RecordingProvider 的 redaction |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-G3-01 | Tampering | LLM 提交 `../../etc/passwd` 类 path traversal | mitigate | tool spec pattern `^current/[a-z0-9-]+/SKILL\.md$` 拒绝 `..` / `/` / 大写;handler raise ToolValidationError |
| T-08-G3-02 | Information Disclosure | distill_evidence 目录含 trace,可能 leak request payload | accept | 与 production node evidence 同等级别;tests/smoke/.runs/ 已 gitignored;不引入新泄露面 |
| T-08-G3-03 | DoS | LLM 反复提交无效 target_skill,trial_skipped 日志膨胀 | mitigate | warn log 单行 + delta_id-keyed,c=20 batch 上限 4 deltas × 20 reqs = 80 行,可接受 |
</threat_model>

<verification>
- pytest -q 全套绿(预期 326+ tests after G1+G2,G3 新增 9 测试)
- grep gates(forbid 词组 / `_TARGET_SKILL_PATTERN` / `trial_skipped` / `distill_evidence`)全部满足
- SKILL prose dual-track 节存在,统一术语锁定
- 实测证据(post-batch G5):IF distill 产出至少 1 个有效 target_skill → `_patch_from_portfolio_row` 解析通过,`distill_evidence/` 非空,trial 真触发(由 G4 接线后真生效);若 distill 产 0 有效 target_skill → stderr `trial_skipped` 行可观测
</verification>

<success_criteria>
G3 ship 当且仅当:(a) target_skill 三处契约 grep-verifiable 一致;(b) `_patch_from_portfolio_row` 拒绝可观测;(c) distill 产出落盘到 `distill_evidence/`;(d) SKILL prose dual-track + 不含字面用户举例;(e) pytest 全绿。Real-LLM 验证延后到 G5 — 真实 batch 中 distill 产 delta 至少 1 条 target_skill 解析通过 / distill_evidence/ 非空。
</success_criteria>

<output>
Create `.planning/phases/08-evolution-wiring-and-runner-debt/08-G3-SUMMARY.md` when done.
</output>
