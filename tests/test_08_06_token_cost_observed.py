from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from seers_harness.agentic.tool_loop import run_skill_via_tools
from seers_harness.evolution.trial_runner import run_request_trial
from seers_harness.provider_runtime.base import ProviderResult
from seers_harness.workflow import dag_runner
from seers_harness.workflow.dag_runner import NodeSpec, WorkflowRuntime


class _Artifact(BaseModel):
    ok: bool


class _UsageProvider:
    def __init__(self, usages: list[dict[str, Any]]) -> None:
        self.usages = list(usages)
        self.calls = 0

    def generate_with_tools(self, *, node_id, skill_bundle, messages, tools):
        usage = self.usages[self.calls]
        self.calls += 1
        tool_name = "submit_final" if self.calls == len(self.usages) else "observe"
        arguments = {"ok": True} if tool_name == "submit_final" else {}
        return ProviderResult(
            usage=usage,
            tool_calls=[{"id": f"c{self.calls}", "name": tool_name, "arguments": arguments}],
            raw_response_text="",
            raw_tool_calls=[],
            reasoning_content="R",
        )


def _handlers() -> dict:
    def observe(args: dict, state: dict) -> str:
        return "observed"

    def submit_final(args: dict, state: dict) -> str:
        state["final_artifact"] = args
        return "finalized"

    return {"observe": observe, "submit_final": submit_final}


def _live_skill_root(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("skill", encoding="utf-8")
    return path


def test_tool_loop_result_aggregates_usage_across_turns() -> None:
    result = run_skill_via_tools(
        skill_name="test",
        skill_bundle="SKILL",
        payload={},
        tools_spec=[],
        tool_handlers=_handlers(),
        provider=_UsageProvider(
            [
                {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                {"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 18},
            ]
        ),
        node_id="n",
    )

    assert result.usage == {
        "prompt_tokens": 17,
        "completion_tokens": 31,
        "total_tokens": 48,
    }


def _register_test_skill(monkeypatch) -> None:
    monkeypatch.setitem(dag_runner.TOOLS_SPEC, "test", [])
    monkeypatch.setitem(dag_runner.TOOL_HANDLERS, "observe", _handlers()["observe"])
    monkeypatch.setitem(dag_runner.TOOL_HANDLERS, "submit_final", _handlers()["submit_final"])
    # Plan 08-G1: dag_runner now resolves ``skill_bundle`` through
    # ``load_skill_prose`` (instead of the old "SKILL_BODY" literal). The
    # synthetic ``skill_name="test"`` used by these tests has no SKILL.md on
    # disk, so we stub the loader symbol that dag_runner imported into its
    # namespace. The token-cost behavior under test is orthogonal to SKILL
    # prose contents, so any non-empty stub is fine.
    monkeypatch.setattr(
        dag_runner,
        "load_skill_prose",
        lambda skill_name: "STUB_SKILL_PROSE_FOR_TESTS",
    )


def test_workflow_runtime_trace_carries_tool_loop_usage(monkeypatch, tmp_path: Path) -> None:
    _register_test_skill(monkeypatch)
    runtime = WorkflowRuntime(
        provider=_UsageProvider([{"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}]),
        output_dir=tmp_path,
    )
    node = NodeSpec(id="node", skill_name="test", output_model=_Artifact)

    runtime._run_node(node=node, scenario={})

    summary = next(ev for ev in runtime.trace if ev.get("type") == "tool_loop_summary")
    assert summary["usage"] == {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
    }


def test_trial_outcome_token_cost_from_runtime_trace_usage(monkeypatch, tmp_path: Path) -> None:
    _register_test_skill(monkeypatch)
    runtime = WorkflowRuntime(
        provider=_UsageProvider([{"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 123}]),
        output_dir=tmp_path / "artifacts",
    )
    node = NodeSpec(id="node", skill_name="test", output_model=_Artifact)

    outcome = run_request_trial(
        runtime=runtime,
        scenario={},
        nodes=[node],
        live_skill_root=_live_skill_root(tmp_path / "live"),
        workspace_dir=tmp_path / "workspace",
        patch=None,
    )

    assert outcome.success is True
    assert outcome.tool_call_count == 1
    assert outcome.token_cost_observed == 123


def test_trial_outcome_token_cost_zero_when_no_usage(tmp_path: Path) -> None:
    class _TraceRuntime:
        trace = [
            {"type": "tool_loop_summary", "tool_calls_made": 1},
            {"type": "tool_loop_summary", "tool_calls_made": 2, "usage": None},
            {"type": "provider_call", "usage": {"total_tokens": 999}},
        ]

        def run_request(self, *, scenario, nodes):
            return {}

    outcome = run_request_trial(
        runtime=_TraceRuntime(),
        scenario={},
        nodes=[],
        live_skill_root=_live_skill_root(tmp_path / "live"),
        workspace_dir=tmp_path / "workspace",
        patch=None,
    )

    assert outcome.success is True
    assert outcome.tool_call_count == 3
    assert outcome.token_cost_observed == 0
