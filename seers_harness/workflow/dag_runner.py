"""WorkflowRuntime — invokes the tool-use loop per node attempt (LOOP-05).

Per master_plan §4.4 and RESEARCH §4 KEEP/DELETE/REWRITE table, ``_run_node``
collapses to one ``run_skill_via_tools(...)`` call followed by
``model_type.model_validate(result.artifact)``. Each node attempt is a single
tool-loop invocation plus pydantic validation; the trace event is
``tool_loop_summary`` with fields {turns_used, tool_calls_made,
last_reasoning_content, usage}. See RESEARCH §4 + §8 for the table and pitfalls.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from seers_harness.core.errors import classify_exception
from seers_harness.tools.skill_tools import TOOL_HANDLERS, TOOLS_SPEC
from seers_harness.workflow.node_attempt import NodeAttemptConfig, run_node_attempt
from seers_harness.workflow.progress import CliReporter
from seers_harness.workflow.skill_loader import load_skill_prose


@dataclass
class NodeSpec:
    """Minimum-viable per-node contract.

    Each NodeSpec declares four fields: ``id`` (node identifier in the DAG
    trace), ``skill_name`` (which skill the tool loop runs), ``output_model``
    (the pydantic model that validates the artifact), and ``max_attempts``
    (retry budget). The runtime takes a single provider in its ctor, so
    NodeSpec carries no provider/temperature/skill_registry routing.
    """
    id: str
    skill_name: str
    output_model: type[BaseModel]
    max_attempts: int = 1


@dataclass
class WorkflowRuntime:
    """In-process DAG runner — drives one tool-loop call per node attempt.

    ``trace`` collects ordered events (provider_call, tool_loop_summary,
    node_retry_decision). ``records`` collects NodeRunRecord-shaped dicts
    (RUNNING / SUCCEEDED / FAILED) with status + error_category for the
    outer-retry shell test (Plan 03-03 Test B).
    """
    provider: Any
    output_dir: Path
    skill_root: Path | None = None
    cli: CliReporter | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)

    def _run_node(
        self,
        *,
        node: NodeSpec,
        scenario: Any,
        dependency_payloads: dict[str, dict[str, Any]] | None = None,
    ) -> Path:
        deps = dependency_payloads or {}
        last_error: Exception | None = None
        request_id = _request_id_from_scenario(scenario)
        for attempt in range(1, node.max_attempts + 1):
            attempt_started = time.monotonic()
            session_id = f"{node.id}:attempt-{attempt}:{uuid.uuid4().hex[:8]}"
            self._cli_event(
                f"node {node.id}",
                "start",
                request_id=request_id,
                skill=node.skill_name,
                attempt=f"{attempt}/{node.max_attempts}",
            )
            self.records.append(
                {"node_id": node.id, "attempt": attempt, "session_id": session_id, "status": "RUNNING"}
            )
            self.trace.append(
                {"type": "provider_call", "node_id": node.id, "session_id": session_id, "attempt": attempt}
            )
            try:
                result = run_node_attempt(
                    config=NodeAttemptConfig(
                        node_id=node.id,
                        skill_name=node.skill_name,
                        output_model=node.output_model,
                        attempt=attempt,
                        session_id=session_id,
                        output_dir=self.output_dir,
                        skill_root=self.skill_root,
                        tools_spec=TOOLS_SPEC,
                        tool_handlers=TOOL_HANDLERS,
                        skill_loader=load_skill_prose,
                    ),
                    scenario=scenario,
                    dependency_payloads=deps,
                    provider=self.provider,
                )
                self.trace.append(result.summary)
                output_path = result.output_path
                self.records.append(result.record)
                self._cli_event(
                    f"node {node.id}",
                    "done",
                    request_id=request_id,
                    status="SUCCEEDED",
                    skill=node.skill_name,
                    attempt=f"{attempt}/{node.max_attempts}",
                    turns=result.summary["turns_used"],
                    tool_calls=result.summary["tool_calls_made"],
                    tokens=_total_tokens(result.summary["usage"]),
                    duration=f"{time.monotonic() - attempt_started:.1f}s",
                    artifact=output_path.name,
                )
                return output_path
            except Exception as exc:
                last_error = exc
                info = classify_exception(exc)
                self.records.append(
                    {"node_id": node.id, "attempt": attempt, "session_id": session_id,
                     "status": "FAILED", "error": repr(exc),
                     "error_category": str(info["category"]), "retryable": bool(info["retryable"])}
                )
                self.trace.append(
                    {"type": "node_retry_decision", "node_id": node.id, "attempt": attempt,
                     "error_category": info["category"], "retryable": info["retryable"],
                     "remaining_attempts": node.max_attempts - attempt}
                )
                self._cli_event(
                    f"node {node.id}",
                    "error",
                    request_id=request_id,
                    skill=node.skill_name,
                    attempt=f"{attempt}/{node.max_attempts}",
                    category=info["category"],
                    retryable=info["retryable"],
                    remaining_attempts=node.max_attempts - attempt,
                    duration=f"{time.monotonic() - attempt_started:.1f}s",
                    error=_short_error(exc),
                )
                if not info["retryable"]:
                    break
        raise RuntimeError(f"Node {node.id} failed after {node.max_attempts} attempts") from last_error

    def run_request(
        self,
        *,
        scenario: Any,
        nodes: list[NodeSpec],
    ) -> dict[str, Path]:
        """Drive a multi-node DAG sequentially.

        Calls ``_run_node`` per ``nodes`` entry in list order. After each node
        succeeds, reads the written artifact JSON back from disk and
        accumulates it into a ``dependency_payloads`` dict keyed by
        ``node.id`` so the next node's ``provider_payload_for_node`` can
        resolve upstream artifacts.

        Returns: dict mapping ``node.id`` -> output_path.
        """
        dependency_payloads: dict[str, dict[str, Any]] = {}
        output_paths: dict[str, Path] = {}
        request_id = _request_id_from_scenario(scenario)
        started = time.monotonic()
        self._cli_event(
            f"request {request_id}",
            "start",
            nodes=len(nodes),
            output_dir=self.output_dir,
        )
        try:
            for node in nodes:
                output_path = self._run_node(
                    node=node,
                    scenario=scenario,
                    dependency_payloads=dependency_payloads,
                )
                dependency_payloads[node.id] = json.loads(
                    output_path.read_text(encoding="utf-8")
                )
                output_paths[node.id] = output_path
        except Exception:
            self._cli_event(
                f"request {request_id}",
                "done",
                status="FAILED",
                nodes=len(nodes),
                artifacts=len(output_paths),
                duration=f"{time.monotonic() - started:.1f}s",
            )
            raise
        self._cli_event(
            f"request {request_id}",
            "done",
            status="SUCCEEDED",
            nodes=len(nodes),
            artifacts=len(output_paths),
            duration=f"{time.monotonic() - started:.1f}s",
        )
        return output_paths

    def _cli_event(self, scope: str, message: str = "", **fields: Any) -> None:
        if self.cli is not None:
            self.cli.event(scope, message, **fields)


def _request_id_from_scenario(scenario: Any) -> str:
    if isinstance(scenario, dict):
        raw = scenario.get("request_id") or scenario.get("scenario_id")
        if raw:
            return str(raw)
    return "request"


def _total_tokens(usage: dict[str, Any]) -> int | str:
    value = usage.get("total_tokens")
    if value is None:
        return "-"
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


def _short_error(exc: Exception) -> str:
    text = repr(exc)
    return text if len(text) <= 240 else text[:237] + "..."
