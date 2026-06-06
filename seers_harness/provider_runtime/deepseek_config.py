"""DeepSeek runtime defaults and pure fact reporting."""

from __future__ import annotations

import os
from typing import Any

from seers_harness.core.errors import classify_exception

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_BETA_BASE_URL = DEEPSEEK_BASE_URL
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_CALL_DEADLINE_SECONDS = 300
DEFAULT_MAX_INFLIGHT_CALLS = 20
DEFAULT_PARSE_MAX_RETRIES = 3
DEFAULT_REASONING_EFFORT = "xhigh"


def parse_max_retries() -> int:
    raw = os.environ.get("DEEPSEEK_PARSE_MAX_RETRIES")
    if not raw:
        return DEFAULT_PARSE_MAX_RETRIES
    try:
        return max(int(raw), 0)
    except ValueError:
        return DEFAULT_PARSE_MAX_RETRIES


def deepseek_runtime_facts() -> dict[str, Any]:
    sample = type("_SampleRateLimit", (Exception,), {})("HTTP 429 rate limit exceeded")
    return {
        "default_model": "deepseek-v4-pro",
        "default_base_url": DEEPSEEK_BASE_URL,
        "default_timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "default_sdk_max_retries": 0,
        "default_call_deadline_seconds": DEFAULT_CALL_DEADLINE_SECONDS,
        "default_max_inflight_calls": DEFAULT_MAX_INFLIGHT_CALLS,
        "streaming_enabled": True,
        "thinking_enabled": True,
        "reasoning_effort": DEFAULT_REASONING_EFFORT,
        "tool_choice": "auto",
        "rate_limit_exception_category": str(classify_exception(sample)["category"]),
    }
