---
phase: 08-evolution-wiring-and-runner-debt
plan: G5
type: execute
wave: 5
gap_closure: true
depends_on:
  - 08-G4
files_modified:
  - .planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md
  - .planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md
autonomous: false
requirements: []
must_haves:
  goal: "在 G1..G4 全部落地 + pytest 绿后,直接跑真实 DeepSeek **Stage 3** (n=20, c=20) batch — 这是最接近生产的场景,一次性验证 F-08-B/C/01/D 全部修复。然后写 `08-VERIFICATION.md`(passed | gaps_found)并 close out `07-WRIN-TRIAGE.md`(7 个 scheduled 项 → phase-8 commit refs)。autonomous: false — 用户必须 spot-check 文案质量后才能 mark passed。"
  truths:
    - "(D8-ACC-1)Stage 3 batch 一次性完成,无 60s timeout / stale env / unhandled transient — runner.py 的 backoff + env-file + timeout 180s 都已落地"
    - "(F-08-B fix verification)每个 stage-3 req 三个 production node 的 `messages.jsonl[0].content` 长度 > 100 bytes — 表示 SKILL prose 真下发,不再裸奔。grep 全 batch 验证"
    - "(F-08-C fix verification)`copy_generation` 节点跨 20 reqs 的 `prompt_cache_miss` 均值落在 [500, 5000] tokens 区间 — 既非 120 token(过窄)也非 8000+(blanket whitelist 破坏 cache prefix)"
    - "(F-08-01 fix verification)至少 5/20 reqs trigger trial:`select_trial_delta` 返非 None,`trial_workspace/{_baseline,<delta_id>}/` 双 dir 存在,`evolution_snapshot.trials[]` 非空"
    - "(F-08-D Gap 8 fix verification)至少 1 个 delta 完成 status 转移(experimental → ready_for_review | rejected)— 由 batch 末尾 `apply_status_transitions` 触发;`portfolio_journal.jsonl` 至少 1 entry"
    - "(D8-ACC-3 retained)`index.json` 每行带 `failure_class` 字段,值取自 7-enum;`batch_summary.json` 含 `by_failure_class` 聚合 dict"
    - "(D8-ACC-5)`07-WRIN-TRIAGE.md` 的 7 个 scheduled 项目全部 → phase-8 commit refs(WR-01 → a99e65f / WR-02 → c740574 / WR-03,04,IN-08 → 45c61c9 / WR-05 → c858e09 / IN-01 → 96cf898 — 通过本 plan close out)"
    - "(locked)手动 spot-check 文案质量:user 随机抽 5 reqs 的 copy_generation/artifact.json,assert 不再是 '4-char modifier + product name' 模板,8-16 字 slogan 多样性可见"
  artifacts:
    - path: .planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md
      provides: "phase-8 acceptance 验证报告:status: passed | gaps_found;含 8 个 truths 的逐条 evidence 路径"
      contains: "status:"
    - path: .planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md
      provides: "7 个 scheduled 项 → phase-8 commit ref 映射"
      contains: "phase-8 commit"
    - path: tests/smoke/.runs/<batch-ts>/stage3/
      provides: "20 个 request_dir + index.json + batch_summary.json + portfolio_journal.jsonl"
      contains: "index.json"
  forbid_list:
    - "禁止用 FakeProvider / mock provider 替代真实 DeepSeek — 本 plan 的唯一证据是真实 batch"
    - "禁止跑 Stage 1 / Stage 2 重新热身 — 用户已锁:`--stage 3` 直接,Stage 3 最接近生产可一次性验证"
    - "禁止跳过 manual copy quality spot-check — 即使 8 个 grep gates 全过,文案质量仍需 user 眼检(F-08-B 修了 LLM 拿到 SKILL,但文案是否真的多样化仍需主观判断)"
    - "禁止把 08-VERIFICATION.md 标 passed 当有 grep gate 失败 — gaps_found 是合法 status,不要为了 close phase 强行通过"
    - "禁止把 batch 跑出来的 `.runs/<ts>/` 大目录 git add — 已 gitignored;只 commit `08-VERIFICATION.md` + `07-WRIN-TRIAGE.md`"
---

<objective>
**真实 DeepSeek Stage 3 acceptance batch** — phase 8 gap-closure 的最终接受门。G1..G4 全部修了,pytest 全绿,现在用一次真实 c=20 batch 一次性验证 4 个深层 finding 的修复都生效:
- F-08-B 修(LLM 真拿到 SKILL prose)
- F-08-C 修(信息密度落在合理区间)
- F-08-01 修(trial 真触发)
- F-08-D 修(bandit + uplift + status 真闭环)

batch 完成后写 08-VERIFICATION.md(8 truths 各一条 evidence 路径)+ close out 07-WRIN-TRIAGE.md。

Purpose: phase 8 charter D8-ACC-1..6 接受门要求 "real-LLM Stage 1+2+3 一次性"。用户 2026-05-28 决定 Stage 3 一次性验证(Stage 1/2 已在 0527 batch 跑过 + STOP B 终止,数据 + finding 已沉淀)。Stage 3 c=20 是最严苛场景,如果 Stage 3 PASSED,phase 7 + phase 8 双门同时关闭。
Output: 1 个真实 batch artifact 树(gitignored)+ 2 个文档 commit(08-VERIFICATION.md / 07-WRIN-TRIAGE.md updates)。
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/08-evolution-wiring-and-runner-debt/08-CHARTER.md
@.planning/phases/08-evolution-wiring-and-runner-debt/08-CONTEXT.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-B-copy-quality-rootcause.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-C-context-budget.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-01-d8f-trial-unreachable.md
@.planning/phases/08-evolution-wiring-and-runner-debt/findings/F-08-D-delta-mechanism-redesign.md
@.planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md
@seers_harness/validation/runner.py
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: 验证 pre-conditions — G1..G4 SUMMARY 全在 + pytest 全绿</name>
  <files>(无文件修改)</files>
  <read_first>
    - .planning/phases/08-evolution-wiring-and-runner-debt/08-G1-SUMMARY.md
    - .planning/phases/08-evolution-wiring-and-runner-debt/08-G2-SUMMARY.md
    - .planning/phases/08-evolution-wiring-and-runner-debt/08-G3-SUMMARY.md
    - .planning/phases/08-evolution-wiring-and-runner-debt/08-G4-SUMMARY.md
  </read_first>
  <behavior>
    检查 4 个 SUMMARY.md 都存在且 status 标 done。跑 `pytest -q` 全套确认无回归。
    若任一 SUMMARY 缺失或 pytest 失败,STOP — 不进入 Stage 3 batch。
  </behavior>
  <action>
    1. `ls .planning/phases/08-evolution-wiring-and-runner-debt/08-G{1,2,3,4}-SUMMARY.md` — 4 文件都存在
    2. `pytest -q 2>&1 | tail -3` — 全绿
    3. 若任一失败,raise 给 user;不进 Task 2
  </action>
  <verify>
    <automated>ls .planning/phases/08-evolution-wiring-and-runner-debt/08-G{1,2,3,4}-SUMMARY.md ; pytest -q 2>&1 | tail -3</automated>
    <human-check>4 SUMMARY 存在;pytest "XXX passed" 不含 "failed"</human-check>
  </verify>
  <done>
    - 4 个 SUMMARY 都存在
    - pytest 全绿
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: 真实 DeepSeek Stage 3 batch launch + 监控完成</name>
  <files>tests/smoke/.runs/&lt;batch-ts&gt;/(gitignored)</files>
  <read_first>
    - .env.local(存在 + DEEPSEEK_API_KEY suffix `****ab06` 已知)
    - seers_harness/validation/runner.py(CLI 参数;`--stage 3` 跳过 1+2)
  </read_first>
  <behavior>
    后台启动 batch,redirect log 到 phase-8 .run-logs/。每 ~5min 抽查进度。stage 3 PASSED 时 batch 完成。

    1. 启动前清旧 pid:`rm .planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/runner.pid` 若存在
    2. `mkdir -p .planning/phases/08-evolution-wiring-and-runner-debt/.run-logs`(应已存在)
    3. `TS=$(date -u +%Y%m%dT%H%M%SZ); LOG=".planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/runner-${TS}.log"`
    4. `nohup python -u -m seers_harness.validation.runner --env-file .env.local --stage 3 > "$LOG" 2>&1 &`
    5. `echo $! > .planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/runner.pid`
    6. 等 ~30-60min 墙钟(stage 3 c=20 一次性跑 20 reqs,paired control 让 trial reqs 翻倍 token 但并发让墙钟可控)
    7. 监控:每 5min `tail -20 $LOG` + `ps -p $(cat .../runner.pid)` 检查 alive,直到看到 `[runner] stage 3 PASSED` 或 `[runner] stage 3 FAILED`
  </behavior>
  <action>
    Run the launch sequence above. 监控直到 batch 完成。记录 batch_ts 与 out_dir(`tests/smoke/.runs/${TS}/`)。
    若 Stage 3 FAILED,记录失败原因到 08-VERIFICATION.md status=gaps_found;不强行通过。
  </action>
  <verify>
    <automated>tail -10 .planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/runner-*.log | tail -5 ; ls tests/smoke/.runs/ | tail -3 ; ls tests/smoke/.runs/&lt;batch-ts&gt;/stage3/ | wc -l</automated>
    <human-check>Stage 3 PASSED log 出现;stage3/ dir 含 20 个 request_dirs + index.json + batch_summary.json + portfolio_journal.jsonl</human-check>
  </verify>
  <done>
    - batch 完成(PASSED 或 FAILED,但已跑完)
    - out_dir 路径记录
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: 验证 8 个 truths 各一条 evidence 路径</name>
  <files>(无文件修改,只生成 evidence 备查)</files>
  <read_first>
    - tests/smoke/.runs/&lt;batch-ts&gt;/stage3/(全部产出)
  </read_first>
  <behavior>
    用 python 脚本对 20 reqs 全量扫描,逐条验证 truths。每条 grep / 计算结果记录,供 08-VERIFICATION.md 引用。

    Truth 1 (D8-ACC-1): batch 完成无 60s timeout / stale env / unhandled transient
      - 验证:`grep -iE 'timeout|stale.{0,5}env|unhandled.{0,5}transient' .run-logs/runner-${TS}.log` 应 0 hits(除了 transient_retries_per_turn config 那行 noise)

    Truth 2 (F-08-B fix): 每 stage-3 req × 3 production node messages.jsonl[0].content 长度 > 100 bytes
      - python:遍历 stage3/*/evidence/{factor_discovery,copy_generation,personalized_copy_rubric}/messages.jsonl,取第一行 json.loads → message[0]['content'],assert len(content) > 100
      - 20 reqs × 3 node = 60 assert;输出 min/max/mean 长度统计

    Truth 3 (F-08-C fix): copy_generation 跨 20 reqs prompt_cache_miss 均值 ∈ [500, 5000]
      - python:遍历 stage3/*/evidence/copy_generation/usage.json,取 prompt_cache_miss_tokens;求 mean / median / p10 / p90;assert 500 ≤ mean ≤ 5000

    Truth 4 (F-08-01 fix): 至少 5/20 reqs trigger trial
      - python:scan stage3/*/evolution_snapshot.json,count len(trials) > 0 的 req 数;assert ≥ 5
      - 同时 ls tests/smoke/.runs/${TS}/stage3/*/trial_workspace/ 看 dir 存在数

    Truth 5 (F-08-D Gap 8 fix): 至少 1 delta 完成 status 转移
      - python:读 batch_summary.json 或 portfolio 最终 dump,find row.status != "experimental";assert ≥ 1
      - 同时:`portfolio_journal.jsonl` 行数 ≥ trial 触发的 req 数

    Truth 6 (D8-ACC-3): index.json 每行带 failure_class;batch_summary by_failure_class 存在
      - python:`index.json` parse;每 row 含 `failure_class` 字段;value ∈ {auth, rate_limit, transient, malformed_tool_args, schema_violation, runner_bug, ok}
      - `batch_summary.json.by_failure_class` 是 dict

    Truth 7 (D8-ACC-5): 07-WRIN-TRIAGE.md 7 项映射 — 在 Task 4 关闭

    Truth 8 (manual spot-check): user 抽 5 reqs 看 copy_generation/artifact.json 文案质量
      - 不可自动化,Task 4 user 介入
  </behavior>
  <action>
    写一个 inline python 脚本(或 bash + python -c 组合)输出 truth1..6 的 verdict + numbers,保存到 `.planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/g5-verification-${TS}.txt`。Truth 7 / 8 留给 Task 4。
  </action>
  <verify>
    <automated>cat .planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/g5-verification-*.txt | tail -30</automated>
    <human-check>verdict 文件存在;6 truths 的 verdict 全部 PASS 或明确标 FAIL 含数字</human-check>
  </verify>
  <done>
    - 6 truths 自动化验证完成,verdict 文件落地
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: User spot-check + 写 08-VERIFICATION.md + close 07-WRIN-TRIAGE.md</name>
  <files>.planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md, .planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md</files>
  <read_first>
    - .planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/g5-verification-*.txt(Task 3 verdict)
    - tests/smoke/.runs/&lt;batch-ts&gt;/stage3/&lt;rid&gt;/evidence/copy_generation/artifact.json(随机 5 reqs)
    - .planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md(现状 7 scheduled 项)
  </read_first>
  <behavior>
    1. 抽 5 reqs 的 copy_generation/artifact.json `candidates[*].text`,展示给 user。
    2. user 判定文案质量(spot-check Truth 8):
       - 是否仍 "4-char modifier + product name" 模板?
       - 5 candidates 是否多样化(不同 anchor type / disposition)?
       - 8-16 字长度?
       - 与目标 product 关联自然?
    3. 基于 Task 3 自动化 verdict + Task 4 spot-check,决定 status:
       - 全 PASS → `status: passed`
       - 任一 truth FAIL → `status: gaps_found`,列 gap 与建议
    4. 写 `08-VERIFICATION.md` 严格遵循 GSD verification 模板:
       ```
       ---
       status: passed | gaps_found
       phase: 08-evolution-wiring-and-runner-debt
       batch_id: <ts>
       commit_of_record: <git rev-parse HEAD>
       acceptance_gates: 8
       ---

       # Phase 8 Verification

       ## Truths Verification

       | # | Truth | Status | Evidence |
       |---|-------|--------|----------|
       | 1 | D8-ACC-1 batch 无 timeout/stale env/transient | PASS | runner-<ts>.log 0 grep hits |
       | 2 | F-08-B per-node SKILL prose > 100 bytes | PASS | min=<N> mean=<N> across 60 messages |
       | ... 8 行 |

       ## Manual Copy Quality Spot-check

       5 reqs sampled: <rid1>, <rid2>, ...
       Verdict: ...

       ## Gaps (if any)
       ...

       ## Closure
       Phase 8 status: <verdict>;phase 7 acceptance gate <opened/blocked>
       ```
    5. 更新 `07-WRIN-TRIAGE.md`:7 个 scheduled 项各加 phase-8 commit ref 列(WR-01 → a99e65f / WR-02 → c740574 / WR-03,04,IN-08 → 45c61c9 / WR-05 → c858e09 / IN-01 → 96cf898 / IN-04 之前已 fix-now 不在此 7 项)
    6. 单 commit 提交两文件:`docs(08-G5): phase-8 verification + WRIN-TRIAGE closeout`
  </behavior>
  <action>
    抽 5 reqs,present to user,记录 user verdict,写 08-VERIFICATION.md 与 07-WRIN-TRIAGE.md。
  </action>
  <verify>
    <automated>cat .planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md | grep "^status:" ; grep -c "phase-8 commit" .planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md</automated>
    <human-check>08-VERIFICATION.md status: passed 或 gaps_found;07-WRIN-TRIAGE.md 至少 5 处 "phase-8 commit" ref(7 items 各 1 ref,部分可同 commit)</human-check>
  </verify>
  <done>
    - 08-VERIFICATION.md 写完 + status 标定
    - 07-WRIN-TRIAGE.md 7 items 全映射到 phase-8 commits
    - 单 commit 落地
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| runner ↔ DeepSeek 真实 API | rate-limit / quota / network 真实约束;无 mock |
| batch artifact ↔ git | tests/smoke/.runs/ 已 gitignored;只 commit docs |
| user spot-check ↔ phase acceptance | 自动 grep gates 不能替代主观文案质量判定 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-G5-01 | DoS | DeepSeek 端 rate limit 在 c=20 paired control 下加剧 → 部分 req fail | accept | 失败由 fail-fast 路由捕获;08-VERIFICATION.md 标 gaps_found,不掩盖 |
| T-08-G5-02 | Information Disclosure | batch artifact 含 trace 与 LLM messages | accept | tests/smoke/.runs/ gitignored,与 0527 batch 同样级别 |
| T-08-G5-03 | Repudiation | user spot-check 后悔 mark passed | mitigate | 08-VERIFICATION.md 明确列出 5 sample rids;事后可重审 |
</threat_model>

<verification>
- Task 1 / 2 / 3 / 4 全部 done
- 08-VERIFICATION.md 落地(status 标 passed 或 gaps_found)
- 07-WRIN-TRIAGE.md 7 items closed
- batch artifact 在 tests/smoke/.runs/<ts>/(gitignored)
</verification>

<success_criteria>
G5 ship 当且仅当:(a) Stage 3 batch 跑完(成功或显式失败);(b) 8 truths 各有 evidence 记录;(c) user spot-check 文案质量;(d) 08-VERIFICATION.md 写完;(e) 07-WRIN-TRIAGE.md 7 items 全 close。

phase 8 acceptance verdict:
- status: passed → phase 8 close,unblock phase 7 acceptance(D8-ACC-1..6 全过)
- status: gaps_found → 列具体 gap,如必要 spawn 新 gap-closure round(罕见;G1..G4 设计上应能闭合 4 finding)
</success_criteria>

<output>
Create `.planning/phases/08-evolution-wiring-and-runner-debt/08-G5-SUMMARY.md` when done.
</output>
