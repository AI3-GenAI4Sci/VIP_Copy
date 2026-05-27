"""Pure-function multi-turn tool-use loop driving every c17 SKILL.

Calls ``provider.generate_with_tools`` per turn, dispatches each tool_call via
``tool_handlers``, appends ``role:tool`` results, and terminates when a handler
sets ``state['final_artifact']``. Echoes ``reasoning_content`` + the SDK-shape
``raw_tool_calls`` on the assistant message every subsequent turn — DeepSeek's
``/beta`` wire-format contract (RESEARCH §2). Failure routing per LOOP-03.
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
    """Terminal loop failure: cap exceeded, stop-without-submit."""


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
) -> ToolLoopResult:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": skill_bundle},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    # state["payload"] is the handler-side ground truth for evidence-path resolution
    # (record_factor / record_candidate / judge_candidate all read it).
    state: dict[str, Any] = {"payload": payload}
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
            "tool_calls": result.raw_tool_calls,
            "reasoning_content": result.reasoning_content,
        })

        if not result.tool_calls:
            raise ToolLoopError("model stopped without submit_final")

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
