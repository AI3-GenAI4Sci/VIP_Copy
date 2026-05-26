"""D-19 trial-failure routing classifier — Phase 7 plan 07-04.

The Phase 7 stage runner consumes ``classify(exc)`` to route exceptions
into one of three labels per D-19:

* ``"trial_failure"`` — the exception originated inside a trial wrapper
  (the ``run_request_trial`` hook from 07-01 already recorded the
  outcome via the ``trial_failed`` event) and the host request must
  continue on the unmodified main path. Schema / tool-protocol failures
  inside a trial still bubble up here only when the caller chose to
  re-raise them; in 07-04 the trial_runner returns a ``TrialOutcome``
  with ``success=False`` instead of raising, so this branch is the seam
  07-06 will extend when full evolution wiring lands. No code in 07-04
  raises ``TrialFailure``; the sentinel exists so 07-06 can attach a
  trial-context envelope without changing the classifier surface.
* ``"provider_error"`` — HTTP / API errors from the OpenAI-compatible
  client: rate limit, auth, transient, response. Per D-02 the stage
  runner fails fast at request level on these (the SDK-level resilience
  budget owned by ``OpenAICompatibleProvider`` per D-03 has already
  been exhausted by the time the exception bubbles up).
* ``"infra_error"`` — anything else (``KeyError``, ``AttributeError``,
  ``FileNotFoundError``, ``ValueError``, schema-validation, tool-
  validation, etc.). Per D-02 the stage runner fails fast at request
  level. The default fallback is ``"infra_error"`` — the classifier
  never silently absorbs an unknown exception class.

Routing summary (consumer side, 07-04 stage runner):

    label             ┃ runner action
    ━━━━━━━━━━━━━━━━━━┃━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "trial_failure"   ┃ record on the request row, host continues
    "provider_error"  ┃ fail-fast (stage stops, exit non-zero)
    "infra_error"     ┃ fail-fast (stage stops, exit non-zero)

The classifier is intentionally narrow: it inspects exception class
only, never the message string, never the cause chain, never the call
site. Type-based classification matches the explicit allow-list rule
the 07-04 plan task 1 calls out.
"""

from __future__ import annotations

from typing import Literal

from seers_harness.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransientError,
)


# ---------------------------------------------------------------------------
# Sentinel exception for trial-context failures (07-06 extension point)
# ---------------------------------------------------------------------------


class TrialFailure(Exception):
    """Sentinel exception class — wraps a trial-context failure.

    07-04 itself never raises ``TrialFailure``: ``run_request_trial``
    (07-01) records failures via the ``TrialOutcome`` return contract
    rather than raising. 07-06's full evolution wiring may choose to
    wrap selected trial-context exceptions in this envelope before
    surfacing them to the stage runner. Defining the sentinel here
    keeps the classifier surface stable across both phases — 07-06 can
    extend behaviour without changing the classifier's three-label
    contract or the stage runner's switch on ``classify(exc)``.
    """


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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify(
    exc: BaseException,
) -> Literal["trial_failure", "provider_error", "infra_error"]:
    """Route ``exc`` into one of three D-19 labels.

    See the module docstring for full label semantics. The function
    short-circuits on the first ``isinstance`` match. The default
    fallback is ``"infra_error"`` — there is no silent-absorb branch.
    """
    if isinstance(exc, TrialFailure):
        return "trial_failure"
    if isinstance(exc, _PROVIDER_EXCEPTION_TYPES):
        return "provider_error"
    return "infra_error"


def is_trial_failure(exc: BaseException) -> bool:
    """``True`` iff ``classify(exc) == "trial_failure"``.

    Convenience predicate for the stage runner's per-request loop:
    the runner records the trial outcome on the request row and
    continues to the next request on ``True``; otherwise it fails
    fast at request level (D-02).
    """
    return classify(exc) == "trial_failure"
