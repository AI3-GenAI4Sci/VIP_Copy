"""Provider call capture-record construction."""

from __future__ import annotations

import copy
from dataclasses import asdict, is_dataclass
from typing import Any

from seers_harness.provider_runtime.streaming import extract_usage


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


def build_failure_capture_record(
    *,
    inner: Any,
    exc: BaseException,
    node_id: str | None,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    partial_response = getattr(exc, "partial_response", None)
    response = result_to_capture_dict(partial_response) if partial_response is not None else {}
    response["node_id"] = node_id
    response["error"] = _short_repr(exc)
    response["error_type"] = type(exc).__name__
    partial_summary = getattr(exc, "partial_summary", None)
    if isinstance(partial_summary, dict):
        response["partial_summary"] = dict(partial_summary)
    usage: dict[str, Any] = {}
    if partial_response is not None:
        usage.update(extract_usage(partial_response))
    if "model" not in usage:
        inner_model = getattr(inner, "model", None)
        if inner_model is not None:
            usage["model"] = inner_model
    return {
        "node_id": node_id,
        "messages": copy.deepcopy(messages),
        "response": response,
        "tool_calls": [],
        "last_usage": usage,
        "final_artifact": None,
    }


def result_to_capture_dict(result: Any) -> dict[str, Any]:
    """Best-effort serialize a provider result for evidence capture."""
    if result is None:
        return {}
    if is_dataclass(result):
        data = asdict(result)
        data.pop("raw_tool_calls", None)
        return data
    choices = getattr(result, "choices", None) or []
    if choices:
        choice = choices[0]
        message = getattr(choice, "message", None)
        if message is not None:
            return {
                "usage": extract_usage(result),
                "tool_calls": getattr(message, "tool_calls", None) or [],
                "finish_reason": getattr(choice, "finish_reason", None),
                "reasoning_content": getattr(message, "reasoning_content", None),
                "raw_response_text": getattr(message, "content", None) or "",
                "model": getattr(result, "model", None),
            }
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


def _short_repr(exc: BaseException) -> str:
    text = repr(exc)
    return text if len(text) <= 1000 else text[:997] + "..."
