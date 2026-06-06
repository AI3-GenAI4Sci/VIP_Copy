"""OpenAI-compatible provider adapter for production JSON and evolution tools."""

from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any

from openai import OpenAI

from seers_harness.core.errors import ProviderAuthError, ProviderRateLimitError, ProviderResponseError, ProviderTransientError, classify_exception
from seers_harness.provider_runtime.base import ProviderResult
from seers_harness.provider_runtime.deepseek_config import DEFAULT_CALL_DEADLINE_SECONDS, DEFAULT_MAX_INFLIGHT_CALLS, DEFAULT_REASONING_EFFORT, DEFAULT_TIMEOUT_SECONDS, DEEPSEEK_BETA_BASE_URL, deepseek_runtime_facts, parse_max_retries
from seers_harness.provider_runtime.streaming import collect_stream_response, extract_usage
from seers_harness.workflow.progress import render_cli_event, write_cli_line

# Locked runtime literals: tool_choice="auto", reasoning_effort="xhigh",
# "thinking": {"type": "enabled"}
_TYPED_PROVIDER_ERRORS: dict[str, type[Exception]] = {
    "rate_limit": ProviderRateLimitError,
    "transient_provider": ProviderTransientError,
    "auth": ProviderAuthError,
}

_SEMAPHORE_LOCK = threading.Lock()
_SEMAPHORES: dict[int, threading.BoundedSemaphore] = {}


class OpenAICompatibleProvider:
    """OpenAI-compatible DeepSeek adapter. ``last_usage`` is set on every call."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = 0,
        call_deadline_seconds: float | None = None,
        max_inflight_calls: int | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key, "base_url": base_url or DEEPSEEK_BETA_BASE_URL, "max_retries": max_retries}
        if timeout_seconds is not None:
            kwargs["timeout"] = timeout_seconds
        self.client = OpenAI(**kwargs)
        self.model = model
        self.last_usage: dict[str, Any] = {}
        self.call_deadline_seconds = (
            float(call_deadline_seconds)
            if call_deadline_seconds is not None
            else DEFAULT_CALL_DEADLINE_SECONDS
        )
        self.max_inflight_calls = max(1, int(max_inflight_calls or DEFAULT_MAX_INFLIGHT_CALLS))

    def generate_with_tools(self, *, node_id: str, skill_bundle: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ProviderResult:
        params: dict[str, Any] = {
            "model": self.model, "messages": messages, "tools": tools,
            "tool_choice": "auto", "reasoning_effort": DEFAULT_REASONING_EFFORT,
            "extra_body": {"thinking": {"type": "enabled"}},
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        last_parse: ProviderResponseError | None = None
        max_parse_retries = parse_max_retries()
        for _attempt in range(max_parse_retries + 1):
            try:
                response = self._stream_chat_completion(params)
            except Exception as exc:
                typed = _TYPED_PROVIDER_ERRORS.get(classify_exception(exc)["category"])
                if typed is not None:
                    raise _typed_provider_error(typed, exc) from exc
                raise
            self.last_usage = extract_usage(response)
            choice = response.choices[0]
            message = choice.message
            raw_tool_calls = getattr(message, "tool_calls", None) or []
            try:
                tool_calls_out = [
                    {"id": tc.id, "name": tc.function.name, "arguments": _parse_args(tc.function.arguments, node_id=node_id)}
                    for tc in raw_tool_calls
                ]
            except ProviderResponseError as exc:
                last_parse = exc
                write_cli_line(
                    sys.stderr,
                    render_cli_event(
                        "provider",
                        "parse_retry",
                        node=node_id,
                        attempt=f"{_attempt + 1}/{max_parse_retries + 1}",
                    ),
                )
                continue
            return ProviderResult(
                payload={}, usage=dict(self.last_usage), tool_calls=tool_calls_out,
                finish_reason=getattr(choice, "finish_reason", None),
                reasoning_content=getattr(message, "reasoning_content", None),
                raw_messages=[dict(m) for m in messages],
                raw_response_text=(message.content or ""),
                model=getattr(response, "model", None),
                raw_tool_calls=raw_tool_calls,
            )
        assert last_parse is not None
        raise last_parse

    def generate_json(self, *, node_id: str, skill_bundle: str, messages: list[dict[str, Any]]) -> ProviderResult:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "reasoning_effort": DEFAULT_REASONING_EFFORT,
            "extra_body": {"thinking": {"type": "enabled"}},
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        try:
            response = self._stream_chat_completion(params)
        except Exception as exc:
            typed = _TYPED_PROVIDER_ERRORS.get(classify_exception(exc)["category"])
            if typed is not None:
                raise _typed_provider_error(typed, exc) from exc
            raise
        self.last_usage = extract_usage(response)
        choice = response.choices[0]
        message = choice.message
        return ProviderResult(
            payload={},
            usage=dict(self.last_usage),
            tool_calls=[],
            finish_reason=getattr(choice, "finish_reason", None),
            reasoning_content=getattr(message, "reasoning_content", None),
            raw_messages=[dict(m) for m in messages],
            raw_response_text=(message.content or ""),
            model=getattr(response, "model", None),
            raw_tool_calls=[],
        )

    def _stream_chat_completion(self, params: dict[str, Any]) -> Any:
        semaphore = _shared_inflight_semaphore(self.max_inflight_calls)
        semaphore.acquire()
        try:
            response_or_stream = self.client.chat.completions.create(**params)
            return collect_stream_response(
                response_or_stream,
                deadline_seconds=self.call_deadline_seconds,
            )
        finally:
            semaphore.release()


def _parse_args(raw: str | None, *, node_id: str) -> dict[str, Any]:
    if raw is None:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderResponseError(f"Failed to parse tool_call.arguments for node {node_id}: {raw[:200]}") from exc


def _typed_provider_error(error_type: type[Exception], exc: Exception) -> Exception:
    typed = error_type(repr(exc))
    for attr in ("partial_response", "partial_summary"):
        if hasattr(exc, attr):
            setattr(typed, attr, getattr(exc, attr))
    return typed


def _shared_inflight_semaphore(max_inflight_calls: int) -> threading.BoundedSemaphore:
    limit = max(1, int(max_inflight_calls))
    with _SEMAPHORE_LOCK:
        semaphore = _SEMAPHORES.get(limit)
        if semaphore is None:
            semaphore = threading.BoundedSemaphore(limit)
            _SEMAPHORES[limit] = semaphore
        return semaphore


def deepseek_provider_from_env(
    *,
    model: str | None = None,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
    call_deadline_seconds: float | None = None,
    max_inflight_calls: int | None = None,
) -> OpenAICompatibleProvider:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required for DeepSeek provider")
    timeout = timeout_seconds if timeout_seconds is not None else float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    retries = max_retries if max_retries is not None else int(os.environ.get("DEEPSEEK_SDK_MAX_RETRIES", "0"))
    deadline = (
        call_deadline_seconds
        if call_deadline_seconds is not None
        else float(os.environ.get("DEEPSEEK_CALL_DEADLINE_SECONDS", str(DEFAULT_CALL_DEADLINE_SECONDS)))
    )
    inflight = (
        max_inflight_calls
        if max_inflight_calls is not None
        else int(os.environ.get("DEEPSEEK_MAX_INFLIGHT_CALLS", str(DEFAULT_MAX_INFLIGHT_CALLS)))
    )
    return OpenAICompatibleProvider(
        model=model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        api_key=api_key, base_url=os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BETA_BASE_URL),
        timeout_seconds=timeout,
        max_retries=retries,
        call_deadline_seconds=deadline,
        max_inflight_calls=inflight,
    )
