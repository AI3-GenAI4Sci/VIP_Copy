"""Request-failure classifier for production batches.

The production batch runner consumes ``classify(exc)`` to route exceptions into
one of three labels:

* ``"trial_failure"`` — the exception originated inside a production-slot
  delta trial after the runner had already recorded a ``trial_failed``
  event. The host batch continues because the failed artifact belongs to
  the temporary patched skill surface, not to normal traffic.
* ``"provider_error"`` — HTTP / API errors from the OpenAI-compatible
  client: rate limit, auth, transient, response. The runner records the
  request failure, continues the batch, and lets the final request-rerun pass
  decide whether it recovers.
* ``"infra_error"`` — anything else (``KeyError``, ``AttributeError``,
  ``FileNotFoundError``, ``ValueError``, schema-validation, tool-
  validation, etc.). The runner records the request failure, continues the
  batch, and includes unresolved failures in ``failed_requests.json``.

Routing summary:

    label             ┃ runner action
    ━━━━━━━━━━━━━━━━━━┃━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "trial_failure"   ┃ record on the request row, host continues
    "provider_error"  ┃ record request failure, rerun at batch end
    "infra_error"     ┃ record request failure, rerun at batch end

The classifier inspects exception class only — never the message
string, never the call site. Type-based classification matches the
explicit allow-list rule the 07-04 plan task 1 calls out. The
classifier DOES walk the ``__cause__`` / ``__context__`` chain so
provider exceptions that upstream wrappers re-raise as a generic
``RuntimeError`` (e.g. ``dag_runner._run_node``'s
``RuntimeError("Node X failed after 1 attempts")`` wrapper) still
route to ``provider_error`` rather than the ``infra_error`` default.
Without the walk, every wrapped provider failure lands in the
default bucket and audit logs diverge from the true upstream cause
(observed live in 07-06 retry: real ``ProviderAuthError`` and
``ProviderResponseError`` both surfaced as ``RuntimeError`` and were
labelled ``infra_error``).
"""

from __future__ import annotations

from typing import Literal

from pydantic import ValidationError as _PydanticValidationError

from seers_harness.core.errors import (
    BusinessOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransientError,
    SchemaValidationHarnessError,
)


# ---------------------------------------------------------------------------
# Sentinel exception for trial-context failures
# ---------------------------------------------------------------------------


class TrialFailure(Exception):
    """Sentinel exception class for patched-skill trial failures."""


# ---------------------------------------------------------------------------
# Classification allow-list
# ---------------------------------------------------------------------------


# Provider HTTP / API errors from ``OpenAICompatibleProvider`` (Phase 2
# error taxonomy in seers_harness/core/errors.py). All four types share
# the ``ProviderCallError`` base, but listing them explicitly keeps the
# allow-list literal — the classifier matches on these and nothing else.
_PROVIDER_EXCEPTION_TYPES: tuple[type[BaseException], ...] = (
    ProviderRateLimitError,
    ProviderTransientError,
    ProviderAuthError,
    ProviderResponseError,
)

_REQUEST_OUTPUT_EXCEPTION_TYPES: tuple[type[BaseException], ...] = (
    BusinessOutputError,
    SchemaValidationHarnessError,
    _PydanticValidationError,
)


FailureClass = Literal[
    "auth",
    "rate_limit",
    "transient",
    "malformed_tool_args",
    "business_output",
    "schema_violation",
    "runner_bug",
    "ok",
]


_FAILURE_CLASS_DISPATCH: tuple[tuple[type[BaseException], FailureClass], ...] = (
    (ProviderAuthError, "auth"),
    (ProviderRateLimitError, "rate_limit"),
    (ProviderTransientError, "transient"),
    (ProviderResponseError, "malformed_tool_args"),
    (BusinessOutputError, "business_output"),
    (SchemaValidationHarnessError, "schema_violation"),
    (_PydanticValidationError, "schema_violation"),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify(
    exc: BaseException,
) -> Literal["trial_failure", "provider_error", "infra_error"]:
    """Route ``exc`` into one of three request-failure labels.

    See the module docstring for full label semantics. The function
    walks the ``__cause__`` / ``__context__`` chain so wrapped
    provider exceptions (e.g. ``dag_runner._run_node`` re-raising as
    ``RuntimeError``) still route correctly. Short-circuits on the
    first ``isinstance`` match. The default fallback is
    ``"infra_error"`` — there is no silent-absorb branch.
    """
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, TrialFailure):
            return "trial_failure"
        if isinstance(cur, _PROVIDER_EXCEPTION_TYPES):
            return "provider_error"
        cur = cur.__cause__ or cur.__context__
    return "infra_error"


def failure_class(exc: BaseException | None) -> FailureClass:
    """Return the seven-label D8-E outcome class for analytics rows.

    This function is intentionally independent from ``classify``:
    ``classify`` owns the three-label request routing contract,
    while ``failure_class`` owns the operator-facing aggregation label.
    Classification is type-only and walks ``__cause__`` / ``__context__``
    so wrapped provider/schema errors keep their upstream class.
    """
    if exc is None:
        return "ok"
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        for exc_type, label in _FAILURE_CLASS_DISPATCH:
            if isinstance(cur, exc_type):
                return label
        cur = cur.__cause__ or cur.__context__
    return "runner_bug"


def is_trial_failure(exc: BaseException) -> bool:
    """``True`` iff ``classify(exc) == "trial_failure"``.

    Convenience predicate for the batch runner's per-request loop: the runner
    records the trial outcome on the request row and continues to the next
    request on ``True``.
    """
    return classify(exc) == "trial_failure"


def is_request_output_failure(exc: BaseException) -> bool:
    """True when node retries are exhausted by invalid model output.

    These failures are request-local: malformed JSON content, schema
    violations, or deterministic business gates such as empty candidates.
    Provider and infrastructure errors are recorded as request failures and
    rerun at the end of the batch.
    """
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, _REQUEST_OUTPUT_EXCEPTION_TYPES):
            return True
        cur = cur.__cause__ or cur.__context__
    return False
