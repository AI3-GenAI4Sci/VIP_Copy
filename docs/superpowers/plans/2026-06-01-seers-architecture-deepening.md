# SEERS Architecture Deepening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the main `seers_harness` Modules without changing harness behavior.

**Architecture:** Add focused Modules for artifact state, node attempts, provider capture records, validation stage dashboarding, and request evidence normalization. Existing callers keep their public behavior while moving implementation details behind narrower Interfaces.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest.

---

### Task 1: Artifact State Module

**Files:**
- Create: `seers_harness/tools/artifact_state.py`
- Modify: `seers_harness/tools/skill_tools.py`
- Test: `tests/test_artifact_state.py`

- [x] Write tests that call artifact state functions directly for user factors, candidates, and judgments.
- [x] Run `python -m pytest tests/test_artifact_state.py -q` and verify import failure.
- [x] Move artifact mutation and validation helpers from `skill_tools.py` into `artifact_state.py`.
- [x] Keep `skill_tools.py` as the tool registry and handler Adapter.
- [x] Run `python -m pytest tests/test_artifact_state.py tests/test_skill_tools_record_candidate.py tests/test_skill_tools_registry.py -q`.

### Task 2: Node Attempt Module

**Files:**
- Create: `seers_harness/workflow/node_attempt.py`
- Modify: `seers_harness/workflow/dag_runner.py`
- Test: `tests/test_node_attempt.py`

- [x] Write tests for success and business-output retry metadata through a node-attempt runner.
- [x] Run `python -m pytest tests/test_node_attempt.py -q` and verify import failure.
- [x] Move one-attempt execution helpers from `WorkflowRuntime._run_node` into `node_attempt.py`.
- [x] Keep `WorkflowRuntime` responsible for retry policy and request DAG order.
- [x] Run `python -m pytest tests/test_node_attempt.py tests/test_dag_runner_integration.py -q`.

### Task 3: Provider Capture Module

**Files:**
- Create: `seers_harness/provider_runtime/capture.py`
- Modify: `seers_harness/validation/recording_provider.py`
- Test: `tests/test_provider_capture.py`

- [x] Write tests for turning a provider call into a capture record.
- [x] Run `python -m pytest tests/test_provider_capture.py -q` and verify import failure.
- [x] Move response serialization and usage attachment into `capture.py`.
- [x] Keep `RecordingProvider` as the Adapter that delegates and appends records.
- [x] Run `python -m pytest tests/test_provider_capture.py tests/test_trajectory_evidence.py -q`.

### Task 4: Validation Stage Dashboard Module

**Files:**
- Create: `seers_harness/validation/stage_dashboard.py`
- Modify: `seers_harness/validation/runner.py`
- Test: `tests/test_stage_dashboard.py`

- [x] Write tests for request start, node event, completion, and failure output through the dashboard Interface.
- [x] Run `python -m pytest tests/test_stage_dashboard.py -q` and verify import failure.
- [x] Move `_BatchDashboard` and elapsed formatting helpers out of `runner.py`.
- [x] Keep `runner.py` focused on stage control.
- [x] Run `python -m pytest tests/test_stage_dashboard.py tests/test_validation_runner.py -q`.

### Task 5: Request Evidence Module

**Files:**
- Create: `seers_harness/validation/request_evidence.py`
- Modify: `seers_harness/validation/evidence_writer.py`
- Test: `tests/test_request_evidence.py`

- [x] Write tests for normalized request evidence grouping, artifact fallback, and usage aggregation.
- [x] Run `python -m pytest tests/test_request_evidence.py -q` and verify import failure.
- [x] Move grouping, artifact resolution, and usage aggregation into `request_evidence.py`.
- [x] Keep `evidence_writer.py` focused on filesystem writes.
- [x] Run `python -m pytest tests/test_request_evidence.py tests/test_evidence_writer.py tests/test_index_writer.py -q`.

### Final Verification

- [x] Run targeted architecture tests listed above.
- [x] Run `python -m pytest -q`.
- [x] Review `git diff --stat` and confirm changes are structure-only.
