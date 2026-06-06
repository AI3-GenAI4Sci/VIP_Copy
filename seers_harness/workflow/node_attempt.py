"""Single workflow node attempt execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from seers_harness.agentic.json_mode import run_skill_via_json
from seers_harness.agentic.tool_loop import run_skill_via_tools
from seers_harness.core.errors import BusinessOutputError, SchemaValidationHarnessError
from seers_harness.tools.skill_tools import TOOL_HANDLERS, TOOLS_SPEC
from seers_harness.validation.artifact_checks import validate_artifact_against_payload
from seers_harness.workflow.payloads import provider_payload_for_node
from seers_harness.workflow.skill_loader import load_skill_prose


@dataclass(frozen=True)
class NodeAttemptConfig:
    node_id: str
    skill_name: str
    output_model: type[BaseModel]
    attempt: int
    session_id: str
    output_dir: Path
    skill_root: Path | None = None
    tools_spec: dict[str, list[dict[str, Any]]] | None = None
    tool_handlers: dict[str, Callable[..., str]] | None = None
    skill_loader: Callable[..., str] | None = None


@dataclass(frozen=True)
class NodeAttemptResult:
    output_path: Path
    parsed: BaseModel
    summary: dict[str, Any]
    record: dict[str, Any]


_PRODUCTION_JSON_SKILLS: frozenset[str] = frozenset(
    {
        "personalized-user-mining",
        "personalized-copy-generation",
        "personalized-copy-rubric-judge",
    }
)


def run_node_attempt(
    *,
    config: NodeAttemptConfig,
    scenario: Any,
    dependency_payloads: dict[str, dict[str, Any]],
    provider: Any,
) -> NodeAttemptResult:
    base_payload = provider_payload_for_node(
        node_id=config.node_id,
        scenario=scenario,
        dependency_payloads=dependency_payloads,
        session_id=config.session_id,
    )
    loader = config.skill_loader or load_skill_prose
    if config.skill_root is None:
        skill_bundle = loader(config.skill_name)
    else:
        skill_bundle = loader(config.skill_name, skill_root=config.skill_root)
    payload = base_payload.get("scenario") or base_payload
    if config.skill_name in _PRODUCTION_JSON_SKILLS:
        result = run_skill_via_json(
            skill_bundle=skill_bundle,
            payload=payload,
            provider=provider,
            node_id=config.node_id,
        )
        summary = {
            "type": "tool_loop_summary",
            "mode": "json",
            "node_id": config.node_id,
            "session_id": config.session_id,
            "turns_used": 1,
            "tool_calls_made": 0,
            "last_reasoning_content": result.reasoning_content,
            "usage": result.usage,
        }
    else:
        tools_spec = config.tools_spec or TOOLS_SPEC
        tool_handlers = config.tool_handlers or TOOL_HANDLERS
        result = run_skill_via_tools(
            skill_name=config.skill_name,
            skill_bundle=skill_bundle,
            payload=payload,
            tools_spec=tools_spec[config.skill_name],
            tool_handlers=tool_handlers,
            provider=provider,
            node_id=config.node_id,
        )
        summary = {
            "type": "tool_loop_summary",
            "mode": "tools",
            "node_id": config.node_id,
            "session_id": config.session_id,
            "turns_used": result.turns_used,
            "tool_calls_made": result.tool_calls_made,
            "last_reasoning_content": result.last_reasoning_content,
            "usage": result.usage,
        }
    try:
        parsed = config.output_model.model_validate(result.artifact)
    except ValidationError as exc:
        raise SchemaValidationHarnessError(
            str(exc),
            raw_artifact=result.artifact,
            summary=summary,
        ) from exc
    _assert_business_output(
        node_id=config.node_id,
        scenario=base_payload.get("scenario") or base_payload,
        artifact=parsed,
    )
    _attach_final_artifact(provider, config.node_id, parsed)
    output_path = write_node_artifact(config.output_dir, config.node_id, config.session_id, parsed)
    record = {
        "node_id": config.node_id,
        "attempt": config.attempt,
        "session_id": config.session_id,
        "status": "SUCCEEDED",
        "output_path": str(output_path),
    }
    return NodeAttemptResult(
        output_path=output_path,
        parsed=parsed,
        summary=summary,
        record=record,
    )


def write_node_artifact(
    output_dir: Path,
    node_id: str,
    session_id: str,
    parsed: BaseModel,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{node_id}-{session_id}.json"
    path.write_text(parsed.model_dump_json(indent=2), encoding="utf-8")
    return path


def _attach_final_artifact(provider: Any, node_id: str, parsed: BaseModel) -> None:
    request_log = getattr(provider, "request_log", None)
    if not isinstance(request_log, list):
        return
    artifact = parsed.model_dump(mode="json")
    for record in reversed(request_log):
        if isinstance(record, dict) and record.get("node_id") == node_id:
            record["final_artifact"] = artifact
            return


def _assert_business_output(*, node_id: str, scenario: dict[str, Any], artifact: BaseModel) -> None:
    if isinstance(scenario, dict):
        validate_artifact_against_payload(
            node_id=node_id,
            payload=scenario,
            artifact=artifact,
        )
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
