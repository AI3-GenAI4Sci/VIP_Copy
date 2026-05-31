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
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from seers_harness.agentic.tool_loop import ToolLoopError, run_skill_via_tools
from seers_harness.core.errors import (
    BusinessOutputError,
    SchemaValidationHarnessError,
    classify_exception,
)
from seers_harness.tools.skill_tools import TOOL_HANDLERS, TOOLS_SPEC
from seers_harness.workflow.payloads import provider_payload_for_node
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
        for attempt in range(1, node.max_attempts + 1):
            session_id = f"{node.id}:attempt-{attempt}:{uuid.uuid4().hex[:8]}"
            self.records.append(
                {"node_id": node.id, "attempt": attempt, "session_id": session_id, "status": "RUNNING"}
            )
            self.trace.append(
                {"type": "provider_call", "node_id": node.id, "session_id": session_id, "attempt": attempt}
            )
            try:
                base_payload = provider_payload_for_node(
                    node_id=node.id, scenario=scenario,
                    dependency_payloads=deps, session_id=session_id,
                )
                skill_bundle = (
                    load_skill_prose(node.skill_name, skill_root=self.skill_root)
                    if self.skill_root is not None
                    else load_skill_prose(node.skill_name)
                )
                result = run_skill_via_tools(
                    skill_name=node.skill_name,
                    skill_bundle=skill_bundle,
                    payload=base_payload.get("scenario") or base_payload,
                    tools_spec=TOOLS_SPEC[node.skill_name],
                    tool_handlers=TOOL_HANDLERS,
                    provider=self.provider,
                    node_id=node.id,
                )
                self.trace.append(
                    {
                        "type": "tool_loop_summary", "node_id": node.id, "session_id": session_id,
                        "turns_used": result.turns_used,
                        "tool_calls_made": result.tool_calls_made,
                        "last_reasoning_content": result.last_reasoning_content,
                        "usage": result.usage,
                    }
                )
                try:
                    parsed = node.output_model.model_validate(result.artifact)
                except ValidationError as exc:
                    raise SchemaValidationHarnessError(str(exc)) from exc
                _assert_business_output(node_id=node.id, scenario=base_payload.get("scenario") or base_payload, artifact=parsed)
                _attach_final_artifact(self.provider, node.id, parsed)
                output_path = self._write_artifact(node, session_id, parsed)
                self.records.append(
                    {"node_id": node.id, "attempt": attempt, "session_id": session_id,
                     "status": "SUCCEEDED", "output_path": str(output_path)}
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
                if not info["retryable"]:
                    break
        raise RuntimeError(f"Node {node.id} failed after {node.max_attempts} attempts") from last_error

    def _write_artifact(self, node: NodeSpec, session_id: str, parsed: BaseModel) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{node.id}-{session_id}.json"
        path.write_text(parsed.model_dump_json(indent=2), encoding="utf-8")
        return path

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
        return output_paths


def _attach_final_artifact(provider: Any, node_id: str, parsed: BaseModel) -> None:
    """Attach the validated node artifact to the latest captured provider turn."""
    request_log = getattr(provider, "request_log", None)
    if not isinstance(request_log, list):
        return
    artifact = parsed.model_dump(mode="json")
    for record in reversed(request_log):
        if isinstance(record, dict) and record.get("node_id") == node_id:
            record["final_artifact"] = artifact
            return


def _assert_business_output(*, node_id: str, scenario: dict[str, Any], artifact: BaseModel) -> None:
    if node_id != "personalized_copy_generation":
        return
    if not isinstance(scenario, dict):
        return
    if int(scenario.get("target_product_count") or 0) <= 0:
        return
    data = artifact.model_dump(mode="json")
    if not data.get("candidates"):
        raise BusinessOutputError(
            "personalized_copy_generation produced zero candidates for a non-empty request"
        )
