"""ScriptedProvider — hermetic Provider Protocol test double for the c17 tool_loop.

Records each ``messages`` snapshot at call time (so wire-format tests can inspect
what the loop fed back on subsequent turns) and pops scripted turns. NO openai
import. Mirrors the Phase 2 Provider Protocol shape: ``last_usage`` attribute +
``generate_with_tools(*, node_id, skill_bundle, messages, tools)`` returning a
``ProviderResult``. Shape locked by RESEARCH §6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seers_harness.provider_runtime.base import ProviderResult


@dataclass
class ScriptedTurn:
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw_tool_calls: list[Any] = field(default_factory=list)
    finish_reason: str = "tool_calls"
    reasoning_content: str | None = "R" * 30
    raise_exc: BaseException | None = None


@dataclass
class ScriptedProvider:
    script: list[ScriptedTurn]
    received_messages: list[list[dict[str, Any]]] = field(default_factory=list)
    last_usage: dict[str, Any] = field(default_factory=dict)
    _idx: int = 0

    def generate_with_tools(
        self,
        *,
        node_id: str,
        skill_bundle: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ProviderResult:
        # Snapshot the messages list as the loop has it RIGHT NOW. Shallow dict
        # copy is sufficient: the loop only appends new dicts to messages; it
        # never mutates the dicts it has already inserted.
        self.received_messages.append([dict(m) for m in messages])
        turn = self.script[self._idx]
        self._idx += 1
        if turn.raise_exc is not None:
            raise turn.raise_exc
        return ProviderResult(
            payload={},
            usage={},
            tool_calls=turn.tool_calls,
            finish_reason=turn.finish_reason,
            reasoning_content=turn.reasoning_content,
            raw_messages=messages,
            raw_response_text="",
            model="scripted",
            raw_tool_calls=turn.raw_tool_calls,
        )
