"""Provider call capture-record construction."""

from __future__ import annotations

import copy
from dataclasses import asdict, is_dataclass
from typing import Any


def build_capture_record(
    *,
    inner: Any,
    result: Any,
    node_id: str | None,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    usage = dict(getattr(inner, "last_usage", {}) or {})
    if "model" not in usage:
        inner_model = getattr(inner, "model", None)
        if inner_model is not None:
            usage["model"] = inner_model
    return {
        "node_id": node_id,
        "messages": copy.deepcopy(messages),
        "response": result_to_capture_dict(result),
        "tool_calls": list(getattr(result, "tool_calls", []) or []),
        "last_usage": usage,
        "final_artifact": None,
    }


def result_to_capture_dict(result: Any) -> dict[str, Any]:
    """Best-effort serialize a provider result for evidence capture."""
    if is_dataclass(result):
        data = asdict(result)
        data.pop("raw_tool_calls", None)
        return data
    keys = (
        "payload",
        "usage",
        "tool_calls",
        "finish_reason",
        "reasoning_content",
        "raw_messages",
        "raw_response_text",
        "model",
    )
    out: dict[str, Any] = {}
    for key in keys:
        if hasattr(result, key):
            out[key] = getattr(result, key)
    return out
