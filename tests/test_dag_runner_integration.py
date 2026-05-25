"""LOOP-05 end-to-end — WorkflowRuntime._run_node + tool_loop + ScriptedProvider.

Two integration assertions per Plan 03-03:
  Test A — happy path: _run_node returns a Pydantic-validated artifact via the
           tool_loop, and the trace stream carries the renamed event
           ``tool_loop_summary`` (NOT the c16 ``agent_loop_summary``).
  Test B — outer retry shell: when the inner ``max_transient_retries_per_turn=2``
           budget exhausts on attempt 1, the outer ``node.max_attempts=2`` shell
           retries on attempt 2 and the artifact still materializes. Pins
           RESEARCH §8 pitfall #4 — inner loop budget and outer retry shell
           are TWO DISTINCT budgets, not one.

These tests are RED at write time: ``seers_harness.workflow.dag_runner`` does
not yet exist. ``pytest.importorskip`` flips them from skipped to active when
Task 3 lands the module.
"""

from __future__ import annotations

import json

import pytest

from seers_harness.core.errors import ProviderTransientError
from seers_harness.domain.models import FactorDiscoveryArtifact

from tests.fakes.scripted_provider import ScriptedProvider, ScriptedTurn

# Skip the whole module while Plan 03-03 Task 3 has not landed dag_runner.py.
# When Task 3 lands the import resolves and these tests activate.
dag_runner_mod = pytest.importorskip(
    "seers_harness.workflow.dag_runner",
    reason="lands in Plan 03-03 Task 3 — module not yet present",
)
WorkflowRuntime = dag_runner_mod.WorkflowRuntime
NodeSpec = dag_runner_mod.NodeSpec


_SCENARIO = {
    "scenario_id": "S-001",
    "request_id": "R-001",
    "user_state": {
        "behavior": {
            "recent_search_cat3_30d": "维生素,面膜,精华液",
            "user_top_brand_30d": "雅诗兰黛,资生堂",
        }
    },
    "products": [{"product_id": "P-001", "group_key": "防晒"}],
}


_FACTOR_ARGS = {
    "factor_id": "F-1",
    "user_side_signal": "recent skincare search",
    "direction": "user_to_need",
    "evidence_paths": ["user_state.behavior.recent_search_cat3_30d"],
    "bridge_to_product": "skincare interest aligns with product",
    "transferable_disposition": "skincare-curious",
    "covers_product_ids": ["P-001"],
}


_SUBMIT_ARGS = {
    "factors": [
        {
            "factor_id": "F-1",
            "user_side_signal": "recent skincare search",
            "direction": "user_to_need",
            "transferable_disposition": "skincare-curious",
            "evidence_refs": [
                {"path": "user_state.behavior.recent_search_cat3_30d", "value": "x"}
            ],
            "bridge": "skincare interest aligns with product",
            "covers_product_ids": ["P-001"],
        }
    ]
}


def _happy_turn() -> ScriptedTurn:
    return ScriptedTurn(
        tool_calls=[
            {"id": "c1", "name": "record_factor", "arguments": _FACTOR_ARGS},
            {"id": "c2", "name": "submit_factors_final", "arguments": _SUBMIT_ARGS},
        ],
        raw_tool_calls=[],
        finish_reason="tool_calls",
        reasoning_content="R" * 30,
    )


def _factor_node() -> NodeSpec:
    return NodeSpec(
        id="factor_discovery",
        skill_name="discover-personalization-factors",
        output_model=FactorDiscoveryArtifact,
        max_attempts=1,
    )


def test_run_node_factor_discovery_happy_path_returns_validated_artifact(tmp_path):
    """LOOP-05 — _run_node ⇒ run_skill_via_tools ⇒ model_validate(result.artifact).

    Pins:
      - returned path exists and re-loads to a valid FactorDiscoveryArtifact
      - trace stream carries the renamed event ``tool_loop_summary`` with
        turns_used=1, tool_calls_made=2, last_reasoning_content='R'*30
      - trace stream does NOT contain the c16 event name ``agent_loop_summary``
    """
    scripted = ScriptedProvider(script=[_happy_turn()])
    runtime = WorkflowRuntime(provider=scripted, output_dir=tmp_path)

    output_path = runtime._run_node(node=_factor_node(), scenario=_SCENARIO)

    # The artifact materializes on disk and re-validates as the same model_type.
    raw = json.loads(output_path.read_text(encoding="utf-8"))
    artifact = FactorDiscoveryArtifact.model_validate(raw)
    assert len(artifact.factors) == 1
    assert artifact.factors[0].factor_id == "F-1"
    assert artifact.factors[0].transferable_disposition == "skincare-curious"

    # Trace event rename is the load-bearing pin (RESEARCH §4 REWRITE row).
    types = [evt.get("type") for evt in runtime.trace]
    assert "tool_loop_summary" in types, (
        f"expected renamed event 'tool_loop_summary' in trace, got: {types}"
    )
    assert "agent_loop_summary" not in types, (
        f"c16 event name 'agent_loop_summary' must be deleted, found: {types}"
    )
    summary = next(e for e in runtime.trace if e.get("type") == "tool_loop_summary")
    assert summary["turns_used"] == 1
    assert summary["tool_calls_made"] == 2
    assert summary["last_reasoning_content"] == "R" * 30


def test_run_node_outer_retry_shell_kicks_in_when_inner_transient_budget_exhausts(tmp_path):
    """RESEARCH §8 pitfall #4 — outer node.max_attempts and inner
    max_transient_retries_per_turn are two distinct budgets.

    Walk-through with max_transient_retries_per_turn=2 (loop default) and
    node.max_attempts=2:
      Outer attempt 1 → inner pulls turn 0 (transient), turn 1 (transient),
                        turn 2 (transient) ⇒ inner budget exhausted, raises
                        ProviderTransientError ⇒ outer records FAILED,
                        classified retryable, continues.
      Outer attempt 2 → inner pulls turn 3 (happy) ⇒ artifact returned.
    """
    transient = ScriptedTurn(raise_exc=ProviderTransientError("simulated 503"))
    scripted = ScriptedProvider(script=[transient, transient, transient, _happy_turn()])
    runtime = WorkflowRuntime(provider=scripted, output_dir=tmp_path)

    node = NodeSpec(
        id="factor_discovery",
        skill_name="discover-personalization-factors",
        output_model=FactorDiscoveryArtifact,
        max_attempts=2,
    )

    output_path = runtime._run_node(node=node, scenario=_SCENARIO)

    raw = json.loads(output_path.read_text(encoding="utf-8"))
    artifact = FactorDiscoveryArtifact.model_validate(raw)
    assert len(artifact.factors) == 1
    assert artifact.factors[0].factor_id == "F-1"

    # Outer retry-shell evidence: 2 RUNNING, 1 FAILED (attempt 1), 1 SUCCEEDED (attempt 2).
    statuses = [r.get("status") for r in runtime.records if r.get("node_id") == node.id]
    assert statuses.count("RUNNING") == 2, f"expected 2 RUNNING records, got: {statuses}"
    assert statuses.count("FAILED") == 1, f"expected 1 FAILED record, got: {statuses}"
    assert statuses.count("SUCCEEDED") == 1, f"expected 1 SUCCEEDED record, got: {statuses}"

    # FAILED record should classify the transient error as retryable.
    failed = next(r for r in runtime.records if r.get("status") == "FAILED")
    assert failed.get("error_category") == "transient_provider"
