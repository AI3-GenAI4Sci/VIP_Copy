"""Provider interfaces shared by runtime adapters.

Production workflow nodes use :py:meth:`Provider.generate_json` so DeepSeek JSON
mode can return structured artifacts without tool calls. Evolution skills still
use :py:meth:`Provider.generate_with_tools` for explicit patch/tool contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class Provider(Protocol):
    """Provider surface for production JSON mode and evolution tool mode.

    Adapters (e.g. ``openai_compatible.OpenAICompatibleProvider`` from Plan 02-02)
    set ``last_usage`` on every call so the workflow can read
    ``provider.last_usage`` after each turn for accounting.
    """

    last_usage: dict[str, Any]

    def generate_with_tools(
        self,
        *,
        node_id: str,
        skill_bundle: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ProviderResult:
        """One LLM turn. Returns either tool_calls or stop (via finish_reason)."""
        ...

    def generate_json(
        self,
        *,
        node_id: str,
        skill_bundle: str,
        messages: list[dict[str, Any]],
    ) -> ProviderResult:
        """One JSON-mode LLM turn for production nodes."""
        ...


# Field order: ``payload`` first so Phase 2 tests can positional-construct
# ``ProviderResult(payload=...)``; ``tool_calls`` follows ``usage`` to keep the
# primary output channel near the top.
@dataclass
class ProviderResult:
    """One LLM turn's structured output.

    PROV-05: ``tool_calls`` is the primary output channel; ``payload`` is the
    back-compat slot (kept empty — Phase 3 reads ``tool_calls``).
    """

    payload: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    # PROV-05: shape is `[{"id": str, "name": str, "arguments": dict}]`.
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # Wave 2 impl populates with whatever the OpenAI SDK returns:
    # `"tool_calls"`, `"stop"`, `"length"`, etc.
    finish_reason: str | None = None
    # DeepSeek `/beta` returns this when reasoning is enabled per ADR-PROBE-7.1.1.
    reasoning_content: str | None = None
    raw_messages: list[dict[str, Any]] | None = None
    raw_response_text: str | None = None
    model: str | None = None
    # SDK passthrough for wire-format echo (LOOP) — RESEARCH §2.
    raw_tool_calls: list | None = None
