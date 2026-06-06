"""Streaming response assembly for OpenAI-compatible chat completions."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any


class StreamDeadlineExceeded(TimeoutError):
    """Deadline exceeded while a stream had already produced partial output."""

    def __init__(
        self,
        *,
        deadline_seconds: float,
        elapsed_seconds: float,
        partial_response: Any,
    ) -> None:
        self.deadline_seconds = deadline_seconds
        self.elapsed_seconds = elapsed_seconds
        self.partial_response = partial_response
        self.partial_summary = stream_response_summary(partial_response)
        super().__init__(
            "call_deadline exceeded during stream "
            f"({deadline_seconds:.3f}s); "
            + ", ".join(
                f"{key}={value}" for key, value in self.partial_summary.items()
            )
        )


def collect_stream_response(response_or_stream: Any, *, deadline_seconds: float) -> Any:
    if not hasattr(response_or_stream, "__iter__") and not hasattr(response_or_stream, "__enter__"):
        return response_or_stream

    started = time.monotonic()
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    state: dict[str, Any] = {
        "finish_reason": None,
        "usage": None,
        "model": getattr(response_or_stream, "model", None),
    }
    tool_builders: dict[int, dict[str, Any]] = {}

    if hasattr(response_or_stream, "__enter__"):
        with response_or_stream as stream:
            _consume_stream(
                stream,
                started=started,
                deadline_seconds=deadline_seconds,
                content_parts=content_parts,
                reasoning_parts=reasoning_parts,
                tool_builders=tool_builders,
                state=state,
            )
    else:
        _consume_stream(
            response_or_stream,
            started=started,
            deadline_seconds=deadline_seconds,
            content_parts=content_parts,
            reasoning_parts=reasoning_parts,
            tool_builders=tool_builders,
            state=state,
        )

    message = SimpleNamespace(
        content="".join(content_parts),
        reasoning_content="".join(reasoning_parts) if reasoning_parts else None,
        tool_calls=_tool_builders_to_raw_calls(tool_builders) or None,
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=state["finish_reason"])],
        model=state["model"],
        usage=state["usage"],
    )


def extract_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    return {
        key: getattr(usage, key, None)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


def stream_response_summary(response: Any) -> dict[str, Any]:
    choices = getattr(response, "choices", None) or []
    message = getattr(choices[0], "message", None) if choices else None
    content = getattr(message, "content", "") if message is not None else ""
    reasoning = (
        getattr(message, "reasoning_content", "") if message is not None else ""
    )
    tool_calls = getattr(message, "tool_calls", None) if message is not None else None
    return {
        "partial_content_chars": len(content or ""),
        "partial_reasoning_chars": len(reasoning or ""),
        "partial_tool_call_count": len(tool_calls or []),
        "finish_reason": getattr(choices[0], "finish_reason", None)
        if choices
        else None,
    }


def _consume_stream(
    stream: Any,
    *,
    started: float,
    deadline_seconds: float,
    content_parts: list[str],
    reasoning_parts: list[str],
    tool_builders: dict[int, dict[str, Any]],
    state: dict[str, Any],
) -> None:
    for chunk in stream:
        if getattr(chunk, "usage", None) is not None:
            state["usage"] = chunk.usage
        if getattr(chunk, "model", None):
            state["model"] = chunk.model
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        choice = choices[0]
        if getattr(choice, "finish_reason", None) is not None:
            state["finish_reason"] = choice.finish_reason
        delta = getattr(choice, "delta", None)
        if delta is None:
            continue
        content = getattr(delta, "content", None)
        if content:
            content_parts.append(content)
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            reasoning_parts.append(reasoning)
        for tool_delta in getattr(delta, "tool_calls", None) or []:
            _merge_tool_delta(tool_builders, tool_delta)
        elapsed = time.monotonic() - started
        if deadline_seconds > 0 and elapsed > deadline_seconds:
            raise StreamDeadlineExceeded(
                deadline_seconds=deadline_seconds,
                elapsed_seconds=elapsed,
                partial_response=_response_from_parts(
                    content_parts=content_parts,
                    reasoning_parts=reasoning_parts,
                    tool_builders=tool_builders,
                    state=state,
                ),
            )


def _merge_tool_delta(tool_builders: dict[int, dict[str, Any]], tool_delta: Any) -> None:
    index = int(getattr(tool_delta, "index", 0) or 0)
    builder = tool_builders.setdefault(
        index,
        {"id": None, "type": "function", "name_parts": [], "argument_parts": []},
    )
    if getattr(tool_delta, "id", None):
        builder["id"] = tool_delta.id
    if getattr(tool_delta, "type", None):
        builder["type"] = tool_delta.type
    function = getattr(tool_delta, "function", None)
    if function is None:
        return
    if getattr(function, "name", None):
        builder["name_parts"].append(function.name)
    if getattr(function, "arguments", None):
        builder["argument_parts"].append(function.arguments)


def _tool_builders_to_raw_calls(tool_builders: dict[int, dict[str, Any]]) -> list[Any]:
    raw_calls: list[Any] = []
    for index in sorted(tool_builders):
        builder = tool_builders[index]
        raw_calls.append(
            SimpleNamespace(
                id=builder["id"] or f"call_{index}",
                type=builder["type"] or "function",
                function=SimpleNamespace(
                    name="".join(builder["name_parts"]),
                    arguments="".join(builder["argument_parts"]),
                ),
            )
        )
    return raw_calls


def _response_from_parts(
    *,
    content_parts: list[str],
    reasoning_parts: list[str],
    tool_builders: dict[int, dict[str, Any]],
    state: dict[str, Any],
) -> Any:
    message = SimpleNamespace(
        content="".join(content_parts),
        reasoning_content="".join(reasoning_parts) if reasoning_parts else None,
        tool_calls=_tool_builders_to_raw_calls(tool_builders) or None,
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=state["finish_reason"])],
        model=state["model"],
        usage=state["usage"],
    )
