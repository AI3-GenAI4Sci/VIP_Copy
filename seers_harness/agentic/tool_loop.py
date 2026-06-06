"""Pure-function multi-turn tool-use loop driving every c17 SKILL.

Terminates via ``state['final_artifact']`` or an optional deterministic
finalizer after the model stops calling tools. Echoes ``reasoning_content`` and
SDK-shaped ``raw_tool_calls`` for DeepSeek ``/beta`` follow-up turns.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from seers_harness.core.errors import ProviderTransientError, ToolValidationError


_TRANSIENT_BACKOFF_SECONDS: tuple[float, ...] = (0.0, 5.0, 15.0)
"""D8-B backoff (charter Q4 + D8-B): attempt 0 → no sleep; 1 → 5s; 2 → 15s.
Literal values locked — no exponential backoff, no per-call print/log."""


class ToolLoopError(RuntimeError):
    """Terminal loop failure: cap exceeded or no final artifact."""


@dataclass(frozen=True)
class ToolLoopResult:
    artifact: dict
    turns_used: int
    tool_calls_made: int
    last_reasoning_content: str | None
    usage: dict[str, Any] = field(default_factory=dict)


def run_skill_via_tools(
    *,
    skill_name: str,
    skill_bundle: str,
    payload: Mapping[str, Any],
    tools_spec: list[dict],
    tool_handlers: dict[str, Callable[..., str]],
    provider,
    node_id: str,
    max_tool_calls: int = 30,
    max_transient_retries_per_turn: int = 2,
    finalize_state: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
) -> ToolLoopResult:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": skill_bundle},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    # state["payload"] is the handler-side ground truth for deterministic
    # finalization that needs upstream request context.
    state: dict[str, Any] = {"payload": payload, "skill_name": skill_name}
    tool_calls_made = 0
    usage: dict[str, Any] = {}

    for turn in range(max_tool_calls):
        for attempt in range(max_transient_retries_per_turn + 1):
            if attempt > 0:
                time.sleep(_TRANSIENT_BACKOFF_SECONDS[min(attempt, len(_TRANSIENT_BACKOFF_SECONDS) - 1)])
            try:
                result = provider.generate_with_tools(
                    node_id=node_id,
                    skill_bundle=skill_bundle,
                    messages=messages,
                    tools=tools_spec,
                )
                _merge_usage(usage, getattr(result, "usage", {}) or {})
                break
            except ProviderTransientError:
                if attempt == max_transient_retries_per_turn:
                    raise

        # Wire-format echo (RESEARCH §2): subsequent turns require BOTH
        # reasoning_content AND the original SDK tool_calls shape.
        messages.append({
            "role": "assistant",
            "content": result.raw_response_text or None,
            "tool_calls": _jsonable_tool_calls(result.raw_tool_calls),
            "reasoning_content": result.reasoning_content,
        })

        if not result.tool_calls:
            if finalize_state is not None:
                artifact = finalize_state(state)
                if artifact is not None:
                    return ToolLoopResult(
                        artifact,
                        turn + 1,
                        tool_calls_made,
                        result.reasoning_content,
                        usage=dict(usage),
                    )
            raise ToolLoopError("model stopped without final artifact")

        for tc in result.tool_calls:
            tool_calls_made += 1
            handler = tool_handlers.get(tc["name"])
            if handler is None:
                msg = f"ERROR: unknown tool {tc['name']!r}"
            else:
                try:
                    msg = handler(tc["arguments"], state)
                except ToolValidationError as exc:
                    msg = f"ERROR: {exc}"
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": msg})

        if "final_artifact" in state:
            return ToolLoopResult(state["final_artifact"], turn + 1, tool_calls_made, result.reasoning_content, usage=dict(usage))

    raise ToolLoopError(f"exceeded max_tool_calls={max_tool_calls}")


def _merge_usage(total: dict[str, Any], usage: Mapping[str, Any]) -> None:
    for key, value in usage.items():
        if value is not None:
            total[key] = total.get(key, 0) + value if isinstance(value, int | float) and not isinstance(value, bool) else value


def _jsonable_tool_calls(raw_tool_calls: Any) -> list[dict[str, Any]] | None:
    return [_jsonable_tool_call(call) for call in raw_tool_calls] if raw_tool_calls else None


def _jsonable_tool_call(call: Any) -> dict[str, Any]:
    function = getattr(call, "function", None)
    return {"id": getattr(call, "id", None), "type": getattr(call, "type", None) or "function", "function": {"name": getattr(function, "name", ""), "arguments": getattr(function, "arguments", "")}}
