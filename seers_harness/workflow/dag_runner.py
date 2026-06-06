"""WorkflowRuntime — invokes the tool-use loop per node attempt (LOOP-05).

Per master_plan §4.4 and RESEARCH §4 KEEP/DELETE/REWRITE table, ``_run_node``
collapses to one ``run_skill_via_tools(...)`` call followed by
``model_type.model_validate(result.artifact)``. Each node attempt is a single
tool-loop invocation plus pydantic validation; the trace event is
``tool_loop_summary`` with fields {turns_used, tool_calls_made,
last_reasoning_content, usage}. See RESEARCH §4 + §8 for the table and pitfalls.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel

from seers_harness.core.errors import classify_exception
from seers_harness.tools.skill_tools import TOOL_HANDLERS, TOOLS_SPEC
from seers_harness.workflow.node_attempt import NodeAttemptConfig, run_node_attempt, write_node_artifact
from seers_harness.workflow.payloads import provider_payload_for_node
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
class ArtifactCache:
    """Thread-safe artifact cache for deterministic reusable node outputs."""

    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    _inflight: dict[str, threading.Event] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def reserve(self, key: str) -> tuple[str, dict[str, Any] | threading.Event | None]:
        with self._lock:
            if key in self.entries:
                return "hit", copy.deepcopy(self.entries[key])
            event = self._inflight.get(key)
            if event is not None:
                return "wait", event
            event = threading.Event()
            self._inflight[key] = event
            return "owner", event

    def store(self, key: str, artifact: Mapping[str, Any]) -> None:
        with self._lock:
            self.entries[key] = copy.deepcopy(dict(artifact))
            event = self._inflight.pop(key, None)
        if event is not None:
            event.set()

    def release(self, key: str) -> None:
        with self._lock:
            event = self._inflight.pop(key, None)
        if event is not None:
            event.set()


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
    display_request_id: str | None = None
    cli: CliReporter | None = None
    artifact_cache: ArtifactCache | None = None
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
        request_id = self.display_request_id or _request_id_from_scenario(scenario)
        cache_key = _cache_key_for_node(
            node=node,
            scenario=scenario,
            deps=deps,
            skill_root=self.skill_root,
        )
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
            owns_cache_key = False
            try:
                if cache_key is not None and self.artifact_cache is not None:
                    cached_or_owner = self._cached_or_reserved(
                        node=node,
                        scenario=scenario,
                        deps=deps,
                        cache_key=cache_key,
                        session_id=session_id,
                        attempt=attempt,
                        started=attempt_started,
                    )
                    if isinstance(cached_or_owner, Path):
                        return cached_or_owner
                    owns_cache_key = True
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
                if owns_cache_key and self.artifact_cache is not None:
                    self.artifact_cache.store(
                        cache_key,
                        result.parsed.model_dump(mode="json"),
                    )
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
                if owns_cache_key and cache_key is not None and self.artifact_cache is not None:
                    self.artifact_cache.release(cache_key)
                last_error = exc
                info = classify_exception(exc)
                exc_summary = getattr(exc, "summary", None)
                if isinstance(exc_summary, dict) and exc_summary:
                    self.trace.append(dict(exc_summary))
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

    def _cached_or_reserved(
        self,
        *,
        node: NodeSpec,
        scenario: Any,
        deps: dict[str, dict[str, Any]],
        cache_key: str,
        session_id: str,
        attempt: int,
        started: float,
    ) -> Path | None:
        assert self.artifact_cache is not None
        while True:
            status, value = self.artifact_cache.reserve(cache_key)
            if status == "owner":
                return None
            if status == "wait":
                assert isinstance(value, threading.Event)
                value.wait()
                continue
            assert isinstance(value, dict)
            parsed = node.output_model.model_validate(value)
            output_path = write_node_artifact(self.output_dir, node.id, session_id, parsed)
            payload = provider_payload_for_node(
                node_id=node.id,
                scenario=scenario,
                dependency_payloads=deps,
                session_id=session_id,
            )["scenario"]
            _attach_cache_record(self.provider, node.id, payload, parsed, cache_key)
            summary = {
                "type": "tool_loop_summary",
                "mode": "cache",
                "node_id": node.id,
                "session_id": session_id,
                "turns_used": 0,
                "tool_calls_made": 0,
                "last_reasoning_content": None,
                "usage": {"total_tokens": 0, "cache_hit": True},
            }
            self.trace.append(summary)
            self.records.append(
                {
                    "node_id": node.id,
                    "attempt": attempt,
                    "session_id": session_id,
                    "status": "SUCCEEDED",
                    "output_path": str(output_path),
                    "cache_hit": True,
                }
            )
            request_id = _request_id_from_scenario(scenario)
            self._cli_event(
                f"node {node.id}",
                "done",
                request_id=request_id,
                status="SUCCEEDED",
                skill=node.skill_name,
                attempt=f"{attempt}/{node.max_attempts}",
                turns=0,
                tool_calls=0,
                tokens=0,
                duration=f"{time.monotonic() - started:.1f}s",
                artifact=output_path.name,
                cache="hit",
            )
            return output_path

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
        request_id = self.display_request_id or _request_id_from_scenario(scenario)
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


def _cache_key_for_node(
    *,
    node: NodeSpec,
    scenario: Any,
    deps: dict[str, dict[str, Any]],
    skill_root: Path | None = None,
) -> str | None:
    if node.id != "personalized_user_mining":
        return None
    user_id = _user_id_from_scenario(scenario)
    if not user_id:
        return None
    payload = provider_payload_for_node(
        node_id=node.id,
        scenario=scenario,
        dependency_payloads=deps,
    )["scenario"]
    skill_prose = load_skill_prose(node.skill_name, skill_root=skill_root)
    stable_payload = {
        "skill_hash": hashlib.sha256(skill_prose.encode("utf-8")).hexdigest(),
        "user_id": user_id,
        "user_history": {
            key: value
            for key, value in payload.items()
            if key not in {"request_id", "scenario_id"}
        },
    }
    encoded = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"{node.id}:{digest}"


def _user_id_from_scenario(scenario: Any) -> str:
    if hasattr(scenario, "model_dump"):
        data = scenario.model_dump(mode="json")
    elif isinstance(scenario, dict):
        data = scenario
    else:
        return ""
    user_state = data.get("user_state") if isinstance(data, dict) else {}
    if not isinstance(user_state, dict):
        return ""
    for source in (
        user_state,
        user_state.get("profile") if isinstance(user_state.get("profile"), dict) else {},
    ):
        raw = source.get("user_id") if isinstance(source, dict) else None
        if raw not in (None, ""):
            return str(raw)
    return ""


def _attach_cache_record(
    provider: Any,
    node_id: str,
    payload: dict[str, Any],
    parsed: BaseModel,
    cache_key: str,
) -> None:
    request_log = getattr(provider, "request_log", None)
    if not isinstance(request_log, list):
        return
    request_log.append(
        {
            "node_id": node_id,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            ],
            "response": {
                "cache_hit": True,
                "cache_key": cache_key,
                "raw_response_text": "",
            },
            "tool_calls": [],
            "last_usage": {"total_tokens": 0, "cache_hit": True},
            "final_artifact": parsed.model_dump(mode="json"),
        }
    )


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
