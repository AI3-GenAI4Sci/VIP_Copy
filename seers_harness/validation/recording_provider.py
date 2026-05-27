"""RecordingProvider — Phase 7 plan 07-02 evidence-capture proxy (D-08).

A content-neutral wrapper around
``seers_harness.provider_runtime.openai_compatible.OpenAICompatibleProvider``.
The wrapper captures each ``generate_with_tools`` invocation into a
``request_log`` list (one record per call) and otherwise behaves
identically to the inner provider — same return value, same exceptions,
same surface (unknown attributes are forwarded via ``__getattr__``).

Per D-08 the proxy is content-neutral: it does not interpret messages,
does not retry, does not classify errors, and does not swallow
exceptions — those are upstream concerns. There is **no** ``try``/
``except`` around the inner provider call inside the override.

The captured record shape is the input to the per-node JSONL writer in
``seers_harness.validation.evidence_writer`` (D-22b):

.. code-block:: python

    {
        "node_id": str | None,
        "messages": list[dict],     # request copy (deep-copied)
        "response": dict,           # serialized ProviderResult fields
        "tool_calls": list[dict],   # parsed tool_calls (id, name, arguments)
        "last_usage": dict,         # prompt_tokens/completion_tokens/
                                    # total_tokens/model
        "final_artifact": None,     # filled by the writer's fallback
    }

``set_current_node_id`` (and its sibling ``get_current_node_id``)
back the per-call ``node_id`` stamping with a
``contextvars.ContextVar`` so the stage runner can scope a node
without threading the id through every call.
"""

from __future__ import annotations

import contextvars
import copy
from dataclasses import asdict, is_dataclass
from typing import Any

# ContextVar so the stage runner (07-04) can stamp records with the
# current node_id without threading the id through every call. The
# inner provider already accepts ``node_id`` as a keyword argument; when
# both are present, the kwarg wins. The contextvar is the fallback.
_current_node_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_recording_provider_current_node_id",
    default=None,
)


def set_current_node_id(node_id: str | None) -> contextvars.Token:
    """Stamp future captured records with ``node_id`` until reset.

    Returns the ``contextvars.Token`` from :py:meth:`ContextVar.set` so
    callers may revert via :py:meth:`ContextVar.reset` once the node
    boundary closes.

    IN-05 note — the stage runner currently both calls this and also
    passes ``node_id`` as a kwarg to ``generate_with_tools``. When both
    are present, the kwarg wins (see :py:meth:`RecordingProvider.generate_with_tools`).
    The ContextVar fallback exists for callers that drive the provider
    through wrapper code without the kwarg (e.g. a future trial_runner
    path); deleting it would be a silent API break for such callers.
    """
    return _current_node_id.set(node_id)


def get_current_node_id() -> str | None:
    """Return the node_id currently set via :func:`set_current_node_id`."""
    return _current_node_id.get()


class RecordingProvider:
    """Content-neutral recording proxy around ``OpenAICompatibleProvider``.

    Composition, not inheritance, per D-08. The wrapper appends one
    fully populated record to ``request_log`` per
    ``generate_with_tools`` call, then returns the inner provider's
    :class:`~seers_harness.provider_runtime.base.ProviderResult`
    unchanged. Exceptions from the inner call propagate unchanged.

    Unknown attributes are forwarded to ``inner`` via :py:meth:`__getattr__`,
    so callers see the inner provider's full surface (``last_usage``,
    ``model``, ``client``, etc.).
    """

    def __init__(self, inner: Any, request_log: list[dict]) -> None:
        # Plain ``self.<name>`` assignment is enough — Python's normal
        # attribute lookup finds these in ``self.__dict__`` before
        # ``__getattr__`` is consulted, so no recursion risk.
        self.inner = inner
        self.request_log = request_log

    def __getattr__(self, name: str) -> Any:
        # __getattr__ runs only when the attribute is NOT found on the
        # instance or its type. The explicit ``generate_with_tools``
        # override below therefore never lands here. Forward everything
        # else (e.g. ``last_usage``, ``model``, ``client``) to ``inner``.
        return getattr(self.inner, name)

    def generate_with_tools(
        self,
        *,
        node_id: str,
        skill_bundle: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        # Deep-copy the request messages BEFORE the inner call. The
        # tool_loop mutates ``messages`` after the call returns
        # (appending the assistant turn + tool results), so a shallow
        # copy would let those later mutations bleed into our snapshot
        # of the *outgoing* request shape.
        captured_messages = copy.deepcopy(messages)

        # NO try/except here (D-08): exceptions propagate unchanged so
        # the stage runner can fail-fast (D-02) on schema/protocol
        # errors and route transient/rate-limit errors per D-19.
        result = self.inner.generate_with_tools(
            node_id=node_id,
            skill_bundle=skill_bundle,
            messages=messages,
            tools=tools,
        )

        # Build the captured record. ``response`` is a JSON-friendly
        # dict (raw_tool_calls SDK objects are dropped because the
        # parsed form ``result.tool_calls`` already carries the data).
        response_dict = _result_to_dict(result)

        # Pull tool_calls in the parsed shape the inner provider returns
        # ({"id", "name", "arguments"}). Empty list when none.
        tool_calls = list(getattr(result, "tool_calls", []) or [])

        # last_usage snapshot. The inner provider populates
        # ``last_usage`` (prompt_tokens, completion_tokens,
        # total_tokens) on every call. We attach ``model`` from the
        # inner provider attribute when the SDK did not echo it back so
        # the per-node ``usage.json`` always carries the model name.
        usage = dict(getattr(self.inner, "last_usage", {}) or {})
        if "model" not in usage:
            inner_model = getattr(self.inner, "model", None)
            if inner_model is not None:
                usage["model"] = inner_model

        # Resolve node_id: prefer the kwarg the harness passes; fall
        # back to the contextvar so stage runners that drive the
        # provider through wrapper code without the kwarg still get
        # stamped records.
        resolved_node_id = node_id if node_id is not None else _current_node_id.get()

        record: dict[str, Any] = {
            "node_id": resolved_node_id,
            "messages": captured_messages,
            "response": response_dict,
            "tool_calls": tool_calls,
            "last_usage": usage,
            # ``final_artifact`` is intentionally None here. The
            # evidence_writer falls back to the last tool_call
            # arguments / last assistant message when None — the
            # stage runner may also set it explicitly after the
            # tool_loop returns (when the artifact path on disk has
            # been validated).
            "final_artifact": None,
        }
        self.request_log.append(record)
        return result


def _result_to_dict(result: Any) -> dict[str, Any]:
    """Best-effort serialize a ``ProviderResult`` into a JSON-friendly dict.

    Drops ``raw_tool_calls`` (SDK objects, not JSON-serializable). All
    other fields on ``ProviderResult`` are plain Python types or simple
    containers. Falls back to per-attribute extraction if a non-
    dataclass duck-typed object slips through.
    """
    if is_dataclass(result):
        d = asdict(result)
        d.pop("raw_tool_calls", None)
        return d
    keys = (
        "payload",
        "usage",
        "tool_calls",
        "finish_reason",
        "reasoning_content",
        "raw_messages",
        "raw_response_text",
        "model",
    )
    out: dict[str, Any] = {}
    for k in keys:
        if hasattr(result, k):
            out[k] = getattr(result, k)
    return out
