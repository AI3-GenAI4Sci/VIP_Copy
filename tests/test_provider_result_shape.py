"""PROV-05 contract tests — `ProviderResult` shape and `Provider` Protocol surface.

These RED tests are written BEFORE `seers_harness.provider_runtime.base` exists.
On first run they fail with ImportError — that is the expected RED state.
Task 2 of Plan 02-01 makes them all GREEN by creating the module.

One behavior per test:
  - 5 ProviderResult dataclass shape tests
  - 2 Provider Protocol signature tests (positive + negative)

The negative protocol test (no `generate_json`) locks PROV-01 at the contract
level — the parallel JSON path is deleted from the Protocol, not just from
the `openai_compatible.py` impl that Plan 02-02 will write.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

from seers_harness.provider_runtime.base import Provider, ProviderResult


# --------------------------------------------------------------------------- #
# ProviderResult dataclass shape (PROV-05)                                    #
# --------------------------------------------------------------------------- #


def test_provider_result_has_tool_calls_field() -> None:
    """PROV-05: `tool_calls` must be a declared dataclass field on ProviderResult."""
    field_names = {f.name for f in fields(ProviderResult)}
    assert "tool_calls" in field_names


def test_provider_result_tool_calls_default_empty_list() -> None:
    """PROV-05: `tool_calls` defaults to a FRESH empty list per instance.

    `field(default_factory=list)` semantics — two independent constructions
    must NOT share the same list object (no mutable shared default bug).
    """
    r1 = ProviderResult(payload={}, usage={})
    r2 = ProviderResult(payload={}, usage={})
    assert r1.tool_calls == [] and r2.tool_calls == [] and r1.tool_calls is not r2.tool_calls


def test_provider_result_payload_backcompat_field_present() -> None:
    """PROV-05: `payload` field is kept for back-compat (empty in c17 runtime)."""
    r = ProviderResult(payload={}, usage={})
    assert r.payload == {}


def test_provider_result_finish_reason_field_present() -> None:
    """`finish_reason: str | None` defaults to None — Phase 3 tool_loop reads
    this to detect `tool_calls` vs `stop`."""
    r = ProviderResult(payload={}, usage={})
    assert r.finish_reason is None


def test_provider_result_accepts_tool_calls_shape() -> None:
    """PROV-05: full tool_calls shape `[{id, name, arguments}]` round-trips."""
    tc = [{"id": "call_1", "name": "record_factor", "arguments": {"factor_id": "F1"}}]
    r = ProviderResult(payload={}, usage={}, tool_calls=tc)
    assert r.tool_calls == tc


# --------------------------------------------------------------------------- #
# Provider Protocol signature (PROV-01 contract)                              #
# --------------------------------------------------------------------------- #


def test_provider_protocol_declares_generate_with_tools() -> None:
    """PROV-01: Provider Protocol declares `generate_with_tools` with the
    keyword-only signature `(*, node_id, skill_bundle, messages, tools) -> ProviderResult`."""
    sig = inspect.signature(Provider.generate_with_tools)
    params = list(sig.parameters.values())
    names = [p.name for p in params]
    non_self = params[1:]
    assert (
        names == ["self", "node_id", "skill_bundle", "messages", "tools"]
        and all(p.kind == p.KEYWORD_ONLY for p in non_self)
        and sig.return_annotation in (ProviderResult, "ProviderResult")
    )


def test_provider_protocol_does_not_declare_generate_json() -> None:
    """PROV-01: the c16 parallel JSON path is DELETED at the contract level,
    not just at the impl level. `Provider` must not declare `generate_json`."""
    assert not hasattr(Provider, "generate_json")
