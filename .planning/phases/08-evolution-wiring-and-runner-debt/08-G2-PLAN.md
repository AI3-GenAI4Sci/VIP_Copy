---
phase: 08-evolution-wiring-and-runner-debt
plan: G2
type: execute
wave: 2
gap_closure: true
depends_on:
  - 08-G1
files_modified:
  - seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md
  - seers_harness/workflow/payloads.py
  - workflow-skills/current/generate-copy-candidates/SKILL.md
  - tests/test_payloads_disclosure.py
autonomous: false
requirements: []
must_haves:
  goal: "把 context disclosure 当信息论问题处理:产出书面分析 `CONTEXT_DISCLOSURE_ANALYSIS.md`(cache-prefix 稳定字段 vs per-request 字段、信息密度、最佳披露边界),用户签字确认后再改 `copy_payload_for` / `rubric_payload_for` + SKILL line 41。F-08-C 观察的 cache_miss=120 token 反映 user_state 整体被剥离;blanket whitelist 又会把 cache_miss 推到 8000+。目标:copy_generation prompt_cache_miss ∈ [500, 5000] tokens 区间(信息密度合理 + cache prefix 仍稳定)。"
  truths:
    - "(F-08-C)`seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md` 存在,含三段:(1) cache-prefix-stable 字段集 vs per-request 字段集,(2) 每个候选字段的信息密度评估(entropy / cross-user 区分度 / SKILL hook 可用性),(3) 最终披露边界提案 + 在边界外字段排除理由"
    - "(F-08-C)CONTEXT_DISCLOSURE_ANALYSIS.md 末尾含 `Sign-off: <date> <user-name>` 行;无此行,implementation task 不得启动"
    - "(F-08-C)`copy_payload_for` 增量披露的字段集合 verbatim 来自 CONTEXT_DISCLOSURE_ANALYSIS.md 的"最终披露边界提案",不引入 ANALYSIS 文档之外的额外字段"
    - "(F-08-C)`rubric_payload_for` 增传 factors_artifact + bridge_logic / used_copyable_hooks / intended_effect(让 SKILL workflow step 1 'Reconstruct the user' 可执行),依据同一 ANALYSIS 文档"
    - "(F-08-C)`generate-copy-candidates/SKILL.md` line 41 'Hook words come only from factor.evidence_refs[].value or derived_features_by_product[product_id] bucket label. Nowhere else.' 改写后引用与新增白名单字段一致;SKILL 增量 prose **不**字面引用用户口头举例(forbid_list 守则)"
    - "(F-08-C)pytest 单测断言 copy_payload_for 输出 dict.keys() 严格 ⊆ ANALYSIS 表 + 现有字段;rubric_payload_for 每条 candidate 出现 bridge_logic dict"
  artifacts:
    - path: seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md
      provides: "信息论分析文档 + 字段白名单提案 + Sign-off 占位"
      contains: "Sign-off:"
    - path: seers_harness/workflow/payloads.py
      provides: "copy_payload_for 与 rubric_payload_for 按 ANALYSIS 增量披露"
      contains: "user_state"
    - path: workflow-skills/current/generate-copy-candidates/SKILL.md
      provides: "SKILL line 41 规则与新披露字段对齐;新增 prose 不含字面用户举例"
    - path: tests/test_payloads_disclosure.py
      provides: "断言新字段集严格匹配 ANALYSIS"
  key_links:
    - from: seers_harness/workflow/payloads.py:copy_payload_for
      to: seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md
      via: "returned dict keys ⊆ ANALYSIS whitelist"
      pattern: "user_state.*behavior|user_state.*context"
    - from: workflow-skills/current/generate-copy-candidates/SKILL.md
      to: seers_harness/workflow/payloads.py
      via: "SKILL line 41 hook source rule references payload keys"
      pattern: "Hook words"
  forbid_list:
    - "禁止 在 SKILL prose 中字面引用用户口头举例:'低价大牌','大牌不贵','周三早9点','代理父亲','信息饕餮','多娃妈妈','金卡仪式感','24h scroll','睡前种草' 等(grep gate 见 acceptance_criteria)"
    - "禁止 把 F-08-A 的 25 个 angle 名当 SKILL prose 直接抄入 —— 这些是规划期 sanity-check 材料,不是 prose 素材"
    - "禁止 在 implementation task(T2)未拿到 ANALYSIS 文档 Sign-off 行的情况下写代码 —— blocking checkpoint"
    - "禁止 blanket whitelist 整个 user_state(F-08-C 已示这会让 cache_miss 跳到 8000+,破坏 prompt-prefix cache);披露字段必须分级"
    - "禁止 跨过 ANALYSIS 单方面在 payloads.py 引入 ANALYSIS 之外的字段(代码与文档必须一致;单测 grep gate 覆盖)"
---

<objective>
F-08-C 观察的不是"copy 节点缺信息"那么简单 —— 是"必要信息没传 + 但 blanket whitelist 又会破坏 prompt-prefix cache 稳定性"的两难。本 plan 分两步:T1 是 research + design,产出 `seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md`(信息论视角:cache-prefix 稳定 vs per-request 变化字段 / 每字段信息密度 / 最佳披露边界提案),用户在该文档末尾写 `Sign-off:` 行后才解锁 T2;T2 是按 sign-off 后的 ANALYSIS 文档照单改 `copy_payload_for` + `rubric_payload_for` + SKILL line 41 与相关 prose。

Purpose: 用户拒绝粗暴 blanket whitelist("context 的披露是不是可以仔细研究一下,可能和缓存命中也相关,信息量上过多或者少都是不可取的")。F-08-C 提出的"加 user_state.behavior + user_state.context 给 copy_gen"是个起点,但需要量化论证哪些字段真值得披露(per-user 区分度高 + 文案 hook 可用)、哪些字段 stable(适合放进 prompt prefix 给 cache 命中)、哪些字段 per-request 变(放尾部不污染 prefix)。本 plan 把这件事正式化:先研究、人工签字、再实装。

Output: ANALYSIS 文档(checkpoint blocking,user sign-off);随后 payloads.py + SKILL.md atomic commit。`pytest -q` 全绿。Real-LLM evidence target 在 G5 验证:copy_generation prompt_cache_miss ∈ [500, 5000] tokens(目前 120,blanket 会跳到 8000+)。
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/08-evolution-wiring-and-runner-debt/08-CONTEXT.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-C-context-budget.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-A-personalization-angles.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-B-copy-quality-rootcause.md
@.planning/phases/08-evolution-wiring-and-runner-debt/.continue-here.md
</context>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task G2-T1: 信息论披露边界 research + ANALYSIS.md + 用户 Sign-off</name>
  <files>
    seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md (new)
  </files>
  <read_first>
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-C-context-budget.md(整文件,§1 顶层 key 对照表 / §2 token 成本曲线 / §4 字段-by-字段差集 / §7 提案是材料)
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-A-personalization-angles.md §6 附录(可机检 angle → field-rule 索引,告诉你哪些字段是 hook 真有用 vs 哪些是 anchor 噪声)
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-B-copy-quality-rootcause.md §5 + §6(说明 SKILL prose 真下发后 LLM 会用 anchor type 体系,而不是 4 字情绪+商品名;由此判断哪些字段是 anchor 候选)
    - seers_harness/workflow/payloads.py 全文件(已在 G1 read,确认 _scenario_dict 接口与 derived_features_by_product / list_context 已传字段,不重复披露)
    - tests/smoke/.runs/20260527T123110Z/stage1/-6834635816105165003/factor_discovery/usage.json + copy_generation/usage.json + personalized_copy_rubric/usage.json(三个真实 usage 数,F-08-C §2 来源)
    - tests/smoke/.runs/20260527T123110Z/stage1/-6834635816105165003/copy_generation/messages.jsonl 第 1 行 content(看现状 prompt 长什么样,prefix 哪段是稳定的)
  </read_first>
  <what-built>
    一个研究文档 `seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md`,内部至少包含 5 段:

    §1 **Cache-prefix 稳定性分类** —— 列出 user_state 全集(profile / behavior / context 三层下所有字段),逐字段标注 "stable across requests in same batch (prefix-cacheable)" vs "varies per request (prefix-busting)"。证据:从 batch 内多个 request 的 user_state 读字段值,看哪些跨 request 同 user 不变(profile.age / register_days / vip_level)、哪些每 request 变(seq_click_brand_48h / context.hour 之类)。

    §2 **信息密度量化** —— 对每候选字段,从 11 个真实 user 的 user_state(F-08-A 表 1 来源同一批 batch)估算:cross-user entropy(值的离散度)、SKILL anchor 可用性(F-08-A 25 angles 哪几条要用此字段)、字符成本(典型字符串长度)、是否被 factor.evidence_refs 已经间接传达。每字段一行表。

    §3 **披露边界提案** —— 把字段分入 4 类:
      (a) Tier-A:必传给 copy_generation(高信息密度 + 在 cache prefix 段或 stable);
      (b) Tier-B:必传给 copy_generation(高信息密度但 per-request 变,放 payload 尾部);
      (c) Tier-C:仅传给 rubric(rubric 只 reconstruct user 的辅助 context,不参与 hook);
      (d) Tier-D:不披露(低信息密度 / 已被 factor 覆盖 / 低 prevalence)。

    §4 **rubric 额外增传项** —— bridge_logic / used_copyable_hooks / intended_effect / factors_artifact —— 给 SKILL workflow step 1 'Reconstruct the user' 真材料(F-08-C §6.1)。

    §5 **预期 token 预算** —— 给出 expected `prompt_cache_miss` 区间(target [500, 5000] tokens for copy_generation)与算法(Tier-A 字段进 prefix → cache hit;Tier-B 进 tail → cache miss 增量)。

    最末一行预留 `Sign-off: __DATE__ __USER__`(占位待人工填)。

    **撰写约束**:文档可以引用 F-08-A 字段名(seq_click_brand_48h 等),但**不**字面引用 F-08-A 的 25 个 angle 名(代理父亲 / 多娃妈妈 / 金卡仪式感 等)—— 这些是 SKILL 实施期的"语义检查"对象,不是 ANALYSIS 文档主语。文档全程用项目术语(disposition / hook / floor / anchor type / cache-prefix / entropy)。
  </what-built>
  <how-to-verify>
    1. 检查文件存在:`ls seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md`
    2. 检查 5 段都有:`grep -nE "^## §[1-5]" seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md` 命中数 ≥ 5
    3. 检查含 Sign-off 占位:`grep -n "^Sign-off:" seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md` 命中 ≥ 1
    4. 用户阅读 §3 披露边界提案,确认 Tier-A/B/C/D 的判定与你心目中的"信息密度合理 + cache 稳定"标准吻合;确认 rubric 增传项符合 SKILL workflow step 1 的需求
    5. 用户阅读 §5 token 预算,确认 [500, 5000] 是合理目标(blanket whitelist 已在 F-08-C §2 显示会到 ~8000+)
    6. 如果 §3 提案合理,用户在末尾把 `Sign-off: __DATE__ __USER__` 替换成真日期 + 名字(e.g. `Sign-off: 2026-05-28 user`)
  </how-to-verify>
  <resume-signal>
    用户 reply 内容:
    - 若签字接受 → 在 ANALYSIS 文件末尾改 `Sign-off:` 占位,然后 reply 含 `approved`(主 agent grep `Sign-off: \\d{4}-\\d{2}-\\d{2}` 命中后解锁 T2)
    - 若有要求改:reply "revise: ..."(主 agent 调度 sub-agent 按反馈改 ANALYSIS,不进入 T2 直到再次 approved)
    - 若否决整个方案:reply "reject"(走 phase-split 路径,详见 escalation rules)
  </resume-signal>
</task>

<task type="auto" tdd="true">
  <name>Task G2-T2: 按 ANALYSIS 文档实装 payloads.py 增量披露 + SKILL line 41 改写</name>
  <files>
    seers_harness/workflow/payloads.py (modify copy_payload_for + rubric_payload_for + provider_payload_for_node dispatch)
    workflow-skills/current/generate-copy-candidates/SKILL.md (modify line 41 + 邻接 prose)
    tests/test_payloads_disclosure.py (new)
  </files>
  <read_first>
    - seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md(T1 产出,带 Sign-off 行,**只能**实装该文档 §3 + §4 列出的字段;T1 未签字时 raise 拒绝执行)
    - seers_harness/workflow/payloads.py 整文件(已于 G1 阶段读过,line 86-112 = copy_payload_for / 115-147 = rubric_payload_for / 150-175 = provider_payload_for_node 分发)
    - workflow-skills/current/generate-copy-candidates/SKILL.md 整文件(68 行;line 41 是 hook source rule;line 27 anchor type 段不动 —— G3 才动)
    - tests/test_payloads_loop06_audit.py(模仿其 grep 风格写新测试;它已 grep 'request/list_group' 与 'score_all_candidates_together_after_hard_rules')
    - .planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-C-context-budget.md §7.1/7.2(参考 code shape,但实施时按 ANALYSIS 提案不按 finding 提案 —— ANALYSIS 是 sign-off 后的 source of truth)
  </read_first>
  <behavior>
    - Test 1(grep gate — Sign-off):测试启动时 assert ANALYSIS.md 含 `Sign-off: \\d{4}-\\d{2}-\\d{2}` regex 命中 ≥ 1;否则 skip(防止 T1 未签字时跑实装)
    - Test 2(copy_payload keys ⊆ ANALYSIS):copy_payload_for 输出 dict 内 user_state 子 dict 的 keys 严格匹配 ANALYSIS §3 Tier-A + Tier-B 字段集(单测把 ANALYSIS 表 hardcode 一次,二者必须 byte-identical)
    - Test 3(rubric_payload 含 factors + bridge_logic):rubric_payload_for 返回 dict 含 `"factors"` key 非空 list AND 每条 candidate 含 `"bridge_logic"` dict + `"used_copyable_hooks"` list + `"intended_effect"` str
    - Test 4(SKILL line 41 改写一致):grep `generate-copy-candidates/SKILL.md` line 41 区域,断言新规则文本中提及的字段名 ⊆ ANALYSIS Tier-A + Tier-B
    - Test 5(forbid 字面用户举例 — SKILL prose):`grep -nE '低.{0,3}价.{0,3}大牌|大牌.{0,3}不贵|周三|代理父亲|信息饕餮|多娃妈妈|金卡仪式|睡前种草' workflow-skills/current/generate-copy-candidates/SKILL.md` 命中数 == 0
    - Test 6(provider_payload_for_node 分发):dispatch 到 rubric 时同时传 copy_artifact 与 factors_artifact 两个 deps,签名向后兼容(copy_artifact 单参调用仍工作)
  </behavior>
  <action>
    **Pre-flight:** Test 1 自动 skip 守门 —— 但 T2 启动前先在脚本内 `grep` ANALYSIS.md 的 Sign-off 行;如果没有,exit 非零并提示 "G2-T1 not signed off"。

    1) `payloads.py:copy_payload_for`(第 86-112 行):
       - 在 return dict 中,根据 ANALYSIS §3 Tier-A + Tier-B,新增 `"user_state": {...}` 子键 —— 内部仅放 ANALYSIS 列出的 behavior 子集 + context 子集 + (可选)profile_summary 子集;**不**整体塞 user_state;
       - 不加 ANALYSIS 之外的字段;
       - 保留现有 factors / products / target_products / derived_features_by_product / list_context / candidate_generation_policy 不变。

    2) `payloads.py:rubric_payload_for`(第 115-147 行):
       - 函数签名加 `factors_artifact: dict[str, Any] | None = None` 默认 None(向后兼容);
       - 在 candidate dict 中新增 `bridge_logic`(从 copy.candidates[i].bridge_logic 取)、`used_copyable_hooks`、`intended_effect` 三 key;
       - 在 return dict 顶层新增 `"factors": list((factors_artifact or {}).get("factors") or [])`;
       - 按 ANALYSIS §4 Tier-C 决定是否加 `"user_state_summary": {...}`(profile + context 子集,非 behavior 重复)。

    3) `payloads.py:provider_payload_for_node`(第 150-175 行):
       - rubric 分发改成 `factors_artifact=deps.get("factor_discovery") or {}` 同时传过去(F-08-C §3.3 提议);
       - 其余 dispatch 不动。

    4) `workflow-skills/current/generate-copy-candidates/SKILL.md` line 41 改写:
       - 原:`Hook words come only from factor.evidence_refs[].value or derived_features_by_product[product_id] bucket label. Nowhere else.`
       - 新:用项目统一术语描述新字段集(具体文本由 ANALYSIS §3 + Sign-off 决定;**禁止**字面引用 F-08-A 的 25 个 angle 例子;新字段名按 payloads.py 实际 key 命名)。
       - 同时检查 SKILL line 27 anchor type 段是否影响,**不动**(那是 G3 范围)。

    5) `tests/test_payloads_disclosure.py` 新建,6 个 test 对应 behavior 1..6;Test 2 把 ANALYSIS 提案 keys 显式 hardcode(防止 silent drift)。

    6) **forbid_list 自查**:
       - SKILL.md grep 5 个用户举例 phrase 都 0 hits;
       - payloads.py 没有 ANALYSIS 之外的字段;
       - 没有 blanket-whitelist 把整 user_state 塞进去。
  </action>
  <acceptance_criteria>
    - `pytest -q` 全套 + 6 new tests 全绿
    - `grep -nE '低.{0,3}价.{0,3}大牌|大牌.{0,3}不贵|周三|代理父亲|信息饕餮|多娃妈妈|金卡仪式|睡前种草' workflow-skills/current/generate-copy-candidates/SKILL.md | grep -v '^[#]'` 命中数 == 0
    - `python -c "from seers_harness.workflow.payloads import copy_payload_for; from seers_harness.domain.models import Scenario; ..."` 用 fixture 跑一次,断言返回 dict 的 user_state 子 keys 严格 ⊆ ANALYSIS Tier-A + Tier-B 集合(test 自动覆盖)
    - `git diff --stat seers_harness/workflow/CONTEXT_DISCLOSURE_ANALYSIS.md` 显示该文件不在本 commit(T1 已 commit;T2 不改它)
    - rubric_payload_for fixture 测试:每个 candidate dict 含 bridge_logic 非空(若 copy_artifact.candidates[i] 有该字段)
  </acceptance_criteria>
</task>

</tasks>

<verification>
- T1 完成 = 文件存在 + Sign-off 行存在(`grep "Sign-off: \\d{4}-\\d{2}-\\d{2}" CONTEXT_DISCLOSURE_ANALYSIS.md` ≥ 1)
- T2 完成 = pytest 全绿 + 6 个新 test 通过 + grep gates 通过 + payloads / SKILL line 41 与 ANALYSIS 一致
- Real-LLM 验证延后到 G5(copy_generation prompt_cache_miss ∈ [500, 5000] tokens)
</verification>

<success_criteria>
G2 ship 当且仅当:(a) ANALYSIS 文档存在 + 用户签字;(b) payloads.py 增量披露严格匹配 ANALYSIS;(c) SKILL line 41 改写一致 + 不含字面用户举例;(d) pytest 全绿。Real-LLM 信息密度落点延到 G5 验证。
</success_criteria>

<output>
Create `.planning/phases/08-evolution-wiring-and-runner-debt/08-G2-SUMMARY.md` when done.
</output>
