---
phase: 05-cleanup-deletes-tests-regression
status: complete
---

# Phase 5 Summary: Cleanup, Deletes, Tests, Regression

## Goal

Strip historical c14/c15/c16 lineage tags from prose, delete the residual
hard-check gate path, tighten every domain model with `extra="forbid"`, and
stand up an end-to-end smoke link `data_100k.csv → preprocess → run_request →
3 forbid-schema artifacts` over 20 requests with `ScriptedProvider` —
single-threaded, stdout-only, no concurrency / progress UX (Phase 6).

## Outputs

| Plan | Wave | Scope | Status |
|---|---|---|---|
| 05-01 | 1 | c14/c15/c16/`verbatim from c` cleanup across 10 files (5 prose docstrings + 5 test renames) | Complete |
| 05-02 | 1 | Delete `hard_check_artifact` parameter + filter branch from `rubric_payload_for`; defensive grep + new `test_no_hard_check_gate_residue` | Complete |
| 05-03 | 2 | Flip 9 `model_config = {"extra": "ignore"}` → `{"extra": "forbid"}`; new `test_all_models_forbid_extra` audit | Complete |
| 05-04 | 3 | Add `WorkflowRuntime.run_request` driver; 20-request E2E smoke (`tests/smoke/test_e2e_smoke.py`) with `ScriptedProvider` | Complete |

## Requirement Coverage

- **CLEAN-01** — `rg 'c14|c15|c16|verbatim from c' seers_harness/ tests/`
  returns 0 hits. Test renames preserve assertion bodies (5 functions
  renamed: `test_c16_pair_present` → `test_anchor_pair_present`,
  `test_c15_slots_absent` → `test_legacy_bridge_slots_absent`,
  `test_c15_legacy_fields_absent` → `test_legacy_plain_text_fields_absent`,
  `test_c15_legacy_aggregate_fields_absent` → `test_legacy_aggregate_fields_absent`,
  `test_legacy_rubric_fields_absent` → `test_legacy_aggregate_fields_absent`).
- **CLEAN-02** — `WorkflowRuntime.run_request` driver lands in
  `dag_runner.py`; smoke test exercises 20 × 3 = 60 forbid-schema artifacts
  in <1s wall time using `ScriptedProvider` (no real LLM, hermetic).
- **CLEAN-03** — `rg 'hard_check' seers_harness/` returns 0 hits.
  `rubric_payload_for` signature reduced to `(*, scenario, copy_artifact)`;
  `provider_payload_for_node` rubric branch no longer threads `hard_check`.
  New audit test `test_no_hard_check_gate_residue` walks `seers_harness/*.py`
  and asserts the token never reappears.
- **CLEAN-04** — Smoke link `data_100k.csv → preprocess_request_from_csv →
  WorkflowRuntime.run_request` is end-to-end green; 60 unique paths, every
  artifact passes `model_validate` with `extra="forbid"` schemas.
- **DATA-06** — All 9 BaseModels in `seers_harness/domain/models.py` declare
  `model_config = {"extra": "forbid"}`. `extra="ignore"` count across the
  entire `seers_harness/` tree is 0. New audit test
  `test_all_models_forbid_extra` iterates models via `inspect.getmembers`
  to prevent drift.
- **REGRESS-01** — Negative scan: `seers_harness/` top-level packages =
  `agentic / core / domain / intake / provider_runtime / tools / workflow`.
  No `storage / assets / evaluation / gates / cli` submodules exist. No
  code changes were required.

## Smoke Link

`tests/smoke/test_e2e_smoke.py::test_e2e_smoke_20_requests` builds a tiny
scratch CSV from the first ~1000 rows of `data_100k.csv` (sampling 20
unique `request_id` values), then drives each request through:

1. `preprocess_request_from_csv(scratch_csv, request_id=...)` → scenario dict
2. `build_full_chain_script()` → fresh `ScriptedProvider` (3 nodes × 2
   turns: `record_*` + `submit_*_final`)
3. `WorkflowRuntime` with `output_dir = tmp_path / request_id`
4. `runtime.run_request(scenario=..., nodes=make_nodes())` →
   `dict[node_id, Path]`

Assertions per request: 3 paths returned, each file exists/non-empty,
each artifact loads via `FactorDiscoveryArtifact.model_validate` /
`CopyGenerationArtifact.model_validate` /
`PersonalizedCopyRubricArtifact.model_validate` with zero `ValidationError`.
Aggregate: 60 unique paths, no collisions.

The single-pass scratch-CSV trick was added during 05-04 task iteration
because `preprocess_request_from_csv` streams the entire 2.3 GB
`data_100k.csv` per call, and 20 full-file scans broke the `<60s` wall-time
budget. The fix: read the first ~1000 raw lines once, capture both the
20 request-ids and their literal CSV lines, write a small scratch CSV
inside `tmp_path`, point all 20 preprocess calls at the scratch file.
Smoke runs in 0.55s.

## ScriptedProvider Script Shape

`build_full_chain_script()` reuses one canonical sequence per smoke
request (smoke verifies wiring, not LLM creativity):

- **factor_discovery** — turn 1: `record_factor` (one factor with
  `evidence_refs` referencing real fixture paths); turn 2:
  `submit_factors_final`
- **copy_generation** — turn 1: `record_candidate` (one candidate per
  product, generic non-leakage text `"探索新选择伴你温柔时光"`); turn 2:
  `submit_copies_final`
- **personalized_copy_rubric** — turn 1: `judge_candidate` (one judgment
  per candidate with full `per_axis` list of 7 binary `PerAxisVerdict`);
  turn 2: `submit_judgments_final`

Token-leak avoidance: candidate text is generic, and `copy_payload_for`
omits `user_state` per master_plan §4.5, so the runtime leak set is
empty by construction.

## Pytest

`uv run --python 3.12 --extra dev python -m pytest -q` from `workspace/`:
**125 passed in 0.77s** — 122 baseline + 3 new audit tests + 1 smoke test
(but `test_no_hard_check_gate_residue` was already in the working tree
when 05-01 ran in parallel with 05-02, so the linear arithmetic is
122 + 1 (hard_check audit) + 1 (forbid audit) + 1 (smoke) = 125).

Smoke wall time: **0.55s** (budget: <60s).

## Verification Gates

All six Phase 5 close-out gates pass:

| Gate | Result |
|---|---|
| `rg 'c14\|c15\|c16\|verbatim from c\|hard_check' seers_harness/` | 0 hits |
| `rg '"extra":\s*"ignore"' seers_harness/` | 0 hits |
| `rg '"extra":\s*"forbid"' seers_harness/domain/models.py` | 9 hits |
| Top-level `seers_harness/` lacks `storage / assets / evaluation / gates / cli` | confirmed absent |
| `pytest -q` | 125 passed |
| Smoke wall time | 0.55s < 60s |

## What Changed vs. Stayed Fixed

Changed in this phase:

- `seers_harness/domain/models.py` — 9 `model_config` flipped to forbid;
  file-level docstring rewritten to current-schema framing.
- `seers_harness/workflow/payloads.py` — `rubric_payload_for` signature
  simplified; file-level docstring rewritten.
- `seers_harness/workflow/dag_runner.py` — `run_request` public method
  added; `_run_node` accepts `dependency_payloads` kwarg (default `{}`);
  file-level + `NodeSpec` docstrings rewritten.
- `seers_harness/provider_runtime/base.py` — c16 prose framing replaced
  with current PROV-01 invariant.
- `seers_harness/tools/skill_tools.py` — banner replaced with helper
  purpose statement.
- 6 test files prose-rewritten or function-renamed; assertion bodies
  preserved (no test added or removed by 05-01).
- `tests/test_payloads_loop06_audit.py` — appended
  `test_no_hard_check_gate_residue`.
- `tests/test_models_no_self_rated_fields.py` — appended
  `test_all_models_forbid_extra`.
- `tests/smoke/__init__.py`, `tests/smoke/scripted_full_chain.py`,
  `tests/smoke/test_e2e_smoke.py` — new, 1 smoke test function.

Stayed fixed:

- Field definitions, `field_validator` and `model_validator` bodies of
  `domain/models.py` — zero diff outside the 9 `model_config` flips and
  the docstring rewrite.
- `tools/skill_tools.py` runtime token-leakage validation
  (`record_candidate` rejecting fixture user-history tokens) — that is
  the real execution point per the rewritten D-04, and it stays exactly
  as Phase 1 left it.
- `intake/categories.py` `TARGET_CATEGORIES` — real business data,
  untouched.
- `harness-runtime/` — promotion decision deferred (not in CLEAN-01..04
  scope).
- `workspace/workflow-skills/current/` SKILL.md prose lint — stays at
  Phase 4 status; no engineering-level grep gate added.

## Handoff to Phase 6

Phase 6 owns:

- DeepSeek concurrency / asyncio / progress UX (`--no-progress`,
  rich/tqdm) — explicitly excluded from Phase 5 by D-11.
- INFO/DEBUG log routing — also D-11 deferred.
- Reference v2 emitter design.
- Evolution skill alignment with tool-use principles.
- `harness-runtime/workflow-skills/` reconciliation against
  `workspace/workflow-skills/current/` (runtime currently lacks
  `personalized-copy-rubric-judge/SKILL.md`).
