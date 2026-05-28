"""Error taxonomy for provider, runtime retries, and tool-use validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HarnessError(Exception):
    message: str
    category: str = "unknown"
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


class ProviderCallError(HarnessError):
    pass


class ProviderRateLimitError(ProviderCallError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, category="rate_limit", retryable=True)


class ProviderTransientError(ProviderCallError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, category="transient_provider", retryable=True)


class ProviderResponseError(ProviderCallError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, category="provider_response", retryable=True)


class ProviderAuthError(ProviderCallError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, category="auth", retryable=False)


class SchemaValidationHarnessError(HarnessError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, category="schema_validation", retryable=True)


class ToolValidationError(HarnessError):
    def __init__(self, message: str, tool_name: str = "", arg_path: str = "") -> None:
        super().__init__(message=message, category="tool_validation", retryable=True)
        self.tool_name = tool_name
        self.arg_path = arg_path


def classify_exception(exc: Exception) -> dict[str, object]:
    category = getattr(exc, "category", None) or infer_category(exc)
    retryable = getattr(exc, "retryable", None)
    if retryable is None:
        retryable = category in {
            "rate_limit",
            "transient_provider",
            "provider_response",
            "schema_validation",
            "tool_validation",
        }
    return {
        "category": category,
        "retryable": bool(retryable),
        "type": type(exc).__name__,
    }


def infer_category(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    text = repr(exc).lower()
    if "ratelimit" in name or "rate_limit" in name or "rate limit" in text or "429" in text:
        return "rate_limit"
    if (
        "authentication" in name
        or "permission" in name
        or "401" in text
        or "402" in text
        or "403" in text
        or "insufficient balance" in text
        or "payment required" in text
    ):
        return "auth"
    if any(term in name for term in ("timeout", "connection", "apierror")):
        return "transient_provider"
    if any(term in text for term in ("timeout", "connection reset", "temporarily unavailable", "502", "503", "504")):
        return "transient_provider"
    if "json" in name or "jsondecode" in name:
        return "provider_response"
    return "unknown"
