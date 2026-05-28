from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from seers_harness.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransientError,
    classify_exception,
)
from seers_harness.validation.exception_classifier import (
    TrialFailure,
    classify,
    failure_class,
)


class _SchemaProbe(BaseModel):
    count: int


def _schema_validation_error() -> ValidationError:
    with pytest.raises(ValidationError) as exc_info:
        _SchemaProbe.model_validate({"count": "not-an-int"})
    return exc_info.value


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (None, "ok"),
        (ProviderAuthError("secret-auth-message"), "auth"),
        (ProviderRateLimitError("rate limited"), "rate_limit"),
        (ProviderTransientError("temporary outage"), "transient"),
        (ProviderResponseError("bad tool args"), "malformed_tool_args"),
        (_schema_validation_error(), "schema_violation"),
        (KeyError("foo"), "runner_bug"),
        (ValueError("bar"), "runner_bug"),
        (TrialFailure("trial wrapped"), "runner_bug"),
    ],
)
def test_failure_class_maps_allowed_exception_types(exc, expected):
    assert failure_class(exc) == expected


def test_failure_class_walks_cause_chain_for_provider_auth():
    provider_exc = ProviderAuthError("wrapped secret-auth-message")
    wrapped = RuntimeError("node failed")
    wrapped.__cause__ = provider_exc

    assert failure_class(wrapped) == "auth"


def test_provider_402_insufficient_balance_classifies_as_auth():
    exc = RuntimeError(
        "APIStatusError: Error code: 402 - "
        "{'error': {'message': 'Insufficient Balance'}}"
    )

    result = classify_exception(exc)

    assert result["category"] == "auth"
    assert result["retryable"] is False


def test_classify_three_label_contract_is_unchanged():
    assert classify(TrialFailure("trial")) == "trial_failure"
    assert classify(ProviderAuthError("auth")) == "provider_error"
    assert classify(ValueError("bug")) == "infra_error"
