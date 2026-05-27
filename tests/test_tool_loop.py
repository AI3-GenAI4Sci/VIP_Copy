"""D8-B — transient retry backoff in ``run_skill_via_tools``.

Phase 08 plan 08-08: the existing turn-internal transient-retry loop in
``seers_harness/agentic/tool_loop.py`` is augmented with a fixed backoff
sequence ``_TRANSIENT_BACKOFF_SECONDS = (0.0, 5.0, 15.0)``. attempt 0
must NOT sleep; attempt 1 sleeps 5.0s; attempt 2 sleeps 15.0s. Only
``ProviderTransientError`` triggers retry. ``ProviderAuthError``,
``ProviderRateLimitError`` and ``ProviderResponseError`` propagate on
the first attempt with no sleep (D-02 / D-19 fail-fast routing).

Tests monkeypatch ``seers_harness.agentic.tool_loop.time.sleep`` to a
list-recording lambda so wall-clock time is not consumed and backoff
values are observable.
"""

from __future__ import annotations

import pytest

from seers_harness.agentic.tool_loop import (
    _TRANSIENT_BACKOFF_SECONDS,
    run_skill_via_tools,
)
from seers_harness.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransientError,
)
from tests.fakes.scripted_provider import ScriptedProvider, ScriptedTurn


_PAYLOAD = {"user_state": {}, "products": []}


def _success_turn() -> ScriptedTurn:
    """A scripted turn that immediately submits a final artifact, terminating the loop in 1 turn."""
    return ScriptedTurn(
        tool_calls=[
            {
                "id": "c-final",
                "name": "submit_factors_final",
                "arguments": {"factors": []},
            }
        ]
    )


def _final_handler(args, state):
    state["final_artifact"] = args
    return "OK"


def _tool_handlers():
    return {"submit_factors_final": _final_handler}


def _tools_spec():
    # The loop never validates tools_spec content for our purposes — handlers
    # dispatch by tool name. An empty list keeps the test hermetic.
    return []


def test_tool_loop_backoff_on_transient(monkeypatch):
    """D8-B: provider raises transient on attempts 0 and 1, succeeds on
    attempt 2 → ``time.sleep`` is called twice with the backoff values
    matching attempts 1 and 2 (5.0s, 15.0s). attempt 0 must NOT sleep."""
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "seers_harness.agentic.tool_loop.time.sleep",
        lambda s: sleep_calls.append(s),
    )

    script = [
        ScriptedTurn(raise_exc=ProviderTransientError("503 attempt 0")),
        ScriptedTurn(raise_exc=ProviderTransientError("503 attempt 1")),
        _success_turn(),
    ]
    provider = ScriptedProvider(script=script)
    result = run_skill_via_tools(
        skill_name="discover-personalization-factors",
        skill_bundle="SKILL_BODY",
        payload=_PAYLOAD,
        tools_spec=_tools_spec(),
        tool_handlers=_tool_handlers(),
        provider=provider,
        node_id="n",
        max_transient_retries_per_turn=2,
    )

    # Loop terminated successfully on attempt-2's submit.
    assert result.artifact == {"factors": []}
    assert result.turns_used == 1
    # Backoff was applied for attempts 1 and 2 (and ONLY those).
    assert sleep_calls == [5.0, 15.0]
    # Provider was called exactly 3 times.
    assert provider._idx == 3


def test_tool_loop_does_not_backoff_on_first_attempt(monkeypatch):
    """D8-B: when attempt 0 succeeds, no ``time.sleep`` call is issued."""
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "seers_harness.agentic.tool_loop.time.sleep",
        lambda s: sleep_calls.append(s),
    )

    provider = ScriptedProvider(script=[_success_turn()])
    result = run_skill_via_tools(
        skill_name="discover-personalization-factors",
        skill_bundle="SKILL_BODY",
        payload=_PAYLOAD,
        tools_spec=_tools_spec(),
        tool_handlers=_tool_handlers(),
        provider=provider,
        node_id="n",
        max_transient_retries_per_turn=2,
    )

    assert result.artifact == {"factors": []}
    assert result.turns_used == 1
    assert sleep_calls == []
    assert provider._idx == 1


@pytest.mark.parametrize(
    "exc",
    [
        ProviderAuthError("401 invalid api key"),
        ProviderRateLimitError("429 too many requests"),
        ProviderResponseError("malformed tool_calls"),
    ],
    ids=["auth", "rate_limit", "response"],
)
def test_tool_loop_does_not_retry_auth_error(monkeypatch, exc):
    """D8-B: only ``ProviderTransientError`` is retried. ``ProviderAuthError``,
    ``ProviderRateLimitError`` and ``ProviderResponseError`` propagate on the
    first attempt with no ``time.sleep`` call (D-02 / D-19 fail-fast)."""
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "seers_harness.agentic.tool_loop.time.sleep",
        lambda s: sleep_calls.append(s),
    )

    script = [ScriptedTurn(raise_exc=exc)]
    provider = ScriptedProvider(script=script)
    with pytest.raises(type(exc)):
        run_skill_via_tools(
            skill_name="discover-personalization-factors",
            skill_bundle="SKILL_BODY",
            payload=_PAYLOAD,
            tools_spec=_tools_spec(),
            tool_handlers=_tool_handlers(),
            provider=provider,
            node_id="n",
            max_transient_retries_per_turn=2,
        )

    assert sleep_calls == []
    # Provider was called exactly once — no retry attempts.
    assert provider._idx == 1


def test_tool_loop_exhausts_transient_budget(monkeypatch):
    """D8-B: 3 consecutive ``ProviderTransientError`` exhausts the budget
    (1 initial + 2 retries). The final transient error propagates; the
    backoff sequence ``[5.0, 15.0]`` is observed before the final attempt."""
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "seers_harness.agentic.tool_loop.time.sleep",
        lambda s: sleep_calls.append(s),
    )

    script = [
        ScriptedTurn(raise_exc=ProviderTransientError("503 attempt 0")),
        ScriptedTurn(raise_exc=ProviderTransientError("503 attempt 1")),
        ScriptedTurn(raise_exc=ProviderTransientError("503 attempt 2 (final)")),
    ]
    provider = ScriptedProvider(script=script)
    with pytest.raises(ProviderTransientError, match="attempt 2"):
        run_skill_via_tools(
            skill_name="discover-personalization-factors",
            skill_bundle="SKILL_BODY",
            payload=_PAYLOAD,
            tools_spec=_tools_spec(),
            tool_handlers=_tool_handlers(),
            provider=provider,
            node_id="n",
            max_transient_retries_per_turn=2,
        )

    # Only attempts 1 and 2 sleep (attempt 0 does not). Even on the last
    # attempt the sleep happens BEFORE the call that ultimately raises.
    assert sleep_calls == [5.0, 15.0]
    assert provider._idx == 3


def test_transient_backoff_constant_literal_locked():
    """D8-B charter lock: the module-level constant must remain
    ``(0.0, 5.0, 15.0)``. A future patch silently changing this sequence
    (T-08-08-02 in the threat register) is caught here at unit-test time."""
    assert _TRANSIENT_BACKOFF_SECONDS == (0.0, 5.0, 15.0)
