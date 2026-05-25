"""Phase 2.2 patch RED tests — ProviderResult.raw_tool_calls field + adapter wiring.

These two tests + Task 2's 5-line patch are the wire-format echo prerequisite
for Phase 3 tool_loop.py (RESEARCH §7-Q1). Adapter test follows the same
monkeypatch-the-local-OpenAI pattern as test_provider_openai_compatible.py.
"""

from __future__ import annotations

import json
from dataclasses import fields

from seers_harness.provider_runtime.base import ProviderResult
from seers_harness.provider_runtime.openai_compatible import OpenAICompatibleProvider


def _make_provider(monkeypatch, fake_openai_client) -> OpenAICompatibleProvider:
    monkeypatch.setattr(
        "seers_harness.provider_runtime.openai_compatible.OpenAI",
        lambda **kw: fake_openai_client,
    )
    return OpenAICompatibleProvider(model="deepseek-v4-pro", api_key="sk-test")


def test_provider_result_has_raw_tool_calls_field():
    """RESEARCH §7-Q1 — the field exists and defaults to None."""
    field_names = {f.name for f in fields(ProviderResult)}
    assert "raw_tool_calls" in field_names
    pr = ProviderResult()
    assert pr.raw_tool_calls is None


def test_openai_compatible_populates_raw_tool_calls_from_sdk(
    monkeypatch, fake_openai_client, fake_openai_response
):
    """Adapter threads message.tool_calls (SDK SimpleNamespace shape) into raw_tool_calls."""
    provider = _make_provider(monkeypatch, fake_openai_client)
    fake_openai_client.queue_response(
        fake_openai_response(
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "record_factor",
                    "arguments": json.dumps({"factor_id": "F1"}),
                }
            ],
            finish_reason="tool_calls",
        )
    )
    result = provider.generate_with_tools(
        node_id="n",
        skill_bundle="s",
        messages=[{"role": "system", "content": "x"}],
        tools=[],
    )
    # raw_tool_calls is the SDK passthrough — preserves the SimpleNamespace
    # objects so the loop can echo them verbatim on the next turn (DeepSeek wire format).
    assert result.raw_tool_calls is not None
    assert len(result.raw_tool_calls) == 1
    assert result.raw_tool_calls[0].id == "call_1"
    assert result.raw_tool_calls[0].function.name == "record_factor"
    # Regression guard: parsed c17 shape (existing behavior) is unchanged.
    assert result.tool_calls == [
        {"id": "call_1", "name": "record_factor", "arguments": {"factor_id": "F1"}}
    ]
