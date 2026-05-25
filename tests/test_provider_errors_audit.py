"""PROV-04 audit tests — confirm Phase 1 `core/errors.py` already routes the
three typed provider exceptions through `classify_exception` correctly.

These tests are RED-then-GREEN ON TASK 1 because Phase 1 already shipped the
contract. If any of these fails, Phase 1 has a regression and Plan 02-01 must
STOP and surface the issue (do NOT silently patch Phase 1 in this plan —
phase-boundary violation).

PROV-04 requirement (REQUIREMENTS.md line 49):
  Exception classification via `classify_exception(exc)` returns:
    rate_limit         -> ProviderRateLimitError
    transient_provider -> ProviderTransientError
    auth               -> ProviderAuthError
    else re-raise (i.e. category="unknown" for unmapped types)
"""

from __future__ import annotations

from seers_harness.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTransientError,
    classify_exception,
)


def test_provider_rate_limit_error_classifies_as_rate_limit() -> None:
    """PROV-04: ProviderRateLimitError -> category 'rate_limit'."""
    assert classify_exception(ProviderRateLimitError("boom"))["category"] == "rate_limit"


def test_provider_transient_error_classifies_as_transient_provider() -> None:
    """PROV-04: ProviderTransientError -> category 'transient_provider'."""
    assert classify_exception(ProviderTransientError("boom"))["category"] == "transient_provider"


def test_provider_auth_error_classifies_as_auth() -> None:
    """PROV-04: ProviderAuthError -> category 'auth' AND retryable=False."""
    result = classify_exception(ProviderAuthError("boom"))
    assert result["category"] == "auth" and result["retryable"] is False


def test_rate_limit_and_transient_errors_are_retryable() -> None:
    """PROV-04: both rate_limit and transient_provider categories ARE retryable."""
    rl = classify_exception(ProviderRateLimitError("a"))
    tr = classify_exception(ProviderTransientError("b"))
    assert rl["retryable"] is True and tr["retryable"] is True


def test_unknown_exception_returns_unknown_category() -> None:
    """PROV-04 'else re-raise' branch: unmapped exception types -> 'unknown'.

    The provider Wave 2 impl reads this to decide whether to bubble the raw
    exception or wrap it in a typed ProviderCallError.
    """
    assert classify_exception(ValueError("x"))["category"] == "unknown"
