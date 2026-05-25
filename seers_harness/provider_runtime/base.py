"""Provider interfaces shared by runtime adapters in C17.

Phase 2 declares one entry point — :py:meth:`Provider.generate_with_tools` —
which returns a :class:`ProviderResult` carrying either tool-call output or a
stop verdict. PROV-01 deletes the c16 parallel JSON method at the Protocol
level (its literal absence here is the contract). PROV-05 makes ``tool_calls``
the primary output channel; ``payload`` is retained as an empty back-compat slot.

Per ADR-PROBE-7.1, reasoning + tools coexist at DeepSeek ``/beta``. Runtime
params (``reasoning_effort="max"``, ``extra_body={"thinking":{"type":"enabled"}}``,
``base_url="https://api.deepseek.com/beta"``, ``tool_choice="auto"``) are
hard-coded inside the Wave 2 adapter — PROV-03 forbids per-turn / per-node
branching, so no per-node policy dataclass appears on this surface (its
literal absence is also a contract). See
``research/probe_reasoning_with_tools_result.md``.

Adapters raise :class:`seers_harness.core.errors.ProviderRateLimitError`,
:class:`seers_harness.core.errors.ProviderTransientError`, or
:class:`seers_harness.core.errors.ProviderAuthError` from
:py:meth:`Provider.generate_with_tools` per PROV-04; the loop layer routes
these via ``classify_exception``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class Provider(Protocol):
    """Single Phase 2 LLM entry point.

    Adapters (e.g. ``openai_compatible.OpenAICompatibleProvider`` from Plan 02-02)
    set ``last_usage`` on every call so the Phase 3 tool_loop can read
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


# Field order rationale (PROV-05 + Plan 02-01 spec):
#   `payload` first to keep the c16 ProviderResult signature stable for tests
#   that positional-construct `ProviderResult(payload=...)`. `tool_calls` third
#   (after `usage`) so the most-frequently-touched new field is near the top;
#   remaining fields keep the c16 ordering verbatim.
@dataclass
class ProviderResult:
    """One LLM turn's structured output.

    PROV-05: ``tool_calls`` is the primary output channel; ``payload`` is the
    back-compat slot (kept empty in c17 — Phase 3 reads ``tool_calls``).
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
