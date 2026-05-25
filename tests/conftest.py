"""Shared test fixtures for c17 unit + integration tests.

`sample_scenario_payload` mirrors the dict shape `state["payload"]` will have at
runtime — handler tests in Plan 02 use it without rebuilding the dict in every
test. Plan 01 (model tests) does not consume it but the fixture must already
exist so Plan 02 can land in Wave 2 without a chicken-and-egg.

Plan 02-02 appends `fake_openai_response` (factory) and `fake_openai_client`
(stateful fake) used by `test_provider_openai_compatible.py`. They mimic the
openai SDK 1.40+ chat.completions.create response shape WITHOUT importing the
SDK — keeps the test layer hermetic (no network, no key, no soft import).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import pytest


@pytest.fixture
def sample_target_product_id() -> str:
    return "P-001"


@pytest.fixture
def sample_scenario_payload() -> dict:
    return {
        "user_state": {
            "behavior": {
                "recent_search_cat3_30d": "维生素,面膜,精华液",
                "user_top_brand_30d": "雅诗兰黛,资生堂",
            }
        },
        "products": [
            {
                "product_id": "P-001",
                "group_key": "防晒霜/乳",
                "attributes": {
                    "item_cat3_name": "防晒霜",
                    "item_brand_name": "兰蔻",
                    "item_name": "兰蔻轻盈防晒乳",
                },
            }
        ],
        "derived_features_by_product": {
            "P-001": {"cat3_alignment": "match"},
        },
    }


# --- Plan 02-02 additions: fake openai SDK client + response factory --- #


class _FakeOpenAIClient:
    """Drop-in for ``openai.OpenAI(...)`` instances.

    Records every ``chat.completions.create(**kwargs)`` invocation in
    ``self.calls`` and returns whatever was queued via ``queue_response`` /
    ``queue_exception``. NO openai import — the shape mimicry happens via
    ``types.SimpleNamespace`` in the response factory below.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.next_response: Any = None
        self.next_exception: BaseException | None = None
        outer = self

        def _create(**kwargs: Any) -> Any:
            outer.calls.append(kwargs)
            if outer.next_exception is not None:
                exc = outer.next_exception
                outer.next_exception = None
                raise exc
            return outer.next_response

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))

    def queue_response(self, response: Any) -> None:
        self.next_response = response

    def queue_exception(self, exc: BaseException) -> None:
        self.next_exception = exc


@pytest.fixture
def fake_openai_client() -> _FakeOpenAIClient:
    return _FakeOpenAIClient()


@pytest.fixture
def fake_openai_response() -> Callable[..., Any]:
    """Returns a builder ``build(tool_calls, finish_reason, usage=None)``.

    Mimics the openai SDK ``ChatCompletion`` response object via nested
    ``SimpleNamespace`` — ``response.choices[0].message.tool_calls[i].function.{name,arguments}``.

    `tool_calls` is a list of dicts ``{"id": str, "name": str, "arguments": str}``
    (where arguments is the raw JSON string the SDK emits). Pass ``None`` to
    represent the SDK's stop-finish case (``message.tool_calls is None``).

    Usage object exposes ``prompt_tokens`` / ``completion_tokens`` / ``total_tokens``
    as attributes only — DOES NOT define ``model_dump`` so the adapter's
    extract_usage fallback branch is exercised.
    """

    def build(
        tool_calls: list[dict[str, Any]] | None,
        finish_reason: str,
        usage: dict[str, int] | None = None,
    ) -> SimpleNamespace:
        if tool_calls is None:
            tc_objects: list[SimpleNamespace] | None = None
            content: str | None = ""
        else:
            tc_objects = [
                SimpleNamespace(
                    id=tc["id"],
                    function=SimpleNamespace(name=tc["name"], arguments=tc["arguments"]),
                )
                for tc in tool_calls
            ]
            content = None
        reasoning = "R" * 30 if finish_reason == "tool_calls" else None
        message = SimpleNamespace(
            tool_calls=tc_objects,
            content=content,
            reasoning_content=reasoning,
        )
        choice = SimpleNamespace(message=message, finish_reason=finish_reason)
        usage_dict = usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        usage_obj = SimpleNamespace(
            prompt_tokens=usage_dict.get("prompt_tokens", 0),
            completion_tokens=usage_dict.get("completion_tokens", 0),
            total_tokens=usage_dict.get("total_tokens", 0),
        )
        return SimpleNamespace(choices=[choice], model="deepseek-chat", usage=usage_obj)

    return build
