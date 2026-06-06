"""RecordingProvider — Phase 7 plan 07-02 evidence-capture proxy (D-08).

A content-neutral wrapper around
``seers_harness.provider_runtime.openai_compatible.OpenAICompatibleProvider``.
The wrapper captures each ``generate_json`` / ``generate_with_tools`` invocation into a
``request_log`` list (one record per call) and otherwise behaves
identically to the inner provider — same return value, same exceptions,
same surface (unknown attributes are forwarded via ``__getattr__``).

Per D-08 the proxy is content-neutral: it does not interpret messages,
does not retry, does not classify errors, and does not swallow
exceptions — those are upstream concerns. It records successful calls and
partial failure evidence, then re-raises the original exception.

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
``contextvars.ContextVar`` so the batch runner can scope a node
without threading the id through every call.
"""

from __future__ import annotations

import contextvars
from typing import Any

from seers_harness.provider_runtime.capture import (
    build_capture_record,
    build_failure_capture_record,
)

# ContextVar so the batch runner can stamp records with the
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

    IN-05 note — the batch runner currently both calls this and also
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


def reset_current_node_id(token: contextvars.Token) -> None:
    """Public helper to revert a prior :func:`set_current_node_id`.

    WR-04 — callers previously reached into the module-private
    ``_current_node_id`` ContextVar to call ``.reset(token)`` directly.
    This helper restores API hygiene: the ContextVar stays private,
    and the round-trip ``token = set_current_node_id(...)`` →
    ``reset_current_node_id(token)`` is the supported pattern.
    """
    _current_node_id.reset(token)


class RecordingProvider:
    """Content-neutral recording proxy around ``OpenAICompatibleProvider``.

    Composition, not inheritance, per D-08. The wrapper appends one
    fully populated record to ``request_log`` per provider call, then
    returns the inner provider's
    :class:`~seers_harness.provider_runtime.base.ProviderResult`
    unchanged. Exceptions from the inner call are captured as partial
    evidence and propagate unchanged.

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
        # Resolve node_id: prefer the kwarg the harness passes; fall
        # back to the contextvar so batch callers that drive the
        # provider through wrapper code without the kwarg still get
        # stamped records.
        resolved_node_id = node_id if node_id is not None else _current_node_id.get()
        try:
            result = self.inner.generate_with_tools(
                node_id=node_id,
                skill_bundle=skill_bundle,
                messages=messages,
                tools=tools,
            )
        except Exception as exc:
            self.request_log.append(
                build_failure_capture_record(
                    inner=self.inner,
                    exc=exc,
                    node_id=resolved_node_id,
                    messages=messages,
                )
            )
            raise

        self.request_log.append(
            build_capture_record(
                inner=self.inner,
                result=result,
                node_id=resolved_node_id,
                messages=messages,
            )
        )
        return result

    def generate_json(
        self,
        *,
        node_id: str,
        skill_bundle: str,
        messages: list[dict[str, Any]],
    ) -> Any:
        resolved_node_id = node_id if node_id is not None else _current_node_id.get()
        try:
            result = self.inner.generate_json(
                node_id=node_id,
                skill_bundle=skill_bundle,
                messages=messages,
            )
        except Exception as exc:
            self.request_log.append(
                build_failure_capture_record(
                    inner=self.inner,
                    exc=exc,
                    node_id=resolved_node_id,
                    messages=messages,
                )
            )
            raise
        self.request_log.append(
            build_capture_record(
                inner=self.inner,
                result=result,
                node_id=resolved_node_id,
                messages=messages,
            )
        )
        return result
