"""Phase 8 plan 08-11 — D8-G-WR-05 narrow except in run_request_trial.

Verifies the three branches of the narrowed exception envelope:

1. ProviderAuthError / ProviderRateLimitError / ProviderTransientError
   re-raise so the runner's D-19 classifier routes them to
   ``provider_error`` and fails fast at request level. The ``events``
   list MUST NOT carry a ``trial_failed`` record for these cases —
   provider errors are not trial failures.
2. TrialFailure / AssertionError / pydantic.ValidationError (alias
   ``SchemaError``) are caught and recorded as a trial failure on the
   ``TrialOutcome`` plus an ``events`` ``trial_failed`` record. The
   trial-failure semantics (D-19 ``trial_failure`` route) are preserved.
3. Any other ``Exception`` (e.g. ``KeyError``) propagates to the caller
   unmodified, so the runner's D-19 routes it to ``infra_error`` and
   fails fast. No ``trial_failed`` record is emitted because this is
   not a trial failure — it is a runner bug.

The tests use a minimal in-memory fault runtime that raises a
configured exception inside ``run_request``. The trial runner is
exercised through its public ``run_request_trial`` surface, with a
``patch=None`` control trial (no skill-text mutation needed for the
narrow assertion) and a real on-disk live skill root so
``apply_delta_patch_temporarily``'s file-isolation contract holds.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from seers_harness.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTransientError,
)
from seers_harness.evolution.trial_runner import run_request_trial
from seers_harness.validation.exception_classifier import TrialFailure


class _Schema(BaseModel):
    must_be_int: int


def _make_pydantic_validation_error() -> ValidationError:
    """Construct a real ``pydantic.ValidationError`` instance."""
    try:
        _Schema(must_be_int="not-an-int")  # type: ignore[arg-type]
    except ValidationError as exc:
        return exc
    raise AssertionError("ValidationError was not raised")  # pragma: no cover


class _FaultRuntime:
    """Runtime stub: ``run_request`` raises a configured exception."""

    trace: list[dict] = []

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def run_request(self, *, scenario, nodes):
        raise self._exc


def _live_skill_root(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("skill", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Re-raise: ProviderError subclasses must NOT be caught (D-19 provider_error) #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "exc",
    [
        ProviderAuthError("401 stale env key"),
        ProviderRateLimitError("429 rate limited"),
        ProviderTransientError("502 upstream"),
    ],
    ids=["auth", "rate_limit", "transient"],
)
def test_trial_runner_reraises_provider_errors(
    tmp_path: Path, exc: BaseException
) -> None:
    runtime = _FaultRuntime(exc)
    events: list[dict] = []

    with pytest.raises(type(exc)) as excinfo:
        run_request_trial(
            runtime=runtime,
            scenario={},
            nodes=[],
            live_skill_root=_live_skill_root(tmp_path / "live"),
            workspace_dir=tmp_path / "workspace",
            patch=None,
            request_id="R-1",
            scenario_id="S-1",
            events=events,
        )

    # Same exception instance bubbles up unmodified — no wrapping.
    assert excinfo.value is exc
    # ``trial_started`` is fine; ``trial_failed`` MUST NOT appear because
    # provider errors are not trial failures (D-19 provider_error route).
    types = [ev.get("type") for ev in events]
    assert "trial_failed" not in types
    assert "trial_succeeded" not in types


# --------------------------------------------------------------------------- #
# Catch: TrialFailure / AssertionError / SchemaError record trial_failed      #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "exc_factory, expected_class",
    [
        (lambda: TrialFailure("schema mismatch in trial"), "TrialFailure"),
        (lambda: AssertionError("invariant broken"), "AssertionError"),
        (_make_pydantic_validation_error, "ValidationError"),
    ],
    ids=["trial_failure", "assertion", "schema_error"],
)
def test_trial_runner_catches_schema_violation(
    tmp_path: Path, exc_factory, expected_class: str
) -> None:
    exc = exc_factory()
    runtime = _FaultRuntime(exc)
    events: list[dict] = []

    outcome = run_request_trial(
        runtime=runtime,
        scenario={},
        nodes=[],
        live_skill_root=_live_skill_root(tmp_path / "live"),
        workspace_dir=tmp_path / "workspace",
        patch=None,
        request_id="R-2",
        scenario_id="S-2",
        events=events,
    )

    assert outcome.success is False
    assert outcome.failure_category == expected_class
    failed = [ev for ev in events if ev.get("type") == "trial_failed"]
    assert len(failed) == 1
    assert failed[0]["exception_class"] == expected_class
    assert failed[0]["trial_id"] == "R-2"
    # No ``trial_succeeded`` event on the failure path.
    assert not any(ev.get("type") == "trial_succeeded" for ev in events)


# --------------------------------------------------------------------------- #
# Propagate: unknown exceptions float up (D-19 infra_error route)             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "exc",
    [
        KeyError("missing-key"),
        TypeError("bad-type"),
        IndexError("out-of-range"),
    ],
    ids=["key_error", "type_error", "index_error"],
)
def test_trial_runner_propagates_unknown_exception(
    tmp_path: Path, exc: BaseException
) -> None:
    runtime = _FaultRuntime(exc)
    events: list[dict] = []

    with pytest.raises(type(exc)) as excinfo:
        run_request_trial(
            runtime=runtime,
            scenario={},
            nodes=[],
            live_skill_root=_live_skill_root(tmp_path / "live"),
            workspace_dir=tmp_path / "workspace",
            patch=None,
            request_id="R-3",
            scenario_id="S-3",
            events=events,
        )

    # The same exception instance propagates unmodified so D-19's
    # classify() lands on ``infra_error`` (not silently absorbed).
    assert excinfo.value is exc
    # No ``trial_failed`` record — runner bugs are not trial failures.
    assert not any(ev.get("type") == "trial_failed" for ev in events)
    assert not any(ev.get("type") == "trial_succeeded" for ev in events)
