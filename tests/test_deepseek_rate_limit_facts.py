"""Tests for DeepSeek runtime fact extraction and doc consistency (PROD-02).

Plan 06-04 task 06-04-02 acceptance criteria:

- ``deepseek_runtime_facts()["default_model"] == "deepseek-v4-pro"``
- base URL is ``https://api.deepseek.com/beta``
- SDK max retries default is ``0``
- 429-like exceptions classify as ``rate_limit``
- function does not make network calls and does not instantiate an SDK
  client (this file asserts the import-time and call-time isolation).

Plan 06-04 task 06-04-03 acceptance criteria (doc-content audit):

- ``docs/deepseek_rate_limit_facts.md`` contains ``deepseek-v4-pro``
- contains ``https://api.deepseek.com/beta``
- contains the literal ``SDK max retries: 0``
- contains the explicit Phase-6 non-goal: no concurrency tuning, no limiter.

The doc-content checks live alongside the runtime-fact checks so a single
``pytest tests/test_deepseek_rate_limit_facts.py -q`` invocation gates both
the data source and the documented surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from seers_harness.provider_runtime.openai_compatible import (
    DEEPSEEK_BETA_BASE_URL,
    deepseek_runtime_facts,
)

DOC_PATH = (
    Path(__file__).parents[1] / "docs" / "deepseek_rate_limit_facts.md"
)


def test_default_model_is_deepseek_v4_pro() -> None:
    facts = deepseek_runtime_facts()
    assert facts["default_model"] == "deepseek-v4-pro"


def test_default_base_url_is_deepseek_beta() -> None:
    facts = deepseek_runtime_facts()
    assert facts["default_base_url"] == "https://api.deepseek.com/beta"
    # The module constant must match the surfaced fact.
    assert facts["default_base_url"] == DEEPSEEK_BETA_BASE_URL


def test_default_sdk_max_retries_is_zero() -> None:
    facts = deepseek_runtime_facts()
    assert facts["default_sdk_max_retries"] == 0


def test_default_timeout_seconds_is_180() -> None:
    facts = deepseek_runtime_facts()
    # Matches the env-fallback default in ``deepseek_provider_from_env``.
    assert facts["default_timeout_seconds"] == 180


def test_thinking_and_reasoning_locked_per_adr_probe_7_1_1() -> None:
    facts = deepseek_runtime_facts()
    assert facts["thinking_enabled"] is True
    assert facts["reasoning_effort"] == "max"
    assert facts["tool_choice"] == "auto"


def test_rate_limit_exception_category_is_rate_limit() -> None:
    facts = deepseek_runtime_facts()
    assert facts["rate_limit_exception_category"] == "rate_limit"


def test_deepseek_runtime_facts_does_not_call_network_or_instantiate_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If `deepseek_runtime_facts` accidentally instantiated an OpenAI client
    or called the network, the patched constructor would raise.
    """

    import seers_harness.provider_runtime.openai_compatible as mod

    def _explode(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "deepseek_runtime_facts must be a pure function — it must not"
            " instantiate an SDK client"
        )

    # Patching the imported `OpenAI` symbol catches any accidental client
    # construction inside `deepseek_runtime_facts`.
    monkeypatch.setattr(mod, "OpenAI", _explode)
    facts = mod.deepseek_runtime_facts()
    assert isinstance(facts, dict)
    assert "default_model" in facts


def test_deepseek_runtime_facts_keys_are_stable() -> None:
    facts = deepseek_runtime_facts()
    expected_keys = {
        "default_model",
        "default_base_url",
        "default_timeout_seconds",
        "default_sdk_max_retries",
        "thinking_enabled",
        "reasoning_effort",
        "tool_choice",
        "rate_limit_exception_category",
    }
    assert set(facts.keys()) == expected_keys


# ---- Doc-content audits (plan 06-04 task 06-04-03) ---------------------


def _doc_text() -> str:
    assert DOC_PATH.exists(), f"missing fact doc at {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def test_doc_contains_default_model_literal() -> None:
    assert "deepseek-v4-pro" in _doc_text()


def test_doc_contains_base_url_literal() -> None:
    assert "https://api.deepseek.com/beta" in _doc_text()


def test_doc_contains_sdk_max_retries_zero_literal() -> None:
    # Plan 06-04 acceptance pins the literal phrase "SDK max retries: 0".
    assert "SDK max retries: 0" in _doc_text()


def test_doc_states_phase_6_does_not_tune_concurrency_or_add_limiter() -> None:
    text = _doc_text().lower()
    # Both halves of the non-goal must be present.
    assert "phase 6" in text
    assert "does not" in text or "non-goal" in text
    assert "concurrency" in text
    assert "limiter" in text


def test_doc_records_fact_date() -> None:
    # Phase-6 plan 06-04 task 06-04-03 requires the fact date 2026-05-26.
    assert "2026-05-26" in _doc_text()


def test_doc_describes_optional_probe_policy() -> None:
    text = _doc_text()
    assert "DEEPSEEK_API_KEY" in text
    assert "off by default" in text.lower()
