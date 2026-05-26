---
phase: 05-cleanup-deletes-tests-regression
artifact: research
gathered: 2026-05-26
mode: in-process (no subagent — workflow runtime missing gsd-phase-researcher)
---

# Phase 5 Research

研究目的：在落 PLAN.md 之前，确认 CONTEXT.md D-01..D-15 的事实假设在当前
workspace 代码里成立；任何与现实不符的决策在此修订并由 plan 引用。

## 1. CLEAN-03 假设的实际验证

**D-06 假设**：`workspace/seers_harness/` 下不存在 hand-handler / rubric judge
之外的硬检查门。

**实际**：假设**不完全成立**。`workflow/payloads.py:113-156` 的
`rubric_payload_for` 仍然消费 `hard_check_artifact` 并按 `passed=False /
blocking_rule_ids` 过滤 candidate；`workflow/dag_runner.py:183` 通过
`deps.get("hard_check") or {}` 显式把该参数连入 DAG 节点路径。这是
c14/c15/c16 留下的最后一处 hard-check gate。

**裁决（Q2/A1）**：删除该参数与过滤分支。理由：

- c17 没有任何节点产出 `hard_check` artifact，所以分支永远走空字典路径，是
  纯结构性残留。
- ADR-01-PRINCIPLE-01 把 rubric 判断划入 tool handler（hand role）+ rubric
  judge 文字判断，不再走 payload 层 gate。
- `dag_runner.py:183` 的 `deps.get("hard_check") or {}` 同步删除，签名不需要
  再接 `hard_check_artifact`。

其他被 grep 的关键词（`STOP_GATE / polling / self_check / gate_`）只在测试
负面断言里出现（断言这些字段/路径**不存在**），属于结构性回归门，不动。

## 2. c14/c15/c16 标记普查

`rg 'c14|c15|c16|verbatim from c' seers_harness/ tests/` 命中 17 处，10 个
文件。两类，处理方式不同：

**类 A — 注释 / docstring 里的历史溯源（必须 D-02 / D-03 清理）**：
- `seers_harness/domain/models.py:3` —— docstring 提 "legacy c14/c15 JSON"
- `seers_harness/workflow/dag_runner.py:5,35` —— docstring 提 c16 polling
- `seers_harness/workflow/payloads.py:12` —— "c16 legacy fan-out quota fields"
- `seers_harness/provider_runtime/base.py:5,53,56` —— "c16 parallel JSON" /
  "c16 ProviderResult signature" / "c16 ordering verbatim"
- `seers_harness/tools/skill_tools.py:38` —— "Verbatim helpers from c16
  check_tools.py" 横幅
- `tests/test_provider_result_shape.py:86` —— "the c16 parallel JSON path"
- `tests/test_provider_line_budget.py:41` —— "c16 dual entry point"
- `tests/test_dag_runner_integration.py:6,108,128` —— "c16 agent_loop_summary"
- `tests/test_payloads_loop06_audit.py:9,32,40` —— "c16 quota fields"

**类 B — 测试函数名 / docstring 里作为负面断言的 c15/c16 标签**：
- `tests/test_models_bridge.py:3,12,21,22,25` —— `test_c16_pair_present`,
  `test_c15_slots_absent`, "c17 BridgeLogic carries only the c16 anchor pair"
- `tests/test_models_factor.py:44,45,59` —— `test_c15_legacy_fields_absent`,
  "Principle 8 — clean delete of c15 legacy plain-text fields"
- `tests/test_models_rubric.py:40,50` —— `test_c15_legacy_aggregate_fields_absent`,
  "c15 legacy aggregate fields removed"

类 B 处理：**改写函数名 + docstring 让 c14/c15/c16 标签消失**，断言体保留
（按 schema 形态命名，例如 `test_anchor_pair_present` /
`test_legacy_plain_text_fields_absent`）。D-03 明确："whatever remains is
justified by the current schema, not by historical lineage" —— 测试名是文档
表面，必须按 schema 形态写。

## 3. 内部梗 token / lint 表的根因修订（D-04 重写）

**原 D-04 假设**：Phase 4 SKILL.md 上的 12-token grep lint 推广为 workspace
工程级门。

**实际**（用户 2026-05-26 澄清）：lint 表不是穷举禁词表，是 SKILL.md prose
的"反举例"保险。根因是：

> 用户画像里的具体 token（购物记录、最近搜索、品牌偏好等
> `user_state.behavior` 内的具体值）不得 verbatim 出现在生成的 copy 中。一旦
> verbatim 出现，离线下发到没有该历史的用户就会出错。

根因的真正执行点是 `tools/skill_tools.py` 的 `record_candidate` runtime 校验
（`tests/test_skill_tools_record_candidate.py:177-186` 已覆盖：把 fixture 的
`recent_search_cat3_30d` 里的 token 当作禁词集合，candidate text 命中即
`ToolValidationError`）。这是**动态、按 fixture 生效的**，不依赖任何固定
列表。

12-token lint 是 SKILL.md prose 的"不该靠列举具体类目教模型"的事后保险；
列表只是抽样。

**`维生素` 同时出现在两处**：

- `intake/categories.py` 的 `TARGET_CATEGORIES = ("防晒霜/乳", "牙膏/牙粉",
  "维生素", "香水", "护肩")` —— 真实业务类目，load-bearing
- `tests/test_skill_tools_record_candidate.py:177-186` —— `维生素` 作为
  `recent_search_cat3_30d` fixture 的 user-history token，验证 runtime 禁令

工程级 grep 门会把这 27 处真实业务数据 / 真实 runtime 校验一律误判。

**修订后的 D-04**：

| 维度 | 决议 |
|---|---|
| 是否推广为工程级 grep 门 | **不推广。** SKILL.md lint 维持 Phase 4 现状不动。 |
| 全工程是否清洗 12 token | **否。** 不动 `intake/categories.py`、`tests/`、`docs/{design,memory}.md` 描述真实类目的段落、`record_candidate` runtime 测试。 |
| 真正执行点是什么 | `record_candidate` runtime 校验；fixture 里的 `user_state.behavior.*` token 即禁词集合，candidate text 命中即抛 `ToolValidationError`。这是动态的，已经覆盖。 |
| Phase 5 实际改动 | 清类 A 注释/docstring 时顺手核查是否有把 token 当**活例子**嵌入注释 / docstring / 段落正文的情况 —— 大概率没几处。无新 grep 门、无工程级 CI、无路径白名单。 |

D-04 在 CONTEXT.md 的原文保留作为讨论锚点；本文件的修订版是 PLAN.md 引用
的版本。

## 4. `extra="ignore"` 翻转点盘点

`seers_harness/domain/models.py` 共 9 处 `model_config`：

| 行号 | Model | 当前 |
|---|---|---|
| 20 | `EvidenceRef` | `{"extra": "ignore"}` |
| 35 | `PersonalizationFactor` | `{"extra": "ignore"}` |
| 54 | `BridgeLogic` | `{"extra": "ignore"}` |
| 70 | `CopyCandidate` | `{"extra": "ignore"}` |
| 91 | `PerAxisVerdict` | `{"extra": "ignore"}` |
| 109 | `PersonalizedCopyRubricJudgment` | `{"extra": "ignore"}` |
| 114 | `FactorDiscoveryArtifact` | `{"extra": "ignore"}` |
| 119 | `CopyGenerationArtifact` | `{"extra": "ignore"}` |
| 124 | `PersonalizedCopyRubricArtifact` | `{"extra": "ignore"}` |

D-07 要求 9 处全部翻 `forbid`。文件头 docstring（第 3 行）说 "legacy c14/c15
JSON on disk decodes silently" —— 与翻转语义相反，必须改写。

D-15 给出 commit slicing 自由度：单次机械 commit 或按 model 切。研究阶段
建议**单次机械 commit + 完整 122-test 跑一次**。若 122 全绿，单 commit
落地；若有红，把红 fixture 改完后仍一次 commit（不切到 9 个）。

## 5. REGRESS-01 负面扫除

`seers_harness/` 顶层包：`agentic / core / domain / intake / provider_runtime
/ tools / workflow`。

**不存在**子模块名：`storage / assets / evaluation / gates / cli`。

D-05 负面扫除直接通过。无对应代码改动。

## 6. Smoke link 入口与多节点 driver

**D-09 / D-12 要求**：`data_100k.csv → intake → tool_loop → DAG → stable
artifact`，20 请求，每请求产出通过 `extra="forbid"` schema 校验的最终 artifact。

**现状**：

- `WorkflowRuntime._run_node(node, scenario)` 已存在（dag_runner.py:59-116），
  每次跑一个 node attempt。
- 没有顶层 `run_request(scenario, nodes)` 把多 node 串联，把上一个 node 的
  artifact 注入 `dependency_payloads`。
- `provider_payload_for_node` 已经按 node_id 接 `dependency_payloads` 字典
  （factor → 无依赖；copy → factor_discovery；rubric → copy_generation），
  上游产物只差一个 driver 去填。
- `ScriptedProvider` 已存在（`tests/fakes/scripted_provider.py`），smoke 用
  它做 provider，不接真 LLM。

**裁决（Q3/A1）**：在 `dag_runner.py` 加一个 `run_request(scenario, nodes)`
公开方法，按 nodes 列表顺序调用 `_run_node`，把每个 node 的 artifact
（从落盘 JSON 反序列化）按 node_id 累积进 `dependency_payloads`，再传给下一个
node 的 `provider_payload_for_node`。20 请求 = 20 次 `run_request`，每次产
3 个 artifact（factor / copy / rubric）。**D-12 的"20 个最终 artifact"以
rubric 节点产物计**。

**Smoke 入口位置（D-14 自由度）**：建议落 `tests/smoke/test_e2e_smoke.py`，
pytest marker = `smoke`，默认在 `pytest -q` 里跑（不分目录排除）。理由：

- 122-test 基线已经包含集成测试，smoke 加入后仍是单一 pytest 入口。
- ScriptedProvider 是 hermetic 测试 double，smoke 不需要 IO/网络隔离。
- 不引入新 Makefile target / 新 runner，diff 最小。

**Smoke 必须断言**：

1. 20 个 `request_id` 从 `data_100k.csv` 选出（取前 20 个唯一
   `request_id`，按文件顺序）。
2. 每个 request 经 `preprocess_request_from_csv` → 3 节点 `run_request` →
   产出 3 个 artifact。
3. 每个 artifact 通过对应 `extra="forbid"` 的 `model_validate`，**零
   ValidationError**。
4. 20 × 3 = 60 个 artifact 全部落盘成 JSON，路径符合
   `<output_dir>/<node_id>-<session_id>.json`。
5. 单线程、sequential、stdout only（D-11）。

**ScriptedProvider 脚本**：每节点最少 2 turns（1 个 record_* + 1 个
submit_*_final）。`record_candidate` runtime 校验需要 candidate text 不含
fixture 里 `recent_search_cat3_30d` 的 token，因此脚本里的 candidate text
必须用通用文案（不复用 fixture 词）。

## 7. 既有测试基线

`uv run --python 3.12 --extra dev python -m pytest -q` 当前 122/122 通过
（STATE.md 记录的 verified baseline）。D-07 翻 `forbid` 时这是回归基线；
smoke 链路加入后基线变为 123+/123+（具体增量看 smoke 拆分粒度，PLAN 写）。

## 8. 三项 Q&A 决议汇总

| Q | 决议 |
|---|---|
| Q1 / 修订 D-04 | lint 表是"反举例"抽样，不是禁词表；不推广为工程级 grep 门；不动业务数据 / runtime 测试 / docs 真实类目段落；执行点是 `record_candidate` runtime 校验 |
| Q2 / 修订 D-06 | 删除 `rubric_payload_for` 的 `hard_check_artifact` 参数与过滤分支 + `dag_runner.py:183` 同步删 |
| Q3 / D-12 落地形式 | `dag_runner.py` 加 `run_request(scenario, nodes)` 公开方法；smoke 跑 3 节点串联；最终 artifact = rubric 节点产物，每请求 3 个 artifact 全部 forbid 校验 |

---

*Research artifacts referenced by plans 05-01 / 05-02 / 05-03 / 05-04 below.*
