# Requirements: SEERS Harness Workspace

Defined 2026-05-25. This file is the compact traceability surface. Detailed
decision text lives in `intel/decisions.md`; implementation evidence lives in
phase summaries and tests.

## Status Legend

- Complete: implemented and covered by the current 122-test baseline.
- Pending: planned but not yet implemented in the flattened workspace.
- Deferred: intentionally out of this release path.

## Validated Provider Facts

| ID | Requirement | Status |
|---|---|---|
| PROBE-01 | DeepSeek `/beta` strict tools are compatible with thinking mode; ADR-PROBE-7.1.1 supersedes the earlier `high` probe and locks `deepseek-v4-pro` + `reasoning_effort=max`. | Complete |

## Phase 1: Schema + Tools Foundation

| ID | Requirement | Status |
|---|---|---|
| DATA-01 | `PersonalizationFactor` has required `transferable_disposition`. | Complete |
| DATA-02 | C16 STOP-GATE residue fields are deleted from factor schema. | Complete |
| DATA-03 | `BridgeLogic` keeps `product_anchor`/`relation_anchor` and drops C15 compatibility slots. | Complete |
| DATA-04 | `CopyCandidate` has `considered_drafts` and `chosen_draft_index`; selected text must match. | Complete |
| DATA-05 | Rubric judgment uses seven binary axes with critique-before-verdict structure. | Complete |
| DATA-06 | No schema contains self-rated metric fields. | Complete |
| TOOL-01 | `record_factor` records factors and resolves evidence paths. | Complete |
| TOOL-02 | `submit_factors_final` validates and finalizes factor artifacts. | Complete |
| TOOL-03 | `record_candidate` enforces draft selection, structural numeric checks, length, anchors, and dynamic user-history token rejection. | Complete |
| TOOL-04 | `submit_copies_final` validates and finalizes copy artifacts. | Complete |
| TOOL-05 | `judge_candidate` validates literal candidate quotes and rubric axis args. | Complete |
| TOOL-06 | `submit_judgments_final` validates and finalizes judgment artifacts. | Complete |
| TOOL-07 | `reflect_on_coverage` returns fixed mirror questions. | Complete |
| TOOL-08 | `reflect_on_diversity` returns fixed mirror questions. | Complete |
| TOOL-09 | Every current handler is classified as hand or mirror; no eye tool exists yet. | Complete |
| TOOL-10 | `TOOLS_SPEC` and `TOOL_HANDLERS` registries exist; static domain lexicons are absent. | Complete |

## Phase 2: Single Provider Path

| ID | Requirement | Status |
|---|---|---|
| PROV-01 | Provider exposes `generate_with_tools`; `generate_json` is gone. | Complete |
| PROV-02 | No `response_format`; schema enforcement happens through tool args. | Complete |
| PROV-03 | Provider call shape uses the locked DeepSeek tool/thinking config. | Complete |
| PROV-04 | Provider exceptions classify into rate-limit, transient, auth, or reraised errors. | Complete |
| PROV-05 | `ProviderResult` carries parsed `tool_calls` and raw tool-call payloads. | Complete |
| PROV-06 | Provider file stays within the agreed line budget. | Complete |

## Phase 3: Tool Loop + DAG Integration

| ID | Requirement | Status |
|---|---|---|
| LOOP-01 | `agentic/tool_loop.py` exposes `run_skill_via_tools`. | Complete |
| LOOP-02 | Loop starts with system skill bundle + user payload and appends tool results in order. | Complete |
| LOOP-03 | Failure routing handles validation errors, unknown tools, stops without submit, caps, and transient retries. | Complete |
| LOOP-04 | Tool-loop file stays within line budget. | Complete |
| LOOP-05 | `dag_runner._run_node` delegates to the tool loop and validates final artifacts with Pydantic. | Complete |
| LOOP-06 | Payload quota fields are removed; `candidate_generation_policy` remains. | Complete |

## Phase 4: SKILL.md Rewrites

| ID | Requirement | Status |
|---|---|---|
| SKILL-01 | Rewrite factor-discovery SKILL with transferable-disposition methodology. | Pending |
| SKILL-02 | Rewrite copy-generation SKILL with user-history token ban as transferable principle. | Pending |
| SKILL-03 | Rewrite rubric-judge SKILL with binary critique-before-verdict judgment. | Pending |
| SKILL-04 | All three SKILL files avoid numeric thresholds, internal examples, enumerations, and JSON-only framing. | Pending |

## Phase 5: Cleanup, Deletes, Tests, Regression

| ID | Requirement | Status |
|---|---|---|
| CLEAN-01 | Align or remove old invariant checks that reference deleted quota fields. | Pending |
| CLEAN-02 | Delete retired check/polling files and tests. | Pending |
| CLEAN-03 | Decide whether old hard-check gates survive or are absorbed by handlers/rubric. | Pending |
| CLEAN-04 | Keep only useful historical notes under `docs/`; no live old research paths. | Pending |
| TEST-01 | FakeProvider scripts tool-call sequences. | Complete |
| TEST-02 | Per-handler unit tests exist. | Complete |
| TEST-03 | Reflect fixed-string tests exist. | Complete |
| TEST-04 | Tool-loop behavior tests exist. | Complete |
| TEST-05 | Provider tool-path tests exist. | Complete |
| TEST-06 | DAG integration test exists. | Complete |
| REGRESS-01 | Storage/assets/evaluation/gates/CLI regression sweep. | Pending |

## Phase 6: Evolution + Production Hardening

| ID | Requirement | Status |
|---|---|---|
| EVO-01 | Delete evolution skills that ask an LLM to judge champion bundles or select probes. | Complete (06-01-SUMMARY.md) |
| EVO-02 | Rewrite `distill-skill-deltas` as a tool-use skill with matching handlers. | Complete (06-01-SUMMARY.md) |
| EVO-03 | Audit `promote-skill-patch` and keep only deterministic action. | Complete (06-05-SUMMARY.md) |
| EVO-04 | Rename and implement scenario-based evolution cadence. | Complete (06-02-SUMMARY.md) |
| EVO-05 | Write reference v2 schema design only; do not emit v2 yet. | Complete (06-01-SUMMARY.md) |
| EVO-06 | Audit evolution field names against current schema. | Complete (06-01-SUMMARY.md) |
| PROD-01 | Stress concurrency 20 with realistic FakeProvider latency. | Complete (06-03-SUMMARY.md) |
| PROD-02 | Verify current DeepSeek rate-limit assumptions before tuning limits. | Complete (06-04-SUMMARY.md) |
| TERM-01 | Add terminal progress display for long runs. | Complete (06-04-SUMMARY.md) |
| TERM-02 | Add CI-safe `--no-progress`/plain-output behavior. | Complete (06-04-SUMMARY.md) |
| PROMOTE-01 | Smoke promotion-chain public entry points against current fixtures. | Complete (06-05-SUMMARY.md) |

## Phase 7: Real-LLM Validation

| ID | Requirement | Status |
|---|---|---|
| VAL-01 | Run 20 real DeepSeek scenarios from `.env.local`. | Pending |
| VAL-02 | Every scenario emits at least one tool call. | Pending |
| VAL-03 | Reflection tools are reachable in real runs. | Pending |
| VAL-04 | Candidate text has zero user-history token, Arabic digit, or state-label leakage. | Pending |
| VAL-05 | Case-reading confirms transferable factors. | Pending |
| VAL-06 | Evolution reflow fires according to scenario cadence. | Pending |

## Cross-Phase Process

| ID | Requirement | Status |
|---|---|---|
| PROC-01 | Execute in atomic order: schema/tools/provider/loop/DAG/SKILL/cleanup/tests/real validation. | In progress |
| PROC-02 | Each phase plan names the skills or methods it relies on. | In progress |

## Out Of Scope

Do not reintroduce `generate_json`, C14/C15 bridge slots, LLM self-rated fields,
static handler lexicons, numeric SKILL thresholds, internal examples, hook/SDK
changes, roleplay/click-rate validation, or reference-v2 emitter implementation.
