"""Plan 02-02 RED tests — OpenAICompatibleProvider behavior contract.

13 behaviors driven by an in-process ``fake_openai_client``. No real openai
SDK call, no API key, no network. The fake is injected by monkeypatching the
LOCAL module symbol ``seers_harness.provider_runtime.openai_compatible.OpenAI``
BEFORE provider construction — necessary because the impl uses
``from openai import OpenAI`` at module top, which copies the reference into the
module's local namespace at import time.

PROV-01..06 coverage map:
  PROV-01 (single entry)          -> all tests use generate_with_tools
  PROV-02 (no response_format)    -> test_generate_with_tools_does_not_pass_response_format
  PROV-03 (locked runtime params) -> test_generate_with_tools_passes_locked_runtime_params_every_call
                                  -> test_deepseek_provider_from_env_uses_beta_base_url
  PROV-04 (exception routing)     -> 4 routing tests (rate_limit, transient, auth, unknown)
  PROV-05 (tool_calls + parsed args) -> test_arguments_are_parsed_to_dict_not_raw_string
                                     -> test_arguments_parse_failure_raises_provider_response_error
                                     -> test_generate_with_tools_returns_provider_result_with_tool_calls
                                     -> test_generate_with_tools_returns_empty_tool_calls_on_stop
"""

from __future__ import annotations

import json

import pytest

from seers_harness.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransientError,
)
from seers_harness.provider_runtime.openai_compatible import (
    OpenAICompatibleProvider,
    deepseek_runtime_facts,
    deepseek_provider_from_env,
)


def _make_provider(monkeypatch, fake_openai_client) -> OpenAICompatibleProvider:
    """Rebind the LOCAL module symbol before constructing the provider.

    Patching ``openai.OpenAI`` would not work because the impl does
    ``from openai import OpenAI`` at the top of the module, which copies the
    reference into the module's namespace at import time.
    """
    monkeypatch.setattr(
        "seers_harness.provider_runtime.openai_compatible.OpenAI",
        lambda **kw: fake_openai_client,
    )
    return OpenAICompatibleProvider(model="deepseek-v4-pro", api_key="sk-test")


def test_generate_with_tools_returns_provider_result_with_tool_calls(
    monkeypatch, fake_openai_client, fake_openai_response
):
    provider = _make_provider(monkeypatch, fake_openai_client)
    fake_openai_client.queue_response(
        fake_openai_response(
            tool_calls=[
                {"id": "call_1", "name": "record_factor", "arguments": json.dumps({"factor_id": "F1"})}
            ],
            finish_reason="tool_calls",
        )
    )
    result = provider.generate_with_tools(
        node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
    )
    assert result.tool_calls == [
        {"id": "call_1", "name": "record_factor", "arguments": {"factor_id": "F1"}}
    ]
    assert result.finish_reason == "tool_calls"


def test_generate_with_tools_returns_empty_tool_calls_on_stop(
    monkeypatch, fake_openai_client, fake_openai_response
):
    provider = _make_provider(monkeypatch, fake_openai_client)
    fake_openai_client.queue_response(
        fake_openai_response(tool_calls=None, finish_reason="stop")
    )
    result = provider.generate_with_tools(
        node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
    )
    assert result.tool_calls == []
    assert result.finish_reason == "stop"


def test_generate_with_tools_passes_locked_runtime_params_every_call(
    monkeypatch, fake_openai_client, fake_openai_response
):
    """PROV-03 — same locked kwargs every turn, regardless of node_id/skill_bundle/messages/tools."""
    provider = _make_provider(monkeypatch, fake_openai_client)
    fake_openai_client.queue_response(
        fake_openai_response(tool_calls=None, finish_reason="stop")
    )
    provider.generate_with_tools(
        node_id="personalized_copy_generation", skill_bundle="sb_a",
        messages=[{"role": "user", "content": "A"}],
        tools=[{"type": "function", "function": {"name": "x"}}],
    )
    fake_openai_client.queue_response(
        fake_openai_response(tool_calls=None, finish_reason="stop")
    )
    provider.generate_with_tools(
        node_id="personalized_copy_generation", skill_bundle="sb_b",
        messages=[{"role": "user", "content": "B"}],
        tools=[{"type": "function", "function": {"name": "y"}}],
    )
    assert len(fake_openai_client.calls) == 2
    for kw in fake_openai_client.calls:
        assert kw["tool_choice"] == "auto"
        assert kw["reasoning_effort"] == "max"
        assert kw["extra_body"] == {"thinking": {"type": "enabled"}}


def test_generate_with_tools_passes_messages_and_tools_through(
    monkeypatch, fake_openai_client, fake_openai_response
):
    provider = _make_provider(monkeypatch, fake_openai_client)
    fake_openai_client.queue_response(
        fake_openai_response(tool_calls=None, finish_reason="stop")
    )
    messages = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
    tools = [{"type": "function", "function": {"name": "x"}}]
    provider.generate_with_tools(node_id="n1", skill_bundle="sb", messages=messages, tools=tools)
    assert fake_openai_client.calls[0]["messages"] == messages
    assert fake_openai_client.calls[0]["tools"] == tools


def test_generate_with_tools_does_not_pass_response_format(
    monkeypatch, fake_openai_client, fake_openai_response
):
    """PROV-02 — no JSON-mode kwarg leaks to the SDK call."""
    provider = _make_provider(monkeypatch, fake_openai_client)
    fake_openai_client.queue_response(
        fake_openai_response(tool_calls=None, finish_reason="stop")
    )
    provider.generate_with_tools(
        node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
    )
    assert "response_format" not in fake_openai_client.calls[0]


def test_arguments_are_parsed_to_dict_not_raw_string(
    monkeypatch, fake_openai_client, fake_openai_response
):
    """PROV-05 — adapter parses tool_call.function.arguments (JSON str) into a dict."""
    provider = _make_provider(monkeypatch, fake_openai_client)
    fake_openai_client.queue_response(
        fake_openai_response(
            tool_calls=[{"id": "call_x", "name": "f", "arguments": '{"factor_id":"F1"}'}],
            finish_reason="tool_calls",
        )
    )
    result = provider.generate_with_tools(
        node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
    )
    assert result.tool_calls[0]["arguments"] == {"factor_id": "F1"}
    assert isinstance(result.tool_calls[0]["arguments"], dict)


def test_arguments_parse_failure_raises_provider_response_error(
    monkeypatch, fake_openai_client, fake_openai_response
):
    """Parse-retry exhausted (budget=1) still surfaces ProviderResponseError."""
    monkeypatch.setenv("DEEPSEEK_PARSE_MAX_RETRIES", "1")
    provider = _make_provider(monkeypatch, fake_openai_client)
    # Both attempts return malformed JSON -> exhausts the budget.
    bad = fake_openai_response(
        tool_calls=[{"id": "call_x", "name": "f", "arguments": '{"factor_id"'}],
        finish_reason="tool_calls",
    )
    seq = iter([bad, bad])

    def _create(**kwargs):
        fake_openai_client.calls.append(kwargs)
        return next(seq)

    fake_openai_client.chat.completions.create = _create
    with pytest.raises(ProviderResponseError):
        provider.generate_with_tools(
            node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
        )
    # Two upstream calls — initial + 1 retry — confirm bounded budget.
    assert len(fake_openai_client.calls) == 2


def test_parse_retry_logs_attempt_without_raw_arguments(
    monkeypatch, fake_openai_client, fake_openai_response, capsys
):
    """Audit log must expose retry attempts without leaking raw model text."""
    monkeypatch.setenv("DEEPSEEK_PARSE_MAX_RETRIES", "1")
    provider = _make_provider(monkeypatch, fake_openai_client)
    bad = fake_openai_response(
        tool_calls=[{"id": "call_x", "name": "f", "arguments": '{"factor_id"'}],
        finish_reason="tool_calls",
    )
    seq = iter([bad, bad])

    def _create(**kwargs):
        fake_openai_client.calls.append(kwargs)
        return next(seq)

    fake_openai_client.chat.completions.create = _create
    with pytest.raises(ProviderResponseError):
        provider.generate_with_tools(
            node_id="personalized_copy_generation",
            skill_bundle="sb",
            messages=[{"role": "user", "content": "go"}],
            tools=[],
        )

    captured = capsys.readouterr()
    assert "[provider] parse_retry node=personalized_copy_generation attempt=1/2" in captured.err
    assert '{"factor_id"' not in captured.err


def test_parse_retry_recovers_when_second_attempt_returns_valid_json(
    monkeypatch, fake_openai_client, fake_openai_response
):
    """CR-05 — malformed tool_call.arguments triggers a bounded retry of the
    full chat.completions.create call. Default budget is at least 1 retry, so a
    first malformed response followed by a valid one yields a successful parse.
    """
    monkeypatch.delenv("DEEPSEEK_PARSE_MAX_RETRIES", raising=False)
    provider = _make_provider(monkeypatch, fake_openai_client)
    bad = fake_openai_response(
        tool_calls=[{"id": "call_x", "name": "f", "arguments": '{"factor_id"'}],
        finish_reason="tool_calls",
    )
    good = fake_openai_response(
        tool_calls=[{"id": "call_x", "name": "f", "arguments": '{"factor_id":"F1"}'}],
        finish_reason="tool_calls",
    )
    seq = iter([bad, good])

    def _create(**kwargs):
        fake_openai_client.calls.append(kwargs)
        return next(seq)

    fake_openai_client.chat.completions.create = _create
    result = provider.generate_with_tools(
        node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
    )
    assert result.tool_calls[0]["arguments"] == {"factor_id": "F1"}
    assert len(fake_openai_client.calls) == 2


def test_parse_retry_budget_zero_disables_retry(
    monkeypatch, fake_openai_client, fake_openai_response
):
    """Budget=0 keeps the original single-shot behaviour."""
    monkeypatch.setenv("DEEPSEEK_PARSE_MAX_RETRIES", "0")
    provider = _make_provider(monkeypatch, fake_openai_client)
    bad = fake_openai_response(
        tool_calls=[{"id": "call_x", "name": "f", "arguments": '{"factor_id"'}],
        finish_reason="tool_calls",
    )
    fake_openai_client.queue_response(bad)
    with pytest.raises(ProviderResponseError):
        provider.generate_with_tools(
            node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
        )
    assert len(fake_openai_client.calls) == 1


def test_rate_limit_error_routes_to_provider_rate_limit_error(
    monkeypatch, fake_openai_client, fake_openai_response
):
    """PROV-04 — type-name containing 'RateLimit' lowercases to 'ratelimit', routes via infer_category."""
    class _FakeRateLimitError(Exception):
        pass

    provider = _make_provider(monkeypatch, fake_openai_client)
    original = _FakeRateLimitError("429 too many requests")
    fake_openai_client.queue_exception(original)
    with pytest.raises(ProviderRateLimitError) as excinfo:
        provider.generate_with_tools(
            node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
        )
    assert excinfo.value.__cause__ is original


def test_transient_error_routes_to_provider_transient_error(
    monkeypatch, fake_openai_client, fake_openai_response
):
    class APITimeoutError(Exception):
        pass

    provider = _make_provider(monkeypatch, fake_openai_client)
    original = APITimeoutError("network timeout")
    fake_openai_client.queue_exception(original)
    with pytest.raises(ProviderTransientError) as excinfo:
        provider.generate_with_tools(
            node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
        )
    assert excinfo.value.__cause__ is original


def test_auth_error_routes_to_provider_auth_error(
    monkeypatch, fake_openai_client, fake_openai_response
):
    class AuthenticationError(Exception):
        pass

    provider = _make_provider(monkeypatch, fake_openai_client)
    original = AuthenticationError("401 unauthorized")
    fake_openai_client.queue_exception(original)
    with pytest.raises(ProviderAuthError) as excinfo:
        provider.generate_with_tools(
            node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
        )
    assert excinfo.value.__cause__ is original


def test_unknown_error_reraises_original(
    monkeypatch, fake_openai_client, fake_openai_response
):
    """PROV-04 — unknown categories re-raise the original exception unwrapped."""
    provider = _make_provider(monkeypatch, fake_openai_client)
    fake_openai_client.queue_exception(ValueError("oh no"))
    with pytest.raises(ValueError, match="oh no"):
        provider.generate_with_tools(
            node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
        )


def test_last_usage_extracted_after_call(
    monkeypatch, fake_openai_client, fake_openai_response
):
    provider = _make_provider(monkeypatch, fake_openai_client)
    fake_openai_client.queue_response(
        fake_openai_response(
            tool_calls=None,
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )
    )
    provider.generate_with_tools(
        node_id="n1", skill_bundle="sb", messages=[{"role": "user", "content": "go"}], tools=[]
    )
    assert provider.last_usage == {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
    }


def test_deepseek_provider_from_env_uses_beta_base_url(
    monkeypatch, fake_openai_client
):
    """PROV-03 — base_url defaults to https://api.deepseek.com/beta (probe-locked)."""
    captured: dict = {}

    def capturing_factory(**kw):
        captured.update(kw)
        return fake_openai_client

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.setattr(
        "seers_harness.provider_runtime.openai_compatible.OpenAI",
        capturing_factory,
    )
    provider = deepseek_provider_from_env()
    assert provider is not None
    assert captured.get("base_url") == "https://api.deepseek.com/beta"


def test_deepseek_provider_from_env_defaults_to_v4_pro(
    monkeypatch, fake_openai_client
):
    """ADR-PROBE-7.1.1 — default model is deepseek-v4-pro (not the deprecated
    deepseek-chat compatibility alias)."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setattr(
        "seers_harness.provider_runtime.openai_compatible.OpenAI",
        lambda **kw: fake_openai_client,
    )
    provider = deepseek_provider_from_env()
    assert provider is not None
    assert provider.model == "deepseek-v4-pro"


def test_deepseek_provider_default_timeout_180s(monkeypatch, fake_openai_client):
    captured: dict = {}

    def capturing_factory(**kw):
        captured.update(kw)
        return fake_openai_client

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("DEEPSEEK_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(
        "seers_harness.provider_runtime.openai_compatible.OpenAI",
        capturing_factory,
    )

    provider = deepseek_provider_from_env()

    assert provider is not None
    assert captured["timeout"] == 180.0


def test_deepseek_runtime_facts_default_timeout_180s():
    assert deepseek_runtime_facts()["default_timeout_seconds"] == 180


def test_deepseek_provider_env_override_still_works(monkeypatch, fake_openai_client):
    captured: dict = {}

    def capturing_factory(**kw):
        captured.update(kw)
        return fake_openai_client

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "240")
    monkeypatch.setattr(
        "seers_harness.provider_runtime.openai_compatible.OpenAI",
        capturing_factory,
    )

    provider = deepseek_provider_from_env()

    assert provider is not None
    assert captured["timeout"] == 240.0
