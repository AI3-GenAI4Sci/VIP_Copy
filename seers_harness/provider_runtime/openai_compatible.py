"""OpenAI-compatible provider adapter — single entry ``generate_with_tools`` (PROV-01).

Runtime params locked per ADR-PROBE-7.1.1: ``reasoning_effort="max"`` +
``thinking={"type":"enabled"}`` + ``tool_choice="auto"`` at DeepSeek ``/beta``
(PROV-03). Default model ``deepseek-v4-pro``; ``deepseek-chat`` deprecated.
CR-05: bounded parse-layer retry (``DEEPSEEK_PARSE_MAX_RETRIES``, default 3,
0 disables) absorbs transient truncated ``tool_call.arguments`` JSON without
touching HTTP retries (D-03) or D-19 routing on exhaustion.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from seers_harness.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransientError,
    classify_exception,
)
from seers_harness.provider_runtime.base import ProviderResult

DEEPSEEK_BETA_BASE_URL = "https://api.deepseek.com/beta"
_DEFAULT_PARSE_MAX_RETRIES = 3
_TYPED_PROVIDER_ERRORS: dict[str, type[Exception]] = {
    "rate_limit": ProviderRateLimitError,
    "transient_provider": ProviderTransientError,
    "auth": ProviderAuthError,
}


def _parse_max_retries() -> int:
    raw = os.environ.get("DEEPSEEK_PARSE_MAX_RETRIES")
    if not raw:
        return _DEFAULT_PARSE_MAX_RETRIES
    try:
        return max(int(raw), 0)
    except ValueError:
        return _DEFAULT_PARSE_MAX_RETRIES


class OpenAICompatibleProvider:
    """Single Phase-2 LLM entry point. ``last_usage`` is set on every call."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = 0,
    ) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key, "base_url": base_url or DEEPSEEK_BETA_BASE_URL, "max_retries": max_retries}
        if timeout_seconds is not None:
            kwargs["timeout"] = timeout_seconds
        self.client = OpenAI(**kwargs)
        self.model = model
        self.last_usage: dict[str, Any] = {}

    def generate_with_tools(self, *, node_id: str, skill_bundle: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ProviderResult:
        params: dict[str, Any] = {
            "model": self.model, "messages": messages, "tools": tools,
            "tool_choice": "auto", "reasoning_effort": "max",
            "extra_body": {"thinking": {"type": "enabled"}},
        }
        last_parse: ProviderResponseError | None = None
        for _attempt in range(_parse_max_retries() + 1):
            try:
                response = self.client.chat.completions.create(**params)
            except Exception as exc:
                typed = _TYPED_PROVIDER_ERRORS.get(classify_exception(exc)["category"])
                if typed is not None:
                    raise typed(repr(exc)) from exc
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


def _parse_args(raw: str | None, *, node_id: str) -> dict[str, Any]:
    if raw is None:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderResponseError(f"Failed to parse tool_call.arguments for node {node_id}: {raw[:200]}") from exc


def extract_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    return {k: getattr(usage, k, None) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}


def deepseek_runtime_facts() -> dict[str, Any]:
    """Return read-only DeepSeek runtime facts (PROD-02). Pure: no client, no network."""
    sample = type("_SampleRateLimit", (Exception,), {})("HTTP 429 rate limit exceeded")
    return {
        "default_model": "deepseek-v4-pro", "default_base_url": DEEPSEEK_BETA_BASE_URL,
        "default_timeout_seconds": 60, "default_sdk_max_retries": 0,
        "thinking_enabled": True, "reasoning_effort": "max", "tool_choice": "auto",
        "rate_limit_exception_category": str(classify_exception(sample)["category"]),
    }


def deepseek_provider_from_env(*, model: str | None = None, timeout_seconds: float | None = None, max_retries: int | None = None) -> OpenAICompatibleProvider:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required for DeepSeek provider")
    timeout = timeout_seconds if timeout_seconds is not None else float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "60"))
    retries = max_retries if max_retries is not None else int(os.environ.get("DEEPSEEK_SDK_MAX_RETRIES", "0"))
    return OpenAICompatibleProvider(
        model=model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        api_key=api_key, base_url=os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BETA_BASE_URL),
        timeout_seconds=timeout, max_retries=retries,
    )

